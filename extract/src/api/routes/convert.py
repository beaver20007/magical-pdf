"""Phase 7 — PDF → DOCX / PPTX via LibreOffice or OCR pipeline.

Engine selection:
  auto        — LibreOffice for native PDFs (text layer detected), OCR pipeline for scans
  libreoffice — always LibreOffice (fast, high-fidelity for native PDFs)
  ocr         — always OCR pipeline (Docling + EasyOCR, good for scans / drawings)
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

import fitz
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/convert", tags=["convert"])

# LibreOffice executable — Windows first, then Linux/macOS paths
_LO_CANDIDATES = [
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    "/usr/bin/soffice",
    "/usr/lib/libreoffice/program/soffice",
    "soffice",
]

_MAX_BYTES = int(os.environ.get("CONVERT_MAX_BYTES", 50 * 1024 * 1024))  # 50 MB
_LO_TIMEOUT = int(os.environ.get("LO_TIMEOUT_SEC", 120))


def _libreoffice_bin() -> str | None:
    for path in _LO_CANDIDATES:
        if Path(path).exists():
            return path
    # also check PATH
    found = shutil.which("soffice")
    return found


def _has_text_layer(pdf_bytes: bytes, min_chars: int = 50) -> bool:
    """Return True if PDF has a meaningful native text layer."""
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        total = sum(len(page.get_text("text").strip()) for page in doc)
        return total >= min_chars
    except Exception:
        return False


def _lo_convert(input_path: Path, fmt: str, out_dir: Path, lo_bin: str) -> Path:
    """Run LibreOffice headless conversion. Returns path to output file."""
    lo_fmt_map = {
        "docx": "docx:MS Word 2007 XML",
        "pptx": "pptx:Impress MS PowerPoint 2007 XML",
    }
    lo_fmt = lo_fmt_map.get(fmt)
    if not lo_fmt:
        raise ValueError(f"Unsupported format: {fmt}")

    cmd = [
        lo_bin,
        "--headless",
        "--norestore",
        "--nofirststartwizard",
        "--convert-to", lo_fmt,
        "--outdir", str(out_dir),
        str(input_path),
    ]
    log.info("LibreOffice cmd: %s", " ".join(cmd))
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=_LO_TIMEOUT,
    )
    if result.returncode != 0:
        log.error("LibreOffice stderr: %s", result.stderr)
        raise RuntimeError(f"LibreOffice failed (code {result.returncode}): {result.stderr[:400]}")

    stem = input_path.stem
    out_file = out_dir / f"{stem}.{fmt}"
    if not out_file.exists():
        # LO sometimes changes the stem — find any matching extension
        candidates = list(out_dir.glob(f"*.{fmt}"))
        if not candidates:
            raise RuntimeError(f"LibreOffice conversion produced no .{fmt} file in {out_dir}")
        out_file = candidates[0]
    return out_file


def _ocr_convert(pdf_path: Path, fmt: str, out_dir: Path, languages: list[str]) -> Path:
    """Run OCR pipeline (Docling + EasyOCR). Returns output file path."""
    from src.worker import run_job, write_job_meta

    # Reuse the jobs worker in a temp job dir
    job_dir = out_dir / "job"
    job_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(pdf_path, job_dir / "input.pdf")
    write_job_meta(job_dir, {
        "id": "inline",
        "status": "queued",
        "outputs": [fmt],
        "languages": languages,
    })

    run_job(job_dir, outputs=[fmt], languages=languages)

    out_file = job_dir / f"output.{fmt}"
    if not out_file.exists():
        raise RuntimeError(f"OCR pipeline did not produce output.{fmt}")
    return out_file


@router.post("")
async def convert_pdf(
    file: UploadFile = File(...),
    format: str = Form(default="docx", description="docx or pptx"),
    engine: str = Form(default="auto", description="auto | libreoffice | ocr"),
    languages: str = Form(default="ru,en", description="OCR languages, comma-separated"),
) -> FileResponse:
    """Convert PDF → DOCX or PPTX.

    - engine=auto: LibreOffice for native PDFs, OCR for scans
    - engine=libreoffice: always LibreOffice (fast, preserves layout of native PDFs)
    - engine=ocr: always OCR pipeline (Docling+EasyOCR, for scans and technical drawings)
    """
    fmt = format.lower().strip()
    if fmt not in ("docx", "pptx"):
        raise HTTPException(400, "format must be 'docx' or 'pptx'")

    engine = engine.lower().strip()
    if engine not in ("auto", "libreoffice", "ocr"):
        raise HTTPException(400, "engine must be 'auto', 'libreoffice', or 'ocr'")

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are supported")

    content = await file.read()
    if not content:
        raise HTTPException(400, "Empty file")
    if len(content) > _MAX_BYTES:
        raise HTTPException(413, f"File exceeds {_MAX_BYTES // (1024*1024)} MB limit")

    langs = [lang.strip() for lang in languages.split(",") if lang.strip()] or ["ru", "en"]

    tmp_root = Path(tempfile.mkdtemp(prefix="mpdf_convert_"))
    try:
        input_pdf = tmp_root / f"input_{uuid.uuid4().hex[:8]}.pdf"
        input_pdf.write_bytes(content)

        lo_bin = _libreoffice_bin()
        use_lo = False

        if engine == "libreoffice":
            if not lo_bin:
                raise HTTPException(503, "LibreOffice not found on this server")
            use_lo = True
        elif engine == "ocr":
            use_lo = False
        else:  # auto
            if lo_bin and _has_text_layer(content):
                use_lo = True
                log.info("auto: native text detected → LibreOffice")
            else:
                use_lo = False
                log.info("auto: no text layer → OCR pipeline")

        try:
            if use_lo:
                out_file = _lo_convert(input_pdf, fmt, tmp_root, lo_bin)
            else:
                out_file = _ocr_convert(input_pdf, fmt, tmp_root, langs)
        except subprocess.TimeoutExpired:
            raise HTTPException(504, f"Conversion timed out after {_LO_TIMEOUT}s")
        except RuntimeError as exc:
            raise HTTPException(500, str(exc))

        stem = Path(file.filename).stem
        download_name = f"{stem}.{fmt}"
        media = (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            if fmt == "docx"
            else "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        )

        # FastAPI FileResponse with background cleanup
        response = FileResponse(
            path=out_file,
            media_type=media,
            filename=download_name,
            headers={"X-Engine": "libreoffice" if use_lo else "ocr"},
        )
        # Store tmp_root for manual cleanup — can't delete while FileResponse streams
        # A production setup would use BackgroundTasks; for now the job_cleanup cron handles it
        return response

    except HTTPException:
        shutil.rmtree(tmp_root, ignore_errors=True)
        raise
    except Exception as exc:
        shutil.rmtree(tmp_root, ignore_errors=True)
        log.exception("convert_pdf error")
        raise HTTPException(500, f"Conversion error: {exc}") from exc
