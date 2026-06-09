"""Full pipeline orchestration."""

from __future__ import annotations

import gc
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Literal

import fitz

from src.config import DEFAULT_BATCH_PAGES, PAGE_BG_DPI, PUBLIC_BETA, SUPPLEMENT_OCR
from src.pipeline.analyze import analyze_pdf
from src.pipeline.emit_docx import emit_docx
from src.pipeline.emit_docx_editable import emit_docx_editable
from src.pipeline.emit_docx_layout import emit_docx_layout
from src.pipeline.emit_docx_visual import emit_docx_visual
from src.pipeline.emit_pptx import emit_pptx
from src.pipeline.ingest import PdfDocument, load_pdf
from src.pipeline.ir import DocumentIR, MetaInfo, Page, PageBreakBlock, SourceInfo
from src.pipeline.layout_errors import LayoutValidationError
from src.pipeline.gap_fill import repair_ir_layout
from src.pipeline.page_render import render_pdf_pages
from src.pipeline.supplement_ocr import ocr_image_labels, tag_figure_captions
from src.pipeline.text_correct import correct_document_text
from src.pipeline.text_dedup import normalize_text_blocks
from src.pipeline.validate_layout import validate_layout

LayoutMode = Literal["flow", "visual", "both", "layout"]

_LOW_MEM_PICTURES = not PUBLIC_BETA


def _batch_threshold() -> int:
    return 2 if PUBLIC_BETA else 8


def _resolve_batch_pages(page_count: int, batch_pages: int | None) -> int:
    size = batch_pages if batch_pages is not None else DEFAULT_BATCH_PAGES
    if size <= 0:
        return 0
    return size if page_count > _batch_threshold() else 0


def _extract_pdf_chunk(src: Path, start_page: int, end_page: int, dest: Path) -> None:
    doc = fitz.open(src)
    try:
        chunk = fitz.open()
        try:
            chunk.insert_pdf(doc, from_page=start_page, to_page=end_page - 1)
            chunk.save(dest)
        finally:
            chunk.close()
    finally:
        doc.close()


def _offset_ir_pages(ir: DocumentIR, page_offset: int) -> None:
    for block in ir.blocks:
        if isinstance(block, PageBreakBlock):
            block.page_index += page_offset
        elif hasattr(block, "page_index"):
            block.page_index += page_offset  # type: ignore[attr-defined]


def merge_document_ir(parts: list[DocumentIR], pdf: PdfDocument) -> DocumentIR:
    pages = [
        Page(index=i, width_pt=w, height_pt=h)
        for i, (w, h) in enumerate(pdf.page_sizes)
    ]
    blocks: list = []
    warnings: list[str] = []
    engine = "docling"
    engine_version = "unknown"

    for part in parts:
        blocks.extend(part.blocks)
        warnings.extend(part.meta.warnings)
        engine = part.meta.engine
        engine_version = part.meta.engine_version

    return DocumentIR(
        source=SourceInfo(
            filename=pdf.path.name,
            page_count=pdf.page_count,
            languages=parts[0].source.languages if parts else ["ru", "en"],
        ),
        pages=pages,
        blocks=blocks,
        meta=MetaInfo(engine=engine, engine_version=engine_version, warnings=warnings),
    )


def analyze_pdf_batched(
    pdf: PdfDocument,
    *,
    batch_pages: int = 4,
    assets_dir: Path | None = None,
    languages: list[str] | None = None,
    progress_callback: Callable[[float, str], None] | None = None,
) -> DocumentIR:
    if pdf.page_count <= batch_pages:
        scale = 1.0 if PUBLIC_BETA else (2.0 if pdf.page_count <= 8 else 1.5)
        return analyze_pdf(
            pdf,
            assets_dir=assets_dir,
            languages=languages,
            images_scale=scale,
            layout_batch_size=1 if PUBLIC_BETA else 2,
            ocr_batch_size=1,
            generate_picture_images=_LOW_MEM_PICTURES,
        )

    parts: list[DocumentIR] = []
    work_assets = assets_dir or pdf.path.parent / "assets"
    total_batches = (pdf.page_count + batch_pages - 1) // batch_pages

    for batch_idx, start in enumerate(range(0, pdf.page_count, batch_pages)):
        end = min(start + batch_pages, pdf.page_count)
        msg = f"Batch pages {start + 1}-{end} / {pdf.page_count}"
        print(f"  {msg}...", flush=True)
        if progress_callback:
            progress_callback((batch_idx + 0.1) / total_batches, msg)

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            chunk_path = Path(tmp.name)

        try:
            _extract_pdf_chunk(pdf.path, start, end, chunk_path)
            chunk_pdf = load_pdf(chunk_path)
            ir = analyze_pdf(
                chunk_pdf,
                assets_dir=work_assets,
                languages=languages,
                images_scale=1.0,
                layout_batch_size=1,
                ocr_batch_size=1,
                generate_picture_images=_LOW_MEM_PICTURES,
            )
            _offset_ir_pages(ir, start)
            parts.append(ir)
            gc.collect()
        finally:
            chunk_path.unlink(missing_ok=True)

    merged = merge_document_ir(parts, pdf)
    if progress_callback:
        progress_callback(0.95, "Merging blocks")
    text_count = sum(1 for b in merged.blocks if b.type == "text")
    if text_count == 0:
        merged.meta.warnings.append(
            "No text blocks extracted — check OCR languages or scan quality"
        )
    return merged


