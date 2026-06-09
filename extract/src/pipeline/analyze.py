"""Docling analysis wrapper — PDF → DocumentIR."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import fitz
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import EasyOcrOptions, PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption

from src.pipeline.font_estimate import DEFAULT_FONT_NAME, estimate_font_size_pt
from src.pipeline.ingest import PdfDocument
from src.pipeline.ir import (
    Bbox,
    DocumentIR,
    ImageBlock,
    MetaInfo,
    Page,
    PageBreakBlock,
    SourceInfo,
    TableBlock,
    TextBlock,
)

# Docling item types — imported lazily inside mapper to avoid import errors before install
_LABEL_ROLE_MAP: dict[str, str] = {
    "title": "title",
    "section_header": "heading",
    "paragraph": "paragraph",
    "text": "paragraph",
    "list_item": "list_item",
    "caption": "caption",
    "page_footer": "footer",
    "page_header": "header",
    "footnote": "caption",
}


def _bbox_from_prov(prov: list[Any], page_sizes: list[tuple[float, float]]) -> tuple[Bbox, int]:
    if not prov:
        return Bbox(), 0
    page_no = getattr(prov[0], "page_no", 1) or 1
    page_index = max(0, int(page_no) - 1)
    box = getattr(prov[0], "bbox", None)
    if box is None:
        return Bbox(), page_index

    l_ = float(getattr(box, "l", 0) or 0)
    t_ = float(getattr(box, "t", 0) or 0)
    r_ = float(getattr(box, "r", 1) or 1)
    b_ = float(getattr(box, "b", 1) or 1)

    if page_index < len(page_sizes):
        pw, ph = page_sizes[page_index]
    else:
        pw, ph = 595.0, 842.0

    if pw <= 0 or ph <= 0:
        return Bbox(), page_index

    # Docling bbox: origin bottom-left in PDF points
    x = l_ / pw
    w = max(0.0, (r_ - l_) / pw)
    y = max(0.0, (ph - t_) / ph)
    h = max(0.0, (t_ - b_) / ph)
    return Bbox(x=x, y=y, w=w, h=h), page_index


def _table_to_rows(table_item: Any, doc: Any) -> list[list[str]]:
    try:
        df = table_item.export_to_dataframe(doc=doc)
        rows: list[list[str]] = []
        for _, row in df.iterrows():
            rows.append([str(v) if v is not None else "" for v in row.tolist()])
        if rows:
            return rows
    except Exception:
        pass

    grid = getattr(getattr(table_item, "data", None), "grid", None)
    if not grid:
        return []

    result: list[list[str]] = []
    for row in grid:
        cells: list[str] = []
        for cell in row:
            text = getattr(cell, "text", "") or ""
            cells.append(str(text).strip())
        result.append(cells)
    return result


def _save_picture(
    item: Any,
    doc: Any,
    assets_dir: Path,
    block_id: str,
) -> str | None:
    assets_dir.mkdir(parents=True, exist_ok=True)
    try:
        pil_image = item.get_image(doc)
        if pil_image is None:
            return None
        out_path = assets_dir / f"{block_id}.png"
        pil_image.save(out_path, format="PNG")
        return str(out_path)
    except Exception:
        return None


def map_docling_to_ir(
    docling_doc: Any,
    pdf: PdfDocument,
    *,
    assets_dir: Path | None = None,
    languages: list[str] | None = None,
) -> DocumentIR:
    from docling_core.types.doc import PictureItem, TableItem, TextItem

    pages = [
        Page(index=i, width_pt=w, height_pt=h)
        for i, (w, h) in enumerate(pdf.page_sizes)
    ]
    blocks: list[Any] = []
    assets = assets_dir or Path("output/assets")
    last_page = -1

    for item, _level in docling_doc.iterate_items():
        prov = getattr(item, "prov", None) or []
        bbox, page_index = _bbox_from_prov(prov, pdf.page_sizes)

        if page_index > last_page and last_page >= 0:
            blocks.append(PageBreakBlock(page_index=last_page))
        last_page = max(last_page, page_index)

        if isinstance(item, TextItem):
            label = str(getattr(item, "label", "paragraph") or "paragraph")
            label_key = label.split(".")[-1].lower() if "." in label else label.lower()
            role = _LABEL_ROLE_MAP.get(label_key, "unknown")
            text = (getattr(item, "text", "") or "").strip()
            if not text:
                continue
            page = pages[page_index] if page_index < len(pages) else Page(index=page_index)
            if bbox.h <= 0:
                bbox.h = max(0.008, estimate_font_size_pt(bbox, page) / page.height_pt)
            if bbox.w <= 0:
                bbox.w = 0.004
            blocks.append(
                TextBlock(
                    page_index=page_index,
                    bbox=bbox,
                    text=text,
                    role=role,  # type: ignore[arg-type]
                    confidence=1.0,
                    font_size_pt=estimate_font_size_pt(bbox, page, text),
                    font_name=DEFAULT_FONT_NAME,
                )
            )
        elif isinstance(item, TableItem):
            rows = _table_to_rows(item, docling_doc)
            if not rows:
                continue
            blocks.append(
                TableBlock(
                    page_index=page_index,
                    bbox=bbox,
                    rows=rows,
                    confidence=0.9,
                )
            )
        elif isinstance(item, PictureItem):
            img_block = ImageBlock(page_index=page_index, bbox=bbox)
            saved = _save_picture(item, docling_doc, assets, img_block.id)
            if saved:
                img_block.image_path = saved
            caption = getattr(item, "caption", "") or ""
            if caption:
                img_block.caption = str(caption)
            blocks.append(img_block)

    try:
        from importlib.metadata import version as pkg_version

        engine_version = pkg_version("docling")
    except Exception:
        engine_version = "unknown"

    return DocumentIR(
        source=SourceInfo(
            filename=pdf.path.name,
            page_count=pdf.page_count,
            languages=languages or ["ru", "en"],
        ),
        pages=pages,
        blocks=blocks,
        meta=MetaInfo(engine="docling", engine_version=str(engine_version)),
    )


def analyze_pdf(
    pdf: PdfDocument,
    *,
    assets_dir: Path | None = None,
    languages: list[str] | None = None,
    images_scale: float = 2.0,
    layout_batch_size: int = 4,
    ocr_batch_size: int = 2,
) -> DocumentIR:
    lang = languages or ["ru", "en"]
    pipeline_options = PdfPipelineOptions(
        do_ocr=True,
        do_table_structure=True,
        generate_picture_images=True,
        images_scale=images_scale,
        layout_batch_size=layout_batch_size,
        ocr_batch_size=ocr_batch_size,
        ocr_options=EasyOcrOptions(lang=lang),
    )
    converter = DocumentConverter(
        allowed_formats=[InputFormat.PDF],
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
        },
    )
    result = converter.convert(str(pdf.path))
    doc = result.document

    ir = map_docling_to_ir(
        doc,
        pdf,
        assets_dir=assets_dir,
        languages=lang,
    )

    # Warn if no text blocks extracted (likely OCR failure)
    text_count = sum(1 for b in ir.blocks if isinstance(b, TextBlock))
    if text_count == 0:
        ir.meta.warnings.append(
            "No text blocks extracted — check OCR languages or scan quality"
        )

    return ir


def render_page_image(pdf_path: Path, page_index: int, dpi: int = 150) -> bytes:
    """Render a PDF page to PNG bytes (utility for debugging)."""
    doc = fitz.open(pdf_path)
    try:
        page = doc.load_page(page_index)
        pix = page.get_pixmap(dpi=dpi)
        return pix.tobytes("png")
    finally:
        doc.close()
