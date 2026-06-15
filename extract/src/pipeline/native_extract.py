"""Native PDF extraction via PyMuPDF — text layer, fonts, tables (no OCR)."""

from __future__ import annotations

from pathlib import Path

import fitz

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
    TextRun,
)

MIN_CHARS_PER_PAGE = 40
MIN_NATIVE_PAGE_RATIO = 0.5
# If more than this fraction of chars are � the text layer is unreadable.
MAX_GARBLED_RATIO = 0.15
_DEFAULT_FONT = "Garamond"


def _garbled_ratio(text: str) -> float:
    """Fraction of replacement characters in text — high value = unreadable encoding."""
    if not text:
        return 0.0
    return text.count("�") / len(text)


def is_native_pdf(path: Path | str) -> bool:
    """True when most pages have a usable (readable) text layer."""
    pdf_path = Path(path)
    doc = fitz.open(pdf_path)
    try:
        if doc.page_count < 1:
            return False
        native_pages = 0
        for i in range(doc.page_count):
            text = doc.load_page(i).get_text().strip()
            if len(text) >= MIN_CHARS_PER_PAGE and _garbled_ratio(text) <= MAX_GARBLED_RATIO:
                native_pages += 1
        return native_pages / doc.page_count >= MIN_NATIVE_PAGE_RATIO
    finally:
        doc.close()


def _norm_bbox(rect: fitz.Rect, page_w: float, page_h: float) -> Bbox:
    if page_w <= 0 or page_h <= 0:
        return Bbox()
    return Bbox(
        x=rect.x0 / page_w,
        y=rect.y0 / page_h,
        w=max(0.0, (rect.x1 - rect.x0) / page_w),
        h=max(0.0, (rect.y1 - rect.y0) / page_h),
    )


def _center_in_bbox(cx: float, cy: float, bb: Bbox, *, margin: float = 0.004) -> bool:
    return (
        bb.x - margin <= cx <= bb.x + bb.w + margin
        and bb.y - margin <= cy <= bb.y + bb.h + margin
    )


def _span_font(span: dict) -> tuple[str, float, bool]:
    name = str(span.get("font") or _DEFAULT_FONT)
    size = float(span.get("size") or 12.0)
    flags = int(span.get("flags") or 0)
    bold = "Bold" in name or bool(flags & 2**4)
    family = name.replace("-Bold", "").replace(",Bold", "").strip() or _DEFAULT_FONT
    return family, size, bold


def _role_from_size(size: float) -> str:
    if size >= 18:
        return "title"
    if size >= 13:
        return "heading"
    return "paragraph"


def _lines_from_dict(
    page_dict: dict,
    *,
    page_index: int,
    pw: float,
    ph: float,
    skip_inside: list[Bbox],
) -> list[TextBlock]:
    blocks: list[TextBlock] = []
    for raw in page_dict.get("blocks", []):
        if raw.get("type") != 0:
            continue
        for line in raw.get("lines", []):
            spans = line.get("spans", [])
            if not spans:
                continue
            rect = fitz.Rect(line["bbox"])
            bb = _norm_bbox(rect, pw, ph)
            cx, cy = bb.x + bb.w / 2, bb.y + bb.h / 2
            if any(_center_in_bbox(cx, cy, zone) for zone in skip_inside):
                continue

            runs: list[TextRun] = []
            parts: list[str] = []
            max_size = 0.0
            for span in spans:
                text = span.get("text", "")
                if not text:
                    continue
                family, size, bold = _span_font(span)
                max_size = max(max_size, size)
                runs.append(
                    TextRun(text=text, font_name=family, font_size_pt=size, bold=bold)
                )
                parts.append(text)

            joined = "".join(parts).strip()
            if not joined or not runs:
                continue

            blocks.append(
                TextBlock(
                    page_index=page_index,
                    bbox=bb,
                    text=joined,
                    role=_role_from_size(max_size),
                    confidence=1.0,
                    font_size_pt=max_size,
                    font_name=runs[0].font_name,
                    runs=runs,
                )
            )
    return blocks


