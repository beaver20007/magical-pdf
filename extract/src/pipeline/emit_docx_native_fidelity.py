"""Premium native PDF → DOCX: masked background + positioned text with PDF fonts."""

from __future__ import annotations

import html
from pathlib import Path

from docx import Document
from docx.enum.text import WD_LINE_SPACING
from docx.oxml import parse_xml
from docx.shared import Pt

from src.pipeline.ir import DocumentIR, ImageBlock, Page, TableBlock, TextBlock, TextRun
from src.pipeline.text_mask import mask_page_background

_PT_TO_EMU = 12700
_SHAPE_ID = 2000
_DEFAULT_FONT = "Garamond"


def _next_id() -> int:
    global _SHAPE_ID
    _SHAPE_ID += 1
    return _SHAPE_ID


def _emu(pt: float) -> int:
    return int(round(pt * _PT_TO_EMU))


def _set_section(section, page: Page) -> None:
    section.page_width = Pt(page.width_pt)
    section.page_height = Pt(page.height_pt)
    section.top_margin = Pt(0)
    section.bottom_margin = Pt(0)
    section.left_margin = Pt(0)
    section.right_margin = Pt(0)


def _bbox_pt(bbox, page: Page) -> tuple[float, float, float, float]:
    left = bbox.x * page.width_pt
    top = bbox.y * page.height_pt
    width = max(8.0, bbox.w * page.width_pt)
    height = max(7.0, bbox.h * page.height_pt)
    return left, top, width, height


def _word_font(name: str | None, bold: bool) -> str:
    if not name:
        return _DEFAULT_FONT
    base = name.replace("-Bold", "").replace(",Bold", "").strip()
    if not base:
        base = _DEFAULT_FONT
    return base


def _runs_for_block(block: TextBlock) -> list[TextRun]:
    if block.runs:
        return [r for r in block.runs if r.text]
    if block.text:
        return [
            TextRun(
                text=block.text,
                font_name=block.font_name or _DEFAULT_FONT,
                font_size_pt=block.font_size_pt or 12.0,
                bold="Bold" in (block.font_name or ""),
            )
        ]
    return []


def _runs_xml(runs: list[TextRun]) -> str:
    parts: list[str] = []
    for run in runs:
        if not run.text:
            continue
        safe = html.escape(run.text, quote=False)
        font = _word_font(run.font_name, run.bold)
        size = run.font_size_pt or 12.0
        sz = max(16, min(72, int(round(size * 2))))
        bold_xml = "<w:b/>" if run.bold or "Bold" in (run.font_name or "") else ""
        parts.append(
            f"""<w:r>
              <w:rPr>
                <w:rFonts w:ascii="{font}" w:hAnsi="{font}" w:cs="{font}"/>
                <w:sz w:val="{sz}"/>
                {bold_xml}
              </w:rPr>
              <w:t xml:space="preserve">{safe}</w:t>
            </w:r>"""
        )
    return "".join(parts) if parts else "<w:r><w:t></w:t></w:r>"


def _anchor_textbox_runs_xml(
    runs: list[TextRun],
    left_pt: float,
    top_pt: float,
    width_pt: float,
    height_pt: float,
    shape_id: int,
) -> str:
    runs_body = _runs_xml(runs)
    left_e, top_e = _emu(left_pt), _emu(top_pt)
    w_e, h_e = _emu(width_pt), _emu(height_pt)
    return f"""
    <mc:AlternateContent xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006">
      <mc:Choice Requires="wps">
        <w:drawing xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
            xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
            xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape">
          <wp:anchor distT="0" distB="0" distL="0" distR="0" simplePos="0"
              relativeHeight="251658240" behindDoc="0" locked="0" layoutInCell="1" allowOverlap="1">
            <wp:simplePos x="0" y="0"/>
            <wp:positionH relativeFrom="page"><wp:posOffset>{left_e}</wp:posOffset></wp:positionH>
            <wp:positionV relativeFrom="page"><wp:posOffset>{top_e}</wp:posOffset></wp:positionV>
            <wp:extent cx="{w_e}" cy="{h_e}"/>
            <wp:effectExtent l="0" t="0" r="0" b="0"/>
            <wp:wrapNone/>
            <wp:docPr id="{shape_id}" name="NativeText {shape_id}"/>
            <wp:cNvGraphicFramePr><a:graphicFrameLocks noChangeAspect="1"/></wp:cNvGraphicFramePr>
            <a:graphic>
              <a:graphicData uri="http://schemas.microsoft.com/office/word/2010/wordprocessingShape">
                <wps:wsp>
                  <wps:cNvSpPr txBox="1"/>
                  <wps:spPr>
                    <a:xfrm><a:off x="0" y="0"/><a:ext cx="{w_e}" cy="{h_e}"/></a:xfrm>
                    <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
                    <a:noFill/>
                    <a:ln w="0"><a:noFill/></a:ln>
                  </wps:spPr>
                  <wps:txbx>
                    <w:txbxContent>
                      <w:p>
                        <w:pPr><w:spacing w:before="0" w:after="0" w:line="240" w:lineRule="auto"/></w:pPr>
                        {runs_body}
                      </w:p>
                    </w:txbxContent>
                  </wps:txbx>
                  <wps:bodyPr wrap="square" lIns="0" tIns="0" rIns="0" bIns="0"/>
                </wps:wsp>
              </a:graphicData>
            </a:graphic>
          </wp:anchor>
        </w:drawing>
      </mc:Choice>
    </mc:AlternateContent>"""


