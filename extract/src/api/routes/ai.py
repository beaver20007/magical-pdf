"""Phase 8 — AI endpoints: summary, extract-json, redact."""

from __future__ import annotations

import json
import logging
import re
import tempfile
from io import BytesIO
from pathlib import Path

import fitz  # pymupdf
from anthropic import Anthropic, APIStatusError
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from src.config import AI_MAX_INPUT_CHARS, AI_MODEL, ANTHROPIC_API_KEY, MAX_BYTES

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/ai", tags=["ai"])

MAX_FILE_BYTES = MAX_BYTES


def _require_client() -> Anthropic:
    if not ANTHROPIC_API_KEY:
        raise HTTPException(503, "AI not configured: ANTHROPIC_API_KEY missing")
    return Anthropic(api_key=ANTHROPIC_API_KEY)


def _extract_text(data: bytes, max_chars: int = AI_MAX_INPUT_CHARS) -> str:
    """Extract plain text from PDF bytes via pymupdf, truncated to max_chars."""
    doc = fitz.open(stream=data, filetype="pdf")
    parts: list[str] = []
    total = 0
    for page in doc:
        text = page.get_text("text")
        if total + len(text) > max_chars:
            parts.append(text[: max_chars - total])
            break
        parts.append(text)
        total += len(text)
    doc.close()
    return "\n".join(parts).strip()


def _validate_upload(file: UploadFile) -> None:
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        if not (file.filename or "").lower().endswith(".pdf"):
            raise HTTPException(400, "Only PDF files are supported")


# ─────────────────────────────────────────────────────────────
# POST /api/v1/ai/summary
# ─────────────────────────────────────────────────────────────

class SummaryResponse(BaseModel):
    summary: str
    word_count: int
    pages: int


