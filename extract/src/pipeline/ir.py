"""DocumentIR v1 — intermediate representation between analysis and emitters."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Literal, Union
from uuid import uuid4

from pydantic import BaseModel, Field

SCHEMA_VERSION = "document-ir-v1"


class Bbox(BaseModel):
    x: float = 0.0
    y: float = 0.0
    w: float = 1.0
    h: float = 1.0


class Page(BaseModel):
    index: int
    width_pt: float = 595.0
    height_pt: float = 842.0
    background_image: str = ""


class SourceInfo(BaseModel):
    filename: str = "input.pdf"
    page_count: int = 0
    languages: list[str] = Field(default_factory=lambda: ["ru", "en"])


class MetaInfo(BaseModel):
    engine: str = "docling"
    engine_version: str = "unknown"
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    warnings: list[str] = Field(default_factory=list)


class TextRun(BaseModel):
    text: str = ""
    font_name: str | None = None
    font_size_pt: float | None = None
    bold: bool = False


class TextBlock(BaseModel):
    type: Literal["text"] = "text"
    id: str = Field(default_factory=lambda: f"b-{uuid4().hex[:8]}")
    page_index: int = 0
    bbox: Bbox = Field(default_factory=Bbox)
    text: str = ""
    role: Literal[
        "title",
        "heading",
        "paragraph",
        "list_item",
        "caption",
        "footer",
        "header",
        "unknown",
    ] = "paragraph"
    confidence: float = 1.0
    font_size_pt: float | None = None
    font_name: str | None = None
    runs: list[TextRun] = Field(default_factory=list)


class TableBlock(BaseModel):
    type: Literal["table"] = "table"
    id: str = Field(default_factory=lambda: f"b-{uuid4().hex[:8]}")
    page_index: int = 0
    bbox: Bbox = Field(default_factory=Bbox)
    rows: list[list[str | None]] = Field(default_factory=list)
    confidence: float = 1.0
    col_widths_pt: list[float] = Field(default_factory=list)
    cell_runs: list[list[list["TextRun"]]] = Field(default_factory=list)
    cell_aligns: list[list[str]] = Field(default_factory=list)


class ImageBlock(BaseModel):
    type: Literal["image"] = "image"
    id: str = Field(default_factory=lambda: f"b-{uuid4().hex[:8]}")
    page_index: int = 0
    bbox: Bbox = Field(default_factory=Bbox)
    image_path: str = ""
    caption: str = ""
    confidence: float = 1.0


class PageBreakBlock(BaseModel):
    type: Literal["page_break"] = "page_break"
    id: str = Field(default_factory=lambda: f"b-{uuid4().hex[:8]}")
    page_index: int = 0


Block = Annotated[
    Union[TextBlock, TableBlock, ImageBlock, PageBreakBlock],
    Field(discriminator="type"),
]


class DocumentIR(BaseModel):
    schema_version: str = SCHEMA_VERSION
    source: SourceInfo = Field(default_factory=SourceInfo)
    pages: list[Page] = Field(default_factory=list)
    blocks: list[
        Union[TextBlock, TableBlock, ImageBlock, PageBreakBlock]
    ] = Field(default_factory=list)
    meta: MetaInfo = Field(default_factory=MetaInfo)