def _lines_in_rect(
    page: fitz.Page,
    rect: fitz.Rect,
    *,
    page_index: int,
    pw: float,
    ph: float,
) -> list[TextBlock]:
    clip_dict = page.get_text("dict", clip=rect)
    return _lines_from_dict(
        clip_dict,
        page_index=page_index,
        pw=pw,
        ph=ph,
        skip_inside=[],
    )


def _table_cell_blocks(
    page: fitz.Page,
    table: object,
    *,
    page_index: int,
    pw: float,
    ph: float,
) -> list[TextBlock]:
    blocks: list[TextBlock] = []
    data = table.extract()
    for ri, row in enumerate(table.rows):
        for ci, cell_rect in enumerate(row.cells):
            if cell_rect is None:
                continue
            rect = fitz.Rect(cell_rect)
            text = ""
            if ri < len(data) and ci < len(data[ri]) and data[ri][ci]:
                text = str(data[ri][ci]).strip()
            line_blocks = _lines_in_rect(
                page, rect, page_index=page_index, pw=pw, ph=ph
            )
            if line_blocks:
                blocks.extend(line_blocks)
                continue
            if not text:
                continue
            blocks.append(
                TextBlock(
                    page_index=page_index,
                    bbox=_norm_bbox(rect, pw, ph),
                    text=text,
                    role="paragraph",
                    confidence=1.0,
                    font_size_pt=12.0,
                    font_name=_DEFAULT_FONT,
                    runs=[
                        TextRun(
                            text=text,
                            font_name=_DEFAULT_FONT,
                            font_size_pt=12.0,
                            bold=False,
                        )
                    ],
                )
            )
    return blocks


def _save_page_image(
    doc: fitz.Document,
    xref: int,
    assets_dir: Path,
    block_id: str,
) -> str | None:
    try:
        img_info = doc.extract_image(xref)
        ext = img_info.get("ext", "png")
        data = img_info.get("image")
        if not data:
            return None
        assets_dir.mkdir(parents=True, exist_ok=True)
        out = assets_dir / f"native_{block_id}.{ext}"
        out.write_bytes(data)
        return str(out)
    except Exception:
        return None