@router.post("/summary", response_model=SummaryResponse)
async def ai_summary(file: UploadFile = File(...)) -> SummaryResponse:
    """Return a concise structured summary of the uploaded PDF."""
    _validate_upload(file)
    data = await file.read()
    if len(data) > MAX_FILE_BYTES:
        raise HTTPException(413, "File too large")

    doc = fitz.open(stream=data, filetype="pdf")
    pages = doc.page_count
    doc.close()

    text = _extract_text(data)
    if not text:
        raise HTTPException(422, "Could not extract text from PDF")

    client = _require_client()
    prompt = (
        "Ты — эксперт по анализу документов. Прочитай текст PDF и напиши краткое резюме "
        "на том же языке, что и документ. Структура ответа:\n\n"
        "## О чём документ\n"
        "<1–2 предложения>\n\n"
        "## Ключевые темы\n"
        "<маркированный список 3–7 пунктов>\n\n"
        "## Главный вывод\n"
        "<1–2 предложения>\n\n"
        f"Текст документа:\n\n{text}"
    )

    try:
        msg = client.messages.create(
            model=AI_MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
    except APIStatusError as e:
        logger.error("Anthropic API error: %s", e)
        raise HTTPException(502, f"AI service error: {e.status_code}") from e

    summary = msg.content[0].text.strip()
    word_count = len(summary.split())
    return SummaryResponse(summary=summary, word_count=word_count, pages=pages)


# ─────────────────────────────────────────────────────────────
# POST /api/v1/ai/extract
# ─────────────────────────────────────────────────────────────

class ExtractResponse(BaseModel):
    fields: dict
    raw_json: str
    pages: int


@router.post("/extract", response_model=ExtractResponse)
async def ai_extract(file: UploadFile = File(...)) -> ExtractResponse:
    """Extract structured fields from document into JSON."""
    _validate_upload(file)
    data = await file.read()
    if len(data) > MAX_FILE_BYTES:
        raise HTTPException(413, "File too large")

    doc = fitz.open(stream=data, filetype="pdf")
    pages = doc.page_count
    doc.close()

    text = _extract_text(data)
    if not text:
        raise HTTPException(422, "Could not extract text from PDF")

    client = _require_client()
    prompt = (
        "Ты — эксперт по извлечению данных из документов. Проанализируй текст PDF и верни "
        "структурированные данные в формате JSON.\n\n"
        "Правила:\n"
        "- Определи тип документа (счёт, договор, заявление, отчёт, резюме и т.д.)\n"
        "- Извлеки все значимые поля (даты, суммы, стороны, номера, адреса и пр.)\n"
        "- Верни ТОЛЬКО валидный JSON без markdown-обёртки, без комментариев\n"
        "- Формат:\n"
        '  {"document_type": "...", "language": "ru/en/...", '
        '"fields": {"field_name": "value", ...}, "entities": {"persons": [], "orgs": [], "dates": [], "amounts": []}}\n\n'
        f"Текст документа:\n\n{text}"
    )

    try:
        msg = client.messages.create(
            model=AI_MODEL,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
    except APIStatusError as e:
        logger.error("Anthropic API error: %s", e)
        raise HTTPException(502, f"AI service error: {e.status_code}") from e

    raw = msg.content[0].text.strip()
    # Strip possible markdown code fences
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        fields = json.loads(raw)
    except json.JSONDecodeError:
        fields = {"raw_text": raw}

    return ExtractResponse(fields=fields, raw_json=raw, pages=pages)


# ─────────────────────────────────────────────────────────────
# POST /api/v1/ai/redact
# ─────────────────────────────────────────────────────────────

class RedactResponse(BaseModel):
    redacted_count: int
    categories: list[str]
    pages: int


_REDACT_FILL = (0.0, 0.0, 0.0)  # black rectangles


@router.post("/redact")
async def ai_redact(file: UploadFile = File(...)) -> Response:
    """Find PII/sensitive data via Claude and return redacted PDF."""
    _validate_upload(file)
    data = await file.read()
    if len(data) > MAX_FILE_BYTES:
        raise HTTPException(413, "File too large")

    text = _extract_text(data, max_chars=40_000)
    if not text:
        raise HTTPException(422, "Could not extract text from PDF")

    client = _require_client()
    prompt = (
        "Ты — эксперт по защите персональных данных. Проанализируй текст PDF и верни "
        "список всех фрагментов, которые нужно скрыть (PII и чувствительные данные).\n\n"
        "Категории для редактирования:\n"
        "- ФИО физических лиц\n"
        "- Номера телефонов\n"
        "- Email-адреса\n"
        "- Паспортные данные, ИНН, СНИЛС\n"
        "- Банковские реквизиты, номера карт\n"
        "- Домашние адреса\n"
        "- Даты рождения\n\n"
        "Верни ТОЛЬКО валидный JSON без markdown:\n"
        '{"items": [{"text": "точная строка из документа", "category": "категория"}, ...], '
        '"categories_found": ["категория1", ...]}\n\n'
        f"Текст документа:\n\n{text}"
    )

    try:
        msg = client.messages.create(
            model=AI_MODEL,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
    except APIStatusError as e:
        logger.error("Anthropic API error: %s", e)
        raise HTTPException(502, f"AI service error: {e.status_code}") from e

    raw = msg.content[0].text.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        result = json.loads(raw)
        items: list[dict] = result.get("items", [])
        categories: list[str] = result.get("categories_found", [])
    except json.JSONDecodeError:
        items = []
        categories = []

    # Apply redactions to PDF
    doc = fitz.open(stream=data, filetype="pdf")
    redacted_count = 0

    for item in items:
        needle: str = item.get("text", "").strip()
        if not needle:
            continue
        for page in doc:
            rects = page.search_for(needle)
            for rect in rects:
                page.add_redact_annot(rect, fill=_REDACT_FILL)
                redacted_count += 1

    doc.apply_redactions()

    out = BytesIO()
    doc.save(out)
    doc.close()

    headers = {
        "X-Redacted-Count": str(redacted_count),
        "X-Categories": ",".join(categories),
        "Content-Disposition": 'attachment; filename="redacted.pdf"',
    }
    return Response(
        content=out.getvalue(),
        media_type="application/pdf",
        headers=headers,
    )
