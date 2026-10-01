"""Base definitions for linting rules and violations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from gfm_math_lint.fixer import LintEdit
    from gfm_math_lint.tokenizer import DocumentZone


@dataclass(frozen=True)
class Violation:
    """Diagnostic violation record."""

    rule_id: str
    message: str
    line: int  # 1-indexed
    col: int  # 1-indexed
    severity: str = "error"  # "error" | "warning"
    edit: LintEdit | None = None


class Rule(Protocol):
    """Protocol defining a linting rule."""

    id: str
    name: str
    description: str
    severity: str

    def check(self, lines: list[str], zones: list[DocumentZone], file_path: str = "") -> list[Violation]:
        """Execute rule checks against the tokenized document."""
        ...
