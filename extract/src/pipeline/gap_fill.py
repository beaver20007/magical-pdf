"""Fill uncovered ink regions with ImageBlocks to meet layout coverage gate."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from scipy import ndimage

from src.pipeline.ir import Bbox, DocumentIR, ImageBlock, TextBlock
from src.pipeline.masks import ir_layout_mask, pdf_content_mask, render_page_rgb


MIN_BBOX_H = 0.008
MIN_BBOX_W = 0.004
MIN_GAP_AREA_PX = 40
MAX_GAP_AREA_RATIO = 0.55
DPI = 150
PAD_PX = 4


def fix_zero_bboxes(ir: DocumentIR) -> int:
    fixed = 0
    for block in ir.blocks:
        if not hasattr(block, "bbox"):
            continue
        bb = block.bbox
        if bb.h <= 0:
            if isinstance(block, TextBlock):
                page = ir.pages[block.page_index] if block.page_index < len(ir.pages) else None
                if page and block.font_size_pt:
                    bb.h = max(MIN_BBOX_H, block.font_size_pt / page.height_pt)
                else:
                    bb.h = MIN_BBOX_H
            else:
                bb.h = MIN_BBOX_H
            fixed += 1
        if bb.w <= 0:
            bb.w = MIN_BBOX_W
            fixed += 1
    return fixed


def _normalize_bbox(x0: int, y0: int, x1: int, y1: int, w: int, h: int) -> Bbox:
    return Bbox(
        x=x0 / w,
        y=y0 / h,
        w=max(MIN_BBOX_W, (x1 - x0) / w),
        h=max(MIN_BBOX_H, (y1 - y0) / h),
    )


def _overlaps_existing(bb: Bbox, images: list[ImageBlock], iou_thresh: float = 0.6) -> bool:
    for img in images:
        a = img.bbox
        x0 = max(bb.x, a.x)
        y0 = max(bb.y, a.y)
        x1 = min(bb.x + bb.w, a.x + a.w)
        y1 = min(bb.y + bb.h, a.y + a.h)
        if x1 <= x0 or y1 <= y0:
            continue
        inter = (x1 - x0) * (y1 - y0)
        area_b = bb.w * bb.h
        area_a = a.w * a.h
        union = area_a + area_b - inter
        if union > 0 and inter / union >= iou_thresh:
            return True
    return False


def fill_ink_gaps(
    pdf_path: Path | str,
    ir: DocumentIR,
    assets_dir: Path,
    *,
    target_coverage: float = 0.98,
    max_passes: int = 3,
) -> int:
    pdf_path = Path(pdf_path)
    gaps_dir = assets_dir / "gap_fills"
    gaps_dir.mkdir(parents=True, exist_ok=True)
    added = 0

    for page in ir.pages:
        idx = page.index
        content = pdf_content_mask(pdf_path, idx, dpi=DPI)
        width, height = content.size
        page_area = width * height

        for pass_no in range(max_passes):
            layout = ir_layout_mask(ir, idx, width, height, pad_px=PAD_PX)
            c_arr = np.array(content) > 127
            l_arr = np.array(layout) > 127
            gap = c_arr & ~l_arr
            if not gap.any():
                break

            labeled, num = ndimage.label(gap)
            page_rgb = render_page_rgb(pdf_path, idx, dpi=DPI)
            existing_images = [
                b for b in ir.blocks if isinstance(b, ImageBlock) and b.page_index == idx
            ]

            pass_added = 0
            for label_id in range(1, num + 1):
                ys, xs = np.where(labeled == label_id)
                if len(xs) < MIN_GAP_AREA_PX:
                    continue
                area_ratio = len(xs) / page_area
                if area_ratio > MAX_GAP_AREA_RATIO:
                    continue

                x0, x1 = int(xs.min()), int(xs.max()) + 1
                y0, y1 = int(ys.min()), int(ys.max()) + 1
                bbox = _normalize_bbox(x0, y0, x1, y1, width, height)

                if _overlaps_existing(bbox, existing_images):
                    continue

                crop = page_rgb.crop((x0, y0, x1, y1))
                block = ImageBlock(page_index=idx, bbox=bbox, confidence=0.85)
                out_path = gaps_dir / f"gap_p{idx:03d}_{block.id}.png"
                crop.save(out_path, format="PNG")
                block.image_path = str(out_path)
                ir.blocks.append(block)
                existing_images.append(block)
                pass_added += 1
                added += 1

            if pass_added == 0:
                break

            layout = ir_layout_mask(ir, idx, width, height, pad_px=PAD_PX)
            from src.pipeline.masks import layout_coverage

            if layout_coverage(content, layout) >= target_coverage:
                break

        # Aggressive: one ImageBlock for all remaining gap pixels on page
        layout = ir_layout_mask(ir, idx, width, height, pad_px=PAD_PX)
        c_arr = np.array(content) > 127
        l_arr = np.array(layout) > 127
        gap = c_arr & ~l_arr
        if gap.any():
            from src.pipeline.masks import layout_coverage as cov_fn

            if cov_fn(content, layout) < target_coverage:
                labeled, num = ndimage.label(ndimage.binary_dilation(gap, iterations=2))
                page_rgb = render_page_rgb(pdf_path, idx, dpi=DPI)
                existing_images = [
                    b
                    for b in ir.blocks
                    if isinstance(b, ImageBlock) and b.page_index == idx
                ]
                for label_id in range(1, num + 1):
                    ys, xs = np.where(labeled == label_id)
                    if len(xs) < MIN_GAP_AREA_PX:
                        continue
                    x0, x1 = int(xs.min()), int(xs.max()) + 1
                    y0, y1 = int(ys.min()), int(ys.max()) + 1
                    bbox = _normalize_bbox(x0, y0, x1, y1, width, height)
                    if _overlaps_existing(bbox, existing_images, iou_thresh=0.85):
                        continue
                    crop = page_rgb.crop((x0, y0, x1, y1))
                    block = ImageBlock(page_index=idx, bbox=bbox, confidence=0.75)
                    out_path = gaps_dir / f"gap_p{idx:03d}_{block.id}_agg.png"
                    crop.save(out_path, format="PNG")
                    block.image_path = str(out_path)
                    ir.blocks.append(block)
                    existing_images.append(block)
                    added += 1

                layout = ir_layout_mask(ir, idx, width, height, pad_px=PAD_PX)
                if cov_fn(content, layout) < target_coverage and gap.any():
                    ys, xs = np.where(gap)
                    x0, x1 = int(xs.min()), int(xs.max()) + 1
                    y0, y1 = int(ys.min()), int(ys.max()) + 1
                    bbox = _normalize_bbox(x0, y0, x1, y1, width, height)
                    crop = page_rgb.crop((x0, y0, x1, y1))
                    block = ImageBlock(page_index=idx, bbox=bbox, confidence=0.7)
                    out_path = gaps_dir / f"gap_p{idx:03d}_{block.id}_rem.png"
                    crop.save(out_path, format="PNG")
                    block.image_path = str(out_path)
                    ir.blocks.append(block)
                    added += 1

    return added


def _is_gap_path(path: str) -> bool:
    return "gap_fills" in (path or "").replace("\\", "/")


def _already_repaired(ir: DocumentIR) -> bool:
    return any(
        isinstance(b, ImageBlock) and _is_gap_path(b.image_path)
        for b in ir.blocks
    )


def repair_ir_layout(
    pdf_path: Path | str,
    ir: DocumentIR,
    assets_dir: Path,
    *,
    target_coverage: float = 0.98,
) -> dict[str, int]:
    fixed = fix_zero_bboxes(ir)
    if _already_repaired(ir):
        return {"fixed_bboxes": fixed, "gap_images": 0}
    added = fill_ink_gaps(
        pdf_path, ir, assets_dir, target_coverage=target_coverage
    )
    if fixed or added:
        ir.meta.warnings.append(
            f"layout repair: fixed_bboxes={fixed}, gap_image_blocks={added}"
        )
    return {"fixed_bboxes": fixed, "gap_images": added}
