"""Job worker — runs pipeline for a job directory."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.pipeline.convert import convert_pdf
from src.pipeline.layout_errors import LayoutValidationError


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_job_meta(job_dir: Path) -> dict[str, Any]:
    meta_path = job_dir / "meta.json"
    if meta_path.exists():
        return json.loads(meta_path.read_text(encoding="utf-8"))
    return {}


def write_job_meta(job_dir: Path, meta: dict[str, Any]) -> None:
    job_dir.mkdir(parents=True, exist_ok=True)
    (job_dir / "meta.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def run_job(
    job_dir: Path,
    *,
    outputs: list[str],
    languages: list[str] | None = None,
) -> dict[str, Any]:
    input_pdf = job_dir / "input.pdf"
    meta = read_job_meta(job_dir)
    meta.update({"status": "running", "progress": 0.1, "updated_at": _utc_now()})
    write_job_meta(job_dir, meta)

    try:
        output_docx = job_dir / "output.docx" if "docx" in outputs else None
        output_pptx = job_dir / "output.pptx" if "pptx" in outputs else None
        manifest_path = job_dir / "manifest.json"
        assets_dir = job_dir / "assets"

        def on_progress(progress: float, message: str) -> None:
            meta["progress"] = round(0.1 + progress * 0.85, 2)
            meta["message"] = message
            meta["updated_at"] = _utc_now()
            write_job_meta(job_dir, meta)

        on_progress(0.0, "Starting conversion")

        try:
            ir = convert_pdf(
                input_pdf,
                output_docx=output_docx,
                output_pptx=output_pptx,
                manifest_path=manifest_path,
                assets_dir=assets_dir,
                languages=languages,
                progress_callback=on_progress,
                layout_mode="layout",
                strict_layout=True,
                min_layout_coverage=0.98,
                validation_report_path=job_dir / "layout.validation.txt",
            )
        except LayoutValidationError as exc:
            (job_dir / "layout.validation.txt").write_text(
                exc.result.summary(), encoding="utf-8"
            )
            raise

        meta.update(
            {
                "status": "done",
                "progress": 1.0,
                "updated_at": _utc_now(),
                "outputs": outputs,
                "warnings": ir.meta.warnings,
                "page_count": ir.source.page_count,
                "block_count": len(ir.blocks),
                "error": None,
            }
        )
        write_job_meta(job_dir, meta)
        return meta

    except Exception as exc:
        meta.update(
            {
                "status": "failed",
                "progress": 0.0,
                "updated_at": _utc_now(),
                "error": str(exc),
            }
        )
        write_job_meta(job_dir, meta)
        raise
