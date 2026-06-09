"""Layout validation errors."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PageValidation:
    page_index: int
    passed: bool
    layout_iou: float  # ink coverage ratio for page
    message: str = ""


@dataclass
class LayoutValidationResult:
    passed: bool
    pages: list[PageValidation] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    min_required_iou: float = 0.98
    font_note: str = ""

    def summary(self) -> str:
        lines = [
            f"Layout validation: {'PASSED' if self.passed else 'FAILED'}",
            f"Required ink coverage: {self.min_required_iou:.0%}",
            self.font_note,
        ]
        for p in self.pages:
            status = "OK" if p.passed else "FAIL"
            lines.append(
                f"  Page {p.page_index + 1}: {status} coverage={p.layout_iou:.1%} {p.message}"
            )
        for f in self.failures:
            lines.append(f"  ! {f}")
        return "\n".join(lines)


class LayoutValidationError(Exception):
    def __init__(self, result: LayoutValidationResult) -> None:
        self.result = result
        super().__init__(result.summary())
