"""Merge and deduplicate OCR text blocks."""

from __future__ import annotations

import re

from src.pipeline.cleanup import clean_ocr_text
from src.pipeline.ir import Bbox, DocumentIR, TextBlock


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _similar(a: str, b: str) -> bool:
    na, nb = _norm(a), _norm(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    if na in nb or nb in na:
        return True
    # token overlap
    ta, tb = set(na.split()), set(nb.split())
    if not ta or not tb:
        return False
    overlap = len(ta & tb) / min(len(ta), len(tb))
    return overlap >= 0.85


def bbox_iou(a: Bbox, b: Bbox) -> float:
    ax2, ay2 = a.x + a.w, a.y + a.h
    bx2, by2 = b.x + b.w, b.y + b.h
    ix1, iy1 = max(a.x, b.x), max(a.y, b.y)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    if ix2 <= ix1 or iy2 <= iy1:
        return 0.0
    inter = (ix2 - ix1) * (iy2 - iy1)
    union = a.w * a.h + b.w * b.h - inter
    return inter / union if union > 0 else 0.0


def deduplicate_text_blocks(ir: DocumentIR, *, iou_threshold: float = 0.35) -> int:
    """Drop overlapping text blocks; keep the longer / more specific one."""
    texts = [b for b in ir.blocks if isinstance(b, TextBlock)]
    others = [b for b in ir.blocks if not isinstance(b, TextBlock)]
    texts.sort(key=lambda b: (-len(b.text), -b.bbox.h * b.bbox.w))

    kept: list[TextBlock] = []
    removed = 0
    for block in texts:
        dup = False
        for k in kept:
            if block.page_index != k.page_index:
                continue
            if bbox_iou(block.bbox, k.bbox) >= iou_threshold and _similar(block.text, k.text):
                dup = True
                break
            # same line band, subset text
            if (
                block.page_index == k.page_index
                and abs(block.bbox.y - k.bbox.y) < 0.012
                and _similar(block.text, k.text)
            ):
                dup = True
                break
        if dup:
            removed += 1
        else:
            kept.append(block)

    ir.blocks = others + kept
    if removed:
        ir.meta.warnings.append(f"text dedup: removed {removed} overlapping blocks")
    return removed


def _inside(inner: Bbox, outer: Bbox, margin: float = 0.02) -> bool:
    return (
        inner.x >= outer.x - margin
        and inner.y >= outer.y - margin
        and inner.x + inner.w <= outer.x + outer.w + margin
        and inner.y + inner.h <= outer.y + outer.h + margin
    )


def remove_subsumed_fragments(ir: DocumentIR) -> int:
    """Drop small OCR fragments whose text is already inside a larger block."""
    texts = [b for b in ir.blocks if isinstance(b, TextBlock)]
    others = [b for b in ir.blocks if not isinstance(b, TextBlock)]
    texts.sort(key=lambda b: (-len(b.text), -(b.bbox.w * b.bbox.h)))

    kept: list[TextBlock] = []
    removed = 0
    for block in texts:
        subsumed = False
        nb = _norm(block.text)
        for parent in kept:
            if block.page_index != parent.page_index:
                continue
            if _inside(block.bbox, parent.bbox) and nb in _norm(parent.text):
                subsumed = True
                break
        if subsumed:
            removed += 1
        else:
            kept.append(block)

    ir.blocks = others + kept
    if removed:
        ir.meta.warnings.append(f"text merge: removed {removed} subsumed fragments")
    return removed


def merge_line_fragments(
    ir: DocumentIR,
    *,
    y_tolerance: float = 0.016,
    max_gap: float = 0.04,
) -> int:
    """Merge horizontally adjacent OCR boxes on the same text line."""
    texts = [b for b in ir.blocks if isinstance(b, TextBlock)]
    others = [b for b in ir.blocks if not isinstance(b, TextBlock)]

    by_page: dict[int, list[TextBlock]] = {}
    for block in texts:
        by_page.setdefault(block.page_index, []).append(block)

    merged_all: list[TextBlock] = []
    merged_count = 0

    for page_index, page_texts in by_page.items():
        page_texts.sort(key=lambda b: (b.bbox.y, b.bbox.x))
        lines: list[list[TextBlock]] = []
        for block in page_texts:
            placed = False
            for line in lines:
                if abs(block.bbox.y - line[0].bbox.y) <= y_tolerance:
                    line.append(block)
                    placed = True
                    break
            if not placed:
                lines.append([block])

        for line in lines:
            line.sort(key=lambda b: b.bbox.x)
            group: list[TextBlock] = []
            for block in line:
                if not group:
                    group = [block]
                    continue
                prev = group[-1]
                gap = block.bbox.x - (prev.bbox.x + prev.bbox.w)
                if gap <= max_gap:
                    group.append(block)
                else:
                    merged_all.append(_merge_group(group, page_index))
                    if len(group) > 1:
                        merged_count += len(group) - 1
                    group = [block]
            if group:
                merged_all.append(_merge_group(group, page_index))
                if len(group) > 1:
                    merged_count += len(group) - 1

    ir.blocks = others + merged_all
    if merged_count:
        ir.meta.warnings.append(f"text merge: merged {merged_count} line fragments")
    return merged_count


def _merge_group(group: list[TextBlock], page_index: int) -> TextBlock:
    if len(group) == 1:
        return group[0]
    text = " ".join(clean_ocr_text(b.text) for b in group if b.text.strip())
    x0 = min(b.bbox.x for b in group)
    y0 = min(b.bbox.y for b in group)
    x1 = max(b.bbox.x + b.bbox.w for b in group)
    y1 = max(b.bbox.y + b.bbox.h for b in group)
    base = max(group, key=lambda b: len(b.text))
    return TextBlock(
        page_index=page_index,
        bbox=Bbox(x=x0, y=y0, w=x1 - x0, h=y1 - y0),
        text=text,
        role=base.role,
        confidence=base.confidence,
        font_size_pt=base.font_size_pt,
        font_name=base.font_name,
    )


def deduplicate_caption_blocks(ir: DocumentIR, *, iou_threshold: float = 0.2) -> int:
    """Extra dedup for figure captions — OCR often emits near-duplicates."""
    texts = [b for b in ir.blocks if isinstance(b, TextBlock)]
    others = [b for b in ir.blocks if not isinstance(b, TextBlock)]
    captions = [b for b in texts if b.role == "caption"]
    body = [b for b in texts if b.role != "caption"]
    captions.sort(key=lambda b: (-len(b.text), -b.bbox.w * b.bbox.h))

    kept: list[TextBlock] = []
    removed = 0
    for block in captions:
        dup = False
        for k in kept:
            if block.page_index != k.page_index:
                continue
            if bbox_iou(block.bbox, k.bbox) >= iou_threshold and _similar(block.text, k.text):
                dup = True
                break
        if dup:
            removed += 1
        else:
            kept.append(block)

    ir.blocks = others + body + kept
    if removed:
        ir.meta.warnings.append(f"caption dedup: removed {removed} blocks")
    return removed


def normalize_text_blocks(ir: DocumentIR) -> None:
    """Full post-OCR text cleanup pipeline."""
    remove_subsumed_fragments(ir)
    deduplicate_text_blocks(ir)
    deduplicate_caption_blocks(ir)
    merge_line_fragments(ir)
