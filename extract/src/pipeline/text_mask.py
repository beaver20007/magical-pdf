"""Mask text regions on raster images so labels can be re-emitted as editable text."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from src.pipeline.ir import Bbox, TableBlock, TextBlock


def _pad_bbox(bbox: Bbox, pad: float) -> Bbox:
    return Bbox(
        x=max(0.0, bbox.x - pad),
        y=max(0.0, bbox.y - pad),
        w=min(1.0 - max(0.0, bbox.x - pad), bbox.w + 2 * pad),
        h=min(1.0 - max(0.0, bbox.y - pad), bbox.h + 2 * pad),
    )


def _sample_fill(img: Image.Image, x0: int, y0: int, x1: int, y1: int) -> tuple[int, int, int]:
    """Pick background color from a thin border around the text box."""
    w, h = img.size
    pixels: list[tuple[int, int, int]] = []
    band = 3
    for x in range(max(0, x0 - band), min(w, x1 + band)):
        for y in (max(0, y0 - band), min(h - 1, y1 + band - 1)):
            pixels.append(img.getpixel((x, y))[:3])  # type: ignore[misc]
    for y in range(max(0, y0 - band), min(h, y1 + band)):
        for x in (max(0, x0 - band), min(w - 1, x1 + band - 1)):
            pixels.append(img.getpixel((x, y))[:3])  # type: ignore[misc]
    if not pixels:
        return (255, 255, 255)
    return (
        sum(p[0] for p in pixels) // len(pixels),
        sum(p[1] for p in pixels) // len(pixels),
        sum(p[2] for p in pixels) // len(pixels),
    )


def mask_text_regions(
    image_path: Path,
    text_blocks: list[TextBlock],
    output_path: Path,
    *,
    pad: float = 0.004,
    fill: tuple[int, int, int] | None = None,
    adaptive: bool = True,
) -> Path:
    """Erase normalized bbox regions; adaptive fill samples nearby background."""
    img = Image.open(image_path).convert("RGB")
    w, h = img.size
    draw = ImageDraw.Draw(img)

    for block in text_blocks:
        extra = 0.006 if block.role == "caption" else pad
        bb = _pad_bbox(block.bbox, extra)
        x0 = int(bb.x * w)
        y0 = int(bb.y * h)
        x1 = int((bb.x + bb.w) * w)
        y1 = int((bb.y + bb.h) * h)
        if x1 <= x0 or y1 <= y0:
            continue
        color = fill if fill else (_sample_fill(img, x0, y0, x1, y1) if adaptive else (255, 255, 255))
        draw.rectangle([x0, y0, x1, y1], fill=color)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, format="PNG")
    return output_path


def mask_page_background(
    bg_path: Path,
    page_text_blocks: list[TextBlock],
    output_path: Path,
    *,
    pad: float = 0.004,
    table_blocks: list[TableBlock] | None = None,
) -> Path:
    """Mask text and table areas so they can be re-emitted as editable Word content.

    Strategy: mask the ENTIRE region from y=0 down to the table bottom with white.
    This eliminates logo/watermark bleed into the header and table area.
    Only the area below the table (stamp + signature) remains visible.
    """
    img = Image.open(bg_path).convert("RGB")
    w, h = img.size
    draw = ImageDraw.Draw(img)

    # Compute the lowest table boundary on this page.
    table_bot_y = max(
        (tblock.bbox.y + tblock.bbox.h for tblock in (table_blocks or [])),
        default=0.0,
    )

    if table_bot_y > 0:
        # Mask everything from the top of the page down to table bottom + small pad.
        # This cleanly removes watermarks/logos from the header and table zones.
        mask_bottom = min(h, int((table_bot_y + 0.01) * h))
        draw.rectangle([0, 0, w, mask_bottom], fill=(255, 255, 255))
    else:
        # No table found — fall back to masking individual text blocks.
        for block in page_text_blocks:
            extra = 0.006 if block.role == "caption" else pad
            bb = _pad_bbox(block.bbox, extra)
            x0, y0 = int(bb.x * w), int(bb.y * h)
            x1, y1 = int((bb.x + bb.w) * w), int((bb.y + bb.h) * h)
            if x1 <= x0 or y1 <= y0:
                continue
            color = _sample_fill(img, x0, y0, x1, y1)
            draw.rectangle([x0, y0, x1, y1], fill=color)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, format="PNG")
    return output_path
