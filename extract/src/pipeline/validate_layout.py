"""Layout fidelity validation — gate before DOCX release."""

from __future__ import annotations

from pathlib import Path

from src.pipeline.ir import DocumentIR, ImageBlock, TextBlock
from src.pipeline.layout_errors import (
    LayoutValidationError,
    LayoutValidationResult,
    PageValidation,
)
from src.pipeline.masks import (
    blocks_for_page,
    ir_layout_mask,
    layout_coverage,
    pdf_content_mask,
)

FONT_NOTE_SCANNED = (
    "Скан: исходные шрифты в PDF отсутствуют (только пиксели). "
    "В DOCX подставляется Times New Roman с размером по высоте bbox. "
    "Побуквенное совпадение гаррифов на скане технически недостижимо."
)


def _validate_block_geometry(ir: DocumentIR) -> list[str]:
    failures: list[str] = []
    for block in ir.blocks:
        if block.type == "page_break":
            continue
        bb = block.bbox
        if bb.w <= 0 or bb.h <= 0:
            failures.append(f"{block.id}: zero-size bbox")
        if bb.x < -0.01 or bb.y < -0.01 or bb.x + bb.w > 1.01 or bb.y + bb.h > 1.01:
            failures.append(f"{block.id}: bbox out of page bounds")
        if isinstance(block, TextBlock):
            if not block.text.strip():
                failures.append(f"{block.id}: empty text block")
            if block.font_size_pt and (block.font_size_pt < 4 or block.font_size_pt > 96):
                failures.append(f"{block.id}: implausible font {block.font_size_pt}pt")
        if isinstance(block, ImageBlock) and block.image_path:
            if not Path(block.image_path).exists():
                failures.append(f"{block.id}: missing image {block.image_path}")
    return failures


def validate_layout(
    pdf_path: Path | str,
    ir: DocumentIR,
    *,
    min_iou: float = 0.98,
    page_backgrounds: list[Path] | None = None,
) -> LayoutValidationResult:
    pdf_path = Path(pdf_path)
    failures = _validate_block_geometry(ir)

    if ir.source.page_count != len(ir.pages):
        failures.append(
            f"page_count mismatch: source={ir.source.page_count} pages={len(ir.pages)}"
        )

    if page_backgrounds and len(page_backgrounds) != ir.source.page_count:
        failures.append(
            f"background images: expected {ir.source.page_count}, got {len(page_backgrounds)}"
        )

    page_results: list[PageValidation] = []

    for page in ir.pages:
        idx = page.index
        blocks = blocks_for_page(ir, idx)
        if not blocks:
            failures.append(f"page {idx + 1}: no content blocks")
            page_results.append(
                PageValidation(idx, False, 0.0, "no blocks")
            )
            continue

        content_mask = pdf_content_mask(pdf_path, idx)
        layout_mask = ir_layout_mask(ir, idx, content_mask.width, content_mask.height)
        coverage = layout_coverage(content_mask, layout_mask)
        passed = coverage + 1e-4 >= min_iou
        if not passed:
            failures.append(
                f"page {idx + 1}: layout coverage {coverage:.2%} < required {min_iou:.2%}"
            )
        page_results.append(
            PageValidation(
                idx,
                passed,
                coverage,
                "" if passed else f"coverage {coverage:.1%} below {min_iou:.0%}",
            )
        )

    result = LayoutValidationResult(
        passed=len(failures) == 0,
        pages=page_results,
        failures=failures,
        min_required_iou=min_iou,
        font_note=FONT_NOTE_SCANNED,
    )
    return result


def require_layout_match(
    pdf_path: Path | str,
    ir: DocumentIR,
    *,
    min_iou: float = 0.98,
    page_backgrounds: list[Path] | None = None,
) -> LayoutValidationResult:
    result = validate_layout(
        pdf_path,
        ir,
        min_iou=min_iou,
        page_backgrounds=page_backgrounds,
    )
    if not result.passed:
        raise LayoutValidationError(result)
    return result
