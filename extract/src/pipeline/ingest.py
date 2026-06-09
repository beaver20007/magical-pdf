"""PDF ingest — validate and extract page geometry."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import fitz


class IngestError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


@dataclass
class PdfDocument:
    path: Path
    page_count: int
    page_sizes: list[tuple[float, float]]


def load_pdf(path: Path | str) -> PdfDocument:
    pdf_path = Path(path)
    if not pdf_path.exists():
        raise IngestError("invalid_pdf", f"File not found: {pdf_path}")

    try:
        doc = fitz.open(pdf_path)
    except Exception as exc:
        raise IngestError("invalid_pdf", f"Cannot open PDF: {exc}") from exc

    try:
        if doc.is_encrypted:
            raise IngestError("encrypted_pdf", "Encrypted PDFs are not supported in v1")
        if doc.page_count < 1:
            raise IngestError("empty_pdf", "PDF has no pages")

        sizes: list[tuple[float, float]] = []
        for i in range(doc.page_count):
            rect = doc.load_page(i).rect
            sizes.append((rect.width, rect.height))

        return PdfDocument(
            path=pdf_path,
            page_count=doc.page_count,
            page_sizes=sizes,
        )
    finally:
        doc.close()
