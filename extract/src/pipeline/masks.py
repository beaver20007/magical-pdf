"""PDF / IR layout masks for validation and gap filling."""

from __future__ import annotations

from pathlib import Path

import fitz
import numpy as np
from PIL import Image, ImageDraw

from src.pipeline.ir import DocumentIR


def blocks_for_page(ir: DocumentIR, page_index: int) -> list:
    return [
        b
        for b in ir.blocks
        if getattr(b, "page_index", -1) == page_index and b.type != "page_break"
    ]


def render_page_rgb(pdf_path: Path | str, page_index: int, dpi: int = 150) -> Image.Image:
    doc = fitz.open(pdf_path)
    try:
        page = doc.load_page(page_index)
        pix = page.get_pixmap(dpi=dpi, alpha=False)
        return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    finally:
        doc.close()


def pdf_content_mask(pdf_path: Path | str, page_index: int, dpi: int = 150) -> Image.Image:
    img = render_page_rgb(pdf_path, page_index, dpi=dpi)
    gray = img.convert("L")
    return gray.point(lambda p: 255 if p < 200 else 0)


def ir_layout_mask(
    ir: DocumentIR,
    page_index: int,
    width: int,
    height: int,
    *,
    pad_px: int = 4,
) -> Image.Image:
    mask = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(mask)
    for block in blocks_for_page(ir, page_index):
        if not hasattr(block, "bbox"):
            continue
        bb = block.bbox
        h = max(bb.h, 0.004)
        w = max(bb.w, 0.004)
        x0 = max(0, int(bb.x * width) - pad_px)
        y0 = max(0, int(bb.y * height) - pad_px)
        x1 = min(width, int((bb.x + w) * width) + pad_px)
        y1 = min(height, int((bb.y + h) * height) + pad_px)
        if x1 > x0 and y1 > y0:
            draw.rectangle([x0, y0, x1, y1], fill=255)
    return mask


def layout_coverage(content_mask: Image.Image, layout_mask: Image.Image) -> float:
    if content_mask.size != layout_mask.size:
        layout_mask = layout_mask.resize(content_mask.size, Image.Resampling.NEAREST)
    content = list(content_mask.getdata())
    layout = list(layout_mask.getdata())
    content_count = sum(1 for p in content if p > 127)
    if content_count == 0:
        return 1.0
    inter = sum(1 for c, l in zip(content, layout) if c > 127 and l > 127)
    return inter / content_count