def extract_native_pdf(
    pdf: PdfDocument,
    *,
    assets_dir: Path | None = None,
    languages: list[str] | None = None,
) -> DocumentIR:
    """Build DocumentIR from PDF text layer with line-level fonts and positions."""
    lang = languages or ["ru", "en"]
    work_assets = assets_dir or pdf.path.parent / "assets"
    images_dir = work_assets / "native_images"

    pages: list[Page] = []
    blocks: list = []

    doc = fitz.open(pdf.path)
    try:
        for page_index in range(doc.page_count):
            page = doc.load_page(page_index)
            pw, ph = pdf.page_sizes[page_index]
            pages.append(Page(index=page_index, width_pt=pw, height_pt=ph))

            if page_index > 0:
                blocks.append(PageBreakBlock(page_index=page_index))

            table_zones: list[Bbox] = []
            table_bottom_pt = 0.0

            try:
                for table in page.find_tables().tables:
                    rect = fitz.Rect(table.bbox)
                    table_bottom_pt = max(table_bottom_pt, rect.y1)
                    bb = _norm_bbox(rect, pw, ph)
                    table_zones.append(bb)

                    # Detect actual column widths from first row cell rects.
                    col_widths_pt: list[float] = []
                    if table.rows:
                        seen_x: dict[int, float] = {}
                        for ci, cell_rect in enumerate(table.rows[0].cells):
                            if cell_rect is not None:
                                r = fitz.Rect(cell_rect)
                                col_widths_pt.append(max(1.0, r.x1 - r.x0))
                            else:
                                col_widths_pt.append(0.0)

                    # Extract structured rows. None in extract() = colspan continuation.
                    rows_data: list[list[str | None]] = []
                    cell_runs_data: list[list[list[TextRun]]] = []
                    cell_aligns_data: list[list[str]] = []
                    raw_rows = table.extract()
                    for ri, row in enumerate(table.rows):
                        row_cells: list[str | None] = []
                        row_cell_runs: list[list[TextRun]] = []
                        row_cell_aligns: list[str] = []
                        for ci, cell_rect in enumerate(row.cells):
                            if ri < len(raw_rows) and ci < len(raw_rows[ri]):
                                raw = raw_rows[ri][ci]
                                if raw is None:
                                    row_cells.append(None)
                                    row_cell_runs.append([])
                                    row_cell_aligns.append("left")
                                    continue
                                cell_text = str(raw).strip()
                            else:
                                cell_text = ""
                            cell_line_runs: list[TextRun] = []
                            cell_align = "left"
                            if cell_rect is not None:
                                cr = fitz.Rect(cell_rect)
                                clip_blocks = _lines_in_rect(
                                    page,
                                    cr,
                                    page_index=page_index,
                                    pw=pw,
                                    ph=ph,
                                )
                                for lb in clip_blocks:
                                    cell_line_runs.extend(lb.runs)
                                if not cell_text:
                                    cell_text = " ".join(b.text for b in clip_blocks).strip()
                                # Detect center alignment: average line center x ≈ cell center x.
                                if clip_blocks:
                                    cell_cx = (cr.x0 + cr.x1) / 2
                                    line_centers = []
                                    for lb in clip_blocks:
                                        tl = lb.bbox.x * pw
                                        tr = (lb.bbox.x + lb.bbox.w) * pw
                                        line_centers.append((tl + tr) / 2)
                                    avg_cx = sum(line_centers) / len(line_centers)
                                    if abs(avg_cx - cell_cx) < (cr.x1 - cr.x0) * 0.20:
                                        cell_align = "center"
                            row_cells.append(cell_text)
                            row_cell_runs.append(cell_line_runs)
                            row_cell_aligns.append(cell_align)
                        rows_data.append(row_cells)
                        cell_runs_data.append(row_cell_runs)
                        cell_aligns_data.append(row_cell_aligns)

                    if rows_data:
                        blocks.append(
                            TableBlock(
                                page_index=page_index,
                                bbox=bb,
                                rows=rows_data,
                                confidence=1.0,
                                col_widths_pt=col_widths_pt,
                                cell_runs=cell_runs_data,
                                cell_aligns=cell_aligns_data,
                            )
                        )
            except Exception:
                pass

            page_dict = page.get_text("dict")
            blocks.extend(
                _lines_from_dict(
                    page_dict,
                    page_index=page_index,
                    pw=pw,
                    ph=ph,
                    skip_inside=table_zones,
                )
            )

            if table_bottom_pt > 0:
                clip = fitz.Rect(0, table_bottom_pt, pw, ph)
                tail_lines = _lines_in_rect(
                    page, clip, page_index=page_index, pw=pw, ph=ph
                )
                for tb in tail_lines:
                    cx = tb.bbox.x + tb.bbox.w / 2
                    cy = tb.bbox.y + tb.bbox.h / 2
                    if any(_center_in_bbox(cx, cy, zone) for zone in table_zones):
                        continue
                    blocks.append(tb)

            for img in page.get_images(full=True):
                xref = img[0]
                try:
                    rects = page.get_image_rects(xref)
                except Exception:
                    rects = []
                for rect in rects:
                    area = (rect.width * rect.height) / max(pw * ph, 1)
                    if area < 0.002:
                        continue
                    block_id = f"p{page_index:03d}_x{xref}"
                    image_path = _save_page_image(doc, xref, images_dir, block_id)
                    if not image_path:
                        continue
                    blocks.append(
                        ImageBlock(
                            page_index=page_index,
                            bbox=_norm_bbox(rect, pw, ph),
                            image_path=image_path,
                            confidence=1.0,
                        )
                    )
    finally:
        doc.close()

    blocks.sort(
        key=lambda b: (
            getattr(b, "page_index", 0),
            getattr(b, "bbox", Bbox()).y,
            getattr(b, "bbox", Bbox()).x,
        )
    )

    text_count = sum(1 for b in blocks if getattr(b, "type", "") == "text")
    return DocumentIR(
        source=SourceInfo(
            filename=pdf.path.name,
            page_count=pdf.page_count,
            languages=lang,
        ),
        pages=pages,
        blocks=blocks,
        meta=MetaInfo(
            engine="pymupdf-native",
            engine_version=fitz.VersionBind,
            warnings=[
                f"native PDF: {text_count} positioned lines with PDF fonts (no OCR)",
            ],
        ),
    )
