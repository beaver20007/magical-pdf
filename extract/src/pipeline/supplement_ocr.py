"""Supplementary EasyOCR — text inside figures and other regions Docling missed."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import fitz
import numpy as np
from PIL import Image

from src.pipeline.cleanup import clean_ocr_text
from src.pipeline.font_estimate import DEFAULT_FONT_NAME
from src.pipeline.ir import Bbox, DocumentIR, ImageBlock, TextBlock
from src.pipeline.text_dedup import bbox_iou, _similar

if TYPE_CHECKING:
    import easyocr

_reader: "easyocr.Reader | None" = None


def _get_reader(languages: list[str]) -> "easyocr.Reader":
    global _reader
    if _reader is None:
        import easyocr

        langs = [lang[:2] for lang in languages] or ["ru", "en"]
        _reader = easyocr.Reader(langs, gpu=False, verbose=False)
    return _reader


def _quad_to_bbox(
    quad: list[list[float]],
    img_w: int,
    img_h: int,
    *,
    offset_x: float = 0.0,
    offset_y: float = 0.0,
    scale_w: float = 1.0,
    scale_h: float = 1.0,
) -> Bbox:
    xs = [p[0] for p in quad]
    ys = [p[1] for p in quad]
    x0, x1 = min(xs) / img_w, max(xs) / img_w
    y0, y1 = min(ys) / img_h, max(ys) / img_h
    return Bbox(
        x=offset_x + x0 * scale_w,
        y=offset_y + y0 * scale_h,
        w=max(0.008, (x1 - x0) * scale_w),
        h=max(0.006, (y1 - y0) * scale_h),
    )


def _existing_texts(ir: DocumentIR, page_index: int) -> list[TextBlock]:
    return [
        b
        for b in ir.blocks
        if isinstance(b, TextBlock) and b.page_index == page_index
    ]


def _center_in(bbox: Bbox, container: Bbox) -> bool:
    cx, cy = bbox.x + bbox.w / 2, bbox.y + bbox.h / 2
    return (
        container.x <= cx <= container.x + container.w
        and container.y <= cy <= container.y + container.h
    )


def _is_duplicate(existing: list[TextBlock], bbox: Bbox, text: str, page_index: int) -> bool:
    for block in existing:
        if block.page_index != page_index:
            continue
        if bbox_iou(block.bbox, bbox) >= 0.25 and _similar(block.text, text):
            return True
    return False


def _plausible_label(text: str) -> bool:
    letters = sum(1 for c in text if c.isalpha())
    if letters < 3:
        return False
    if len(text) < 4:
        return False
    # reject mostly-symbol garbage
    if letters / max(1, len(text)) < 0.35:
        return False
    return True


def _add_text(
    ir: DocumentIR,
    page_index: int,
    bbox: Bbox,
    text: str,
    *,
    existing: list[TextBlock],
    page_h_pt: float,
    role: str = "caption",
) -> bool:
    text = clean_ocr_text(" ".join(text.split()))
    if len(text) < 2:
        return False
    if role == "caption" and not _plausible_label(text):
        return False
    if _is_duplicate(existing, bbox, text, page_index):
        return False
    size_pt = max(7.0, min(24.0, bbox.h * page_h_pt * 0.82))
    block = TextBlock(
        page_index=page_index,
        bbox=bbox,
        text=text,
        role=role,  # type: ignore[arg-type]
        confidence=0.85,
        font_size_pt=size_pt,
        font_name=DEFAULT_FONT_NAME,
    )
    ir.blocks.append(block)
    existing.append(block)
    return True


def _upscale(arr: np.ndarray, factor: int = 2) -> np.ndarray:
    if factor <= 1:
        return arr
    img = Image.fromarray(arr)
    img = img.resize((img.width * factor, img.height * factor), Image.Resampling.LANCZOS)
    return np.array(img)


def _read_detections(
    reader: "easyocr.Reader",
    arr: np.ndarray,
    *,
    img_w: int,
    img_h: int,
    offset_x: float,
    offset_y: float,
    scale_w: float,
    scale_h: float,
    min_confidence: float,
    merge_lines: bool = False,
) -> list[tuple[Bbox, str, float]]:
    """EasyOCR detections mapped to page-normalized bbox."""
    detections: list[tuple[Bbox, str, float]] = []
    for quad, text, conf in reader.readtext(arr, paragraph=False):
        if conf < min_confidence:
            continue
        t = text.strip()
        if len(t) < 2:
            continue
        bbox = _quad_to_bbox(
            quad,
            img_w,
            img_h,
            offset_x=offset_x,
            offset_y=offset_y,
            scale_w=scale_w,
            scale_h=scale_h,
        )
        detections.append((bbox, t, conf))

    if not detections or not merge_lines:
        return detections

    detections.sort(key=lambda d: (d[0].y, d[0].x))
    lines: list[list[tuple[Bbox, str, float]]] = []
    for bbox, text, conf in detections:
        placed = False
        for line in lines:
            ref = line[0][0]
            same_band = abs((bbox.y + bbox.h / 2) - (ref.y + ref.h / 2)) < max(0.01, ref.h * 0.5)
            gap = bbox.x - (line[-1][0].x + line[-1][0].w)
            if same_band and gap <= 0.025:
                line.append((bbox, text, conf))
                placed = True
                break
        if not placed:
            lines.append([(bbox, text, conf)])

    out: list[tuple[Bbox, str, float]] = []
    for line in lines:
        line.sort(key=lambda x: x[0].x)
        x0 = min(b.x for b, _, _ in line)
        y0 = min(b.y for b, _, _ in line)
        x1 = max(b.x + b.w for b, _, _ in line)
        y1 = max(b.y + b.h for b, _, _ in line)
        merged = Bbox(x=x0, y=y0, w=x1 - x0, h=y1 - y0)
        out.append((merged, " ".join(t for _, t, _ in line), sum(c for _, _, c in line) / len(line)))
    return out


def _ocr_region(
    reader: "easyocr.Reader",
    arr: np.ndarray,
    *,
    page_bbox: Bbox,
    page_h_pt: float,
    upscale: int = 2,
    min_confidence: float = 0.28,
) -> list[tuple[Bbox, str]]:
    up = _upscale(arr, upscale)
    uh, uw = up.shape[:2]
    scale_w = page_bbox.w
    scale_h = page_bbox.h
    return _read_detections(
        reader,
        up,
        img_w=uw,
        img_h=uh,
        offset_x=page_bbox.x,
        offset_y=page_bbox.y,
        scale_w=scale_w,
        scale_h=scale_h,
        min_confidence=min_confidence,
        merge_lines=False,
    )


def _render_page_crop(
    pdf_path: Path,
    page_index: int,
    norm_bbox: Bbox,
    *,
    dpi: int = 300,
    pad: float = 0.01,
) -> np.ndarray | None:
    doc = fitz.open(pdf_path)
    try:
        page = doc.load_page(page_index)
        rect = page.rect
        x0 = max(0, (norm_bbox.x - pad) * rect.width)
        y0 = max(0, (norm_bbox.y - pad) * rect.height)
        x1 = min(rect.width, (norm_bbox.x + norm_bbox.w + pad) * rect.width)
        y1 = min(rect.height, (norm_bbox.y + norm_bbox.h + pad) * rect.height)
        clip = fitz.Rect(x0, y0, x1, y1)
        if clip.is_empty:
            return None
        pix = page.get_pixmap(dpi=dpi, clip=clip, alpha=False)
        return np.array(Image.frombytes("RGB", (pix.width, pix.height), pix.samples))
    finally:
        doc.close()


def ocr_image_labels(
    ir: DocumentIR,
    pdf_path: Path | str | None = None,
    *,
    languages: list[str] | None = None,
    min_area: float = 0.08,
    min_confidence: float = 0.42,
    max_labels_per_image: int = 10,
) -> int:
    """OCR diagram labels — high-DPI PDF crop + upscaled asset pass."""
    langs = languages or ir.source.languages or ["ru", "en"]
    reader = _get_reader(langs)
    pdf_path = Path(pdf_path) if pdf_path else None
    added = 0

    for block in list(ir.blocks):
        if not isinstance(block, ImageBlock):
            continue
        if block.bbox.w * block.bbox.h < min_area:
            continue

        page_h_pt = (
            ir.pages[block.page_index].height_pt
            if block.page_index < len(ir.pages)
            else 405.0
        )
        existing = _existing_texts(ir, block.page_index)

        regions: list[tuple[Bbox, str]] = []
        if pdf_path and pdf_path.exists():
            arr = _render_page_crop(pdf_path, block.page_index, block.bbox, dpi=300)
            if arr is not None:
                regions = _ocr_region(
                    reader,
                    arr,
                    page_bbox=block.bbox,
                    page_h_pt=page_h_pt,
                    upscale=2,
                    min_confidence=min_confidence,
                )
        elif block.image_path and Path(block.image_path).exists():
            img = Image.open(block.image_path).convert("RGB")
            regions = _ocr_region(
                reader,
                np.array(img),
                page_bbox=block.bbox,
                page_h_pt=page_h_pt,
                upscale=2,
                min_confidence=min_confidence,
            )

        regions.sort(key=lambda r: r[2], reverse=True)
        kept = 0
        for page_bbox, text, _conf in regions[: max_labels_per_image * 2]:
            if kept >= max_labels_per_image:
                break
            if _add_text(
                ir,
                block.page_index,
                page_bbox,
                text,
                existing=existing,
                page_h_pt=page_h_pt,
                role="caption",
            ):
                added += 1
                kept += 1

    if added:
        ir.meta.warnings.append(f"image label OCR: added {added} text blocks")
    return added


def tag_figure_captions(ir: DocumentIR) -> int:
    """Mark TextBlocks inside ImageBlock bbox as caption role."""
    images = [b for b in ir.blocks if isinstance(b, ImageBlock)]
    tagged = 0
    for block in ir.blocks:
        if not isinstance(block, TextBlock):
            continue
        for img in images:
            if block.page_index == img.page_index and _center_in(block.bbox, img.bbox):
                if block.role != "caption":
                    block.role = "caption"
                    tagged += 1
                break
    return tagged
