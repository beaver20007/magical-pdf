"""Render PDF pages to images for background layer and validation."""

from __future__ import annotations

from pathlib import Path

import fitz


def render_pdf_pages(
    pdf_path: Path | str,
    out_dir: Path,
    *,
    dpi: int = 150,
) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf_path)
    paths: list[Path] = []
    try:
        for i in range(doc.page_count):
            page = doc.load_page(i)
            pix = page.get_pixmap(dpi=dpi, alpha=False)
            out_path = out_dir / f"page_{i:03d}.png"
            pix.save(out_path)
            paths.append(out_path)
    finally:
        doc.close()
    return paths
