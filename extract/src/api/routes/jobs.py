"""Job API routes."""

from __future__ import annotations

import asyncio
import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import fitz
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from src.config import (
    DEFAULT_LANGUAGES,
    JOBS_DIR,
    MAX_BYTES,
    MAX_CONCURRENT_JOBS,
    MAX_PAGES,
    PUBLIC_BETA,
)
from src.job_cleanup import cleanup_old_jobs
from src.worker import read_job_meta, run_job, write_job_meta

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])

_running: set[str] = set()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _job_dir(job_id: str) -> Path:
    return JOBS_DIR / job_id


def _parse_outputs(output: str) -> list[str]:
    parts = [p.strip().lower() for p in output.split(",") if p.strip()]
    valid = {"docx", "pptx"}
    result = [p for p in parts if p in valid]
    return result or ["docx"]


def _parse_languages(languages: str | None) -> list[str]:
    if not languages:
        return list(DEFAULT_LANGUAGES)
    return [lang.strip() for lang in languages.split(",") if lang.strip()]


async def _execute_job(job_id: str, outputs: list[str], languages: list[str]) -> None:
    _running.add(job_id)
    try:
        await asyncio.to_thread(run_job, _job_dir(job_id), outputs=outputs, languages=languages)
    finally:
        _running.discard(job_id)


@router.post("", status_code=201)
async def create_job(
    file: UploadFile = File(...),
    output: str = Form(default="docx"),
    languages: str | None = Form(default=None),
) -> dict[str, Any]:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are supported")

    content = await file.read()
    if not content:
        raise HTTPException(400, "Empty file")
    if len(content) > MAX_BYTES:
        raise HTTPException(413, f"File exceeds {MAX_BYTES} bytes")

    # Validate page count
    try:
        doc = fitz.open(stream=content, filetype="pdf")
        page_count = doc.page_count
        doc.close()
    except Exception as exc:
        raise HTTPException(400, f"Invalid PDF: {exc}") from exc

    if page_count < 1:
        raise HTTPException(400, "PDF has no pages")
    if page_count > MAX_PAGES:
        raise HTTPException(422, f"PDF exceeds {MAX_PAGES} pages (beta limit)")

    if PUBLIC_BETA and len(_running) >= MAX_CONCURRENT_JOBS:
        raise HTTPException(
            429,
            "Сервер занят другим документом. Подождите и попробуйте снова.",
        )

    cleanup_old_jobs()

    job_id = str(uuid.uuid4())
    job_dir = _job_dir(job_id)
    job_dir.mkdir(parents=True, exist_ok=True)
    (job_dir / "input.pdf").write_bytes(content)

    outputs = _parse_outputs(output)
    langs = _parse_languages(languages)

    meta = {
        "id": job_id,
        "status": "queued",
        "progress": 0.0,
        "created_at": _utc_now(),
        "updated_at": _utc_now(),
        "outputs": outputs,
        "languages": langs,
        "page_count": page_count,
        "error": None,
        "warnings": [],
    }
    write_job_meta(job_dir, meta)

    asyncio.create_task(_execute_job(job_id, outputs, langs))

    return {"id": job_id, "status": "queued", "created_at": meta["created_at"]}


@router.get("/{job_id}")
async def get_job(job_id: str) -> dict[str, Any]:
    job_dir = _job_dir(job_id)
    if not job_dir.exists():
        raise HTTPException(404, "Job not found")

    meta = read_job_meta(job_dir)
    manifest_path = job_dir / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        meta.setdefault("block_count", len(manifest.get("blocks", [])))

    return meta


@router.get("/{job_id}/download.docx")
async def download_docx(job_id: str) -> FileResponse:
    job_dir = _job_dir(job_id)
    meta = read_job_meta(job_dir)
    if not job_dir.exists():
        raise HTTPException(404, "Job not found")
    if meta.get("status") == "failed":
        raise HTTPException(409, meta.get("error", "Job failed"))
    path = job_dir / "output.docx"
    if not path.exists():
        raise HTTPException(404, "DOCX not ready")
    return FileResponse(path, filename="output.docx", media_type=(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ))


@router.get("/{job_id}/download.pptx")
async def download_pptx(job_id: str) -> FileResponse:
    job_dir = _job_dir(job_id)
    meta = read_job_meta(job_dir)
    if not job_dir.exists():
        raise HTTPException(404, "Job not found")
    if meta.get("status") == "failed":
        raise HTTPException(409, meta.get("error", "Job failed"))
    path = job_dir / "output.pptx"
    if not path.exists():
        raise HTTPException(404, "PPTX not ready")
    return FileResponse(
        path,
        filename="output.pptx",
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
    )


@router.get("/{job_id}/manifest.json")
async def download_manifest(job_id: str) -> JSONResponse:
    job_dir = _job_dir(job_id)
    path = job_dir / "manifest.json"
    if not path.exists():
        raise HTTPException(404, "Manifest not found")
    return JSONResponse(json.loads(path.read_text(encoding="utf-8")))
