"""Font size estimation from layout bbox (scanned documents)."""

from __future__ import annotations

from src.pipeline.ir import Bbox, Page

DEFAULT_FONT_NAME = "Times New Roman"
MIN_FONT_PT = 8.0
MAX_FONT_PT = 36.0


def estimate_font_size_pt(bbox: Bbox, page: Page, text: str = "") -> float:
    """Estimate point size from bbox height and line count (capped for Word)."""
    line_count = max(1, text.count("\n") + 1)
    if text:
        # Rough wrap estimate for Cyrillic legal text
        chars_per_line = max(20, int(bbox.w * page.width_pt / 6))
        line_count = max(line_count, (len(text) + chars_per_line - 1) // chars_per_line)

    height_pt = max(6.0, bbox.h * page.height_pt)
    per_line = height_pt / line_count
    size = per_line * 0.75
    return max(MIN_FONT_PT, min(MAX_FONT_PT, round(size, 1)))