def _grid_cols(col_count: int, col_w_emu: int) -> str:
    return "".join(f'<w:gridCol w:w="{col_w_emu}"/>' for _ in range(col_count))


def _page_table_blocks(ir: DocumentIR, page_index: int) -> list[TableBlock]:
    blocks: list[TableBlock] = []
    for b in ir.blocks:
        if b.type != "table":
            continue
        if getattr(b, "page_index", -1) == page_index:
            blocks.append(b)
    blocks.sort(key=lambda x: (x.bbox.y, x.bbox.x))
    return blocks


def _table_xml(
    rows: list[list[str]],
    left_pt: float,
    top_pt: float,
    width_pt: float,
    height_pt: float,
    shape_id: int,
) -> str:
    """Positioned floating table as DrawingML textbox containing an OOXML table."""
    if not rows:
        return ""
    col_count = max(len(r) for r in rows)
    if col_count == 0:
        return ""

    col_w = max(1, int(width_pt / col_count))
    col_w_emu = _emu(col_w)

    def cell_xml(text: str) -> str:
        safe = html.escape(str(text), quote=False)
        return (
            f'<w:tc><w:tcPr>'
            f'<w:tcW w:w="{col_w_emu}" w:type="dxa"/>'
            f'<w:tcBorders>'
            f'<w:top w:val="single" w:sz="4" w:color="000000"/>'
            f'<w:bottom w:val="single" w:sz="4" w:color="000000"/>'
            f'<w:left w:val="single" w:sz="4" w:color="000000"/>'
            f'<w:right w:val="single" w:sz="4" w:color="000000"/>'
            f'</w:tcBorders>'
            f'</w:tcPr>'
            f'<w:p><w:pPr><w:spacing w:before="0" w:after="0"/></w:pPr>'
            f'<w:r><w:rPr><w:sz w:val="18"/></w:rPr>'
            f'<w:t xml:space="preserve">{safe}</w:t></w:r></w:p></w:tc>'
        )

    rows_xml = ""
    for row in rows:
        cells = "".join(cell_xml(row[ci] if ci < len(row) else "") for ci in range(col_count))
        rows_xml += f"<w:tr>{cells}</w:tr>"

    tbl_xml = (
        f'<w:tbl>'
        f'<w:tblPr>'
        f'<w:tblStyle w:val="TableGrid"/>'
        f'<w:tblW w:w="{_emu(width_pt)}" w:type="dxa"/>'
        f'<w:tblBorders>'
        f'<w:insideH w:val="single" w:sz="4" w:color="000000"/>'
        f'<w:insideV w:val="single" w:sz="4" w:color="000000"/>'
        f'</w:tblBorders>'
        f'</w:tblPr>'
        f'<w:tblGrid>{_grid_cols(col_count, col_w_emu)}</w:tblGrid>'
        f'{rows_xml}'
        f'</w:tbl>'
    )

    left_e, top_e = _emu(left_pt), _emu(top_pt)
    w_e, h_e = _emu(width_pt), _emu(max(height_pt, 20.0))

    return f"""
    <mc:AlternateContent xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006">
      <mc:Choice Requires="wps">
        <w:drawing xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
            xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
            xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape">
          <wp:anchor distT="0" distB="0" distL="0" distR="0" simplePos="0"
              relativeHeight="251658241" behindDoc="0" locked="0" layoutInCell="1" allowOverlap="1">
            <wp:simplePos x="0" y="0"/>
            <wp:positionH relativeFrom="page"><wp:posOffset>{left_e}</wp:posOffset></wp:positionH>
            <wp:positionV relativeFrom="page"><wp:posOffset>{top_e}</wp:posOffset></wp:positionV>
            <wp:extent cx="{w_e}" cy="{h_e}"/>
            <wp:effectExtent l="0" t="0" r="0" b="0"/>
            <wp:wrapNone/>
            <wp:docPr id="{shape_id}" name="Table {shape_id}"/>
            <wp:cNvGraphicFramePr><a:graphicFrameLocks noChangeAspect="1"/></wp:cNvGraphicFramePr>
            <a:graphic>
              <a:graphicData uri="http://schemas.microsoft.com/office/word/2010/wordprocessingShape">
                <wps:wsp>
                  <wps:cNvSpPr txBox="1"/>
                  <wps:spPr>
                    <a:xfrm><a:off x="0" y="0"/><a:ext cx="{w_e}" cy="{h_e}"/></a:xfrm>
                    <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
                    <a:noFill/>
                    <a:ln w="0"><a:noFill/></a:ln>
                  </wps:spPr>
                  <wps:txbx>
                    <w:txbxContent xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
                      {tbl_xml}
                    </w:txbxContent>
                  </wps:txbx>
                  <wps:bodyPr wrap="square" lIns="36000" tIns="36000" rIns="36000" bIns="36000"/>
                </wps:wsp>
              </a:graphicData>
            </a:graphic>
          </wp:anchor>
        </w:drawing>
      </mc:Choice>
    </mc:AlternateContent>"""