def convert_pdf(
    input_path: Path | str,
    *,
    output_docx: Path | None = None,
    output_pptx: Path | None = None,
    manifest_path: Path | None = None,
    assets_dir: Path | None = None,
    languages: list[str] | None = None,
    batch_pages: int | None = None,
    progress_callback: Callable[[float, str], None] | None = None,
    layout_mode: LayoutMode = "both",
    strict_layout: bool = True,
    min_layout_coverage: float = 0.98,
    validation_report_path: Path | None = None,
) -> DocumentIR:
    input_path = Path(input_path)
    pdf = load_pdf(input_path)
    work_assets = assets_dir or input_path.parent / "assets"

    use_batch = _resolve_batch_pages(pdf.page_count, batch_pages)
    if use_batch and pdf.page_count > use_batch:
        ir = analyze_pdf_batched(
            pdf,
            batch_pages=use_batch,
            assets_dir=work_assets,
            languages=languages,
            progress_callback=progress_callback,
        )
    else:
        if progress_callback:
            progress_callback(0.2, "Analyzing document")
        ir = analyze_pdf(
            pdf,
            assets_dir=work_assets,
            languages=languages,
            images_scale=1.0 if PUBLIC_BETA else 2.0,
            layout_batch_size=1 if PUBLIC_BETA else 4,
            ocr_batch_size=1 if PUBLIC_BETA else 2,
            generate_picture_images=_LOW_MEM_PICTURES,
        )

    if SUPPLEMENT_OCR:
        if progress_callback:
            progress_callback(0.88, "OCR labels inside figures")
        ocr_image_labels(
            ir,
            input_path,
            languages=languages or ir.source.languages,
        )
        tag_figure_captions(ir)
    normalize_text_blocks(ir)

    if progress_callback:
        progress_callback(0.89, "Spelling and grammar correction")
    correct_document_text(ir, languages=languages or ir.source.languages)

    if progress_callback:
        progress_callback(0.90, "Repairing layout gaps")
    repair_ir_layout(
        input_path,
        ir,
        work_assets,
        target_coverage=min_layout_coverage,
    )

    page_bg_dir = work_assets / "page_backgrounds"
    bg_paths: list[Path] | None = None
    if layout_mode in ("visual", "both", "layout"):
        if progress_callback:
            progress_callback(0.92, "Rendering page backgrounds")
        bg_paths = render_pdf_pages(input_path, page_bg_dir, dpi=PAGE_BG_DPI)
        for i, p in enumerate(ir.pages):
            if i < len(bg_paths):
                p.background_image = str(bg_paths[i])

    if progress_callback:
        progress_callback(0.94, "Validating layout fidelity")

    validation = validate_layout(
        input_path,
        ir,
        min_iou=min_layout_coverage,
        page_backgrounds=bg_paths,
    )

    report_path = validation_report_path or (
        output_docx.with_suffix(".validation.txt") if output_docx else None
    )
    if report_path:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(validation.summary(), encoding="utf-8")

    if strict_layout and not validation.passed:
        raise LayoutValidationError(validation)

    if manifest_path:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(ir.model_dump_json(indent=2), encoding="utf-8")

    if output_docx:
        if layout_mode == "flow":
            emit_docx(ir, output_docx)
        elif layout_mode == "visual":
            if not bg_paths:
                raise ValueError("visual mode requires page backgrounds")
            emit_docx_visual(ir, output_docx, page_backgrounds=bg_paths)
        elif layout_mode == "layout":
            if not bg_paths:
                raise ValueError("layout mode requires page backgrounds")
            emit_docx_layout(ir, output_docx, page_backgrounds=bg_paths)
        elif layout_mode == "both":
            if not bg_paths:
                raise ValueError("both mode requires page backgrounds")
            emit_docx_visual(ir, output_docx, page_backgrounds=bg_paths)
            emit_docx_editable(
                ir,
                output_docx.with_name(output_docx.stem + "-текст" + output_docx.suffix),
            )

    if output_pptx:
        emit_pptx(ir, output_pptx, page_backgrounds=bg_paths)

    return ir