def _page_text_blocks(ir: DocumentIR, page_index: int) -> list[TextBlock]:
    blocks: list[TextBlock] = []
    for b in ir.blocks:
        if b.type != "text":
            continue
        if getattr(b, "page_index", -1) == page_index:
            blocks.append(b)
    blocks.sort(key=lambda x: (x.bbox.y, x.bbox.x))
    return blocks


def emit_docx_native_fidelity(
    ir: DocumentIR,
    output_path: Path,
    *,
    page_backgrounds: list[Path],
    mask_dir: Path | None = None,
    dpi: int = 200,
) -> Path:
    """Masked page raster (borders, logo) + PDF-positioned editable text with native fonts."""
    global _SHAPE_ID
    _SHAPE_ID = 2000

    doc = Document()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    work_mask = mask_dir or output_path.parent / "masked_assets"
    work_mask.mkdir(parents=True, exist_ok=True)

    pages = ir.pages or [Page(index=i) for i in range(ir.source.page_count)]
    page_count = ir.source.page_count

    for pi in range(page_count):
        page = pages[pi] if pi < len(pages) else Page(index=pi)
        if pi > 0:
            doc.add_section()
        _set_section(doc.sections[-1], page)

        bg = page_backgrounds[pi] if pi < len(page_backgrounds) else None
        page_texts = _page_text_blocks(ir, pi)
        page_tables = _page_table_blocks(ir, pi)

        if bg and bg.exists() and page_texts:
            masked = work_mask / f"native_page_{pi:03d}.png"
            bg_use = mask_page_background(bg, page_texts, masked, pad=0.002)
        else:
            bg_use = bg

        para = doc.add_paragraph()
        pf = para.paragraph_format
        pf.space_before = Pt(0)
        pf.space_after = Pt(0)
        pf.line_spacing_rule = WD_LINE_SPACING.EXACTLY
        pf.line_spacing = Pt(0.1)

        run = para.add_run()
        if bg_use and Path(bg_use).exists():
            run.add_picture(str(bg_use), width=Pt(page.width_pt), height=Pt(page.height_pt))

        for block in page_texts:
            runs = _runs_for_block(block)
            if not runs:
                continue
            left, top, width, height = _bbox_pt(block.bbox, page)
            run._r.append(
                parse_xml(
                    _anchor_textbox_runs_xml(runs, left, top, width, height, _next_id())
                )
            )

        for tblock in page_tables:
            if not tblock.rows:
                continue
            left, top, width, height = _bbox_pt(tblock.bbox, page)
            xml = _table_xml(tblock.rows, left, top, width, height, _next_id())
            if xml:
                run._r.append(parse_xml(xml))

        # Raster logos and line art remain in the masked background layer.

    doc.save(output_path)
    return output_path
