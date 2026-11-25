"""Base definitions for linting rules and violations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Sequence

    from gfm_math_lint.fixer import LintEdit
    from gfm_math_lint.tokenizer import DocumentZone


SAFE_SUBSET_DOCS_URL = "https://github.com/jacobhammond/gfm-math-lint/blob/main/docs/safe-subset-cheatsheet.md"

_RULE_CHEATSHEET_ANCHORS: dict[str, str] = {
    "GFM-M05": "#letter-named-macros",
    "GFM-M06": "#letter-named-macros",
    "GFM-M07": "#letter-named-macros",
    "GFM-M08": "#letter-named-macros",
    "GFM-M09": "#letter-named-macros",
    "GFM-M15": "#letter-named-macros",
    "GFM-M18": "#letter-named-macros",
    "GFM-M01": "#display-math-structure",
    "GFM-M02": "#display-math-structure",
    "GFM-M11": "#display-math-structure",
    "GFM-M16": "#display-math-structure",
    "GFM-M17": "#display-math-structure",
    "GFM-M03": "#inline-math-and-tables",
    "GFM-M04": "#inline-math-and-tables",
    "GFM-M10": "#inline-math-and-tables",
    "GFM-M12": "#inline-math-and-tables",
    "GFM-M13": "#inline-math-and-tables",
    "GFM-M14": "#inline-math-and-tables",
    "GFM-T01": "#inline-math-and-tables",
    "GFM-D01": "#mermaid-diagrams",
    "GFM-D02": "#mermaid-diagrams",
    "GFM-D03": "#mermaid-diagrams",
    "GFM-D04": "#mermaid-diagrams",
    "GFM-D05": "#mermaid-diagrams",
    "GFM-D06": "#mermaid-diagrams",
    "GFM-C01": "#code-fences-and-shell",
    "GFM-C02": "#code-fences-and-shell",
    "GFM-C03": "#code-fences-and-shell",
    "GFM-S01": "#code-fences-and-shell",
    "GFM-E01": "#github-probe-ground-truth",
}


def get_safe_subset_url(rule_id: str | None = None) -> str:
    """Return the Safe Subset Cheat Sheet URL (with section anchor for known rule IDs)."""
    if not rule_id:
        return SAFE_SUBSET_DOCS_URL
    anchor = _RULE_CHEATSHEET_ANCHORS.get(rule_id.upper(), "")
    return f"{SAFE_SUBSET_DOCS_URL}{anchor}"


def get_verification_docs_url(category: str | None = None) -> str:
    """Return the Safe Subset Cheat Sheet URL for a `VerificationIssue.category`."""
    if not category:
        return SAFE_SUBSET_DOCS_URL
    cat = category.lower()
    if cat.startswith("span-"):
        return f"{SAFE_SUBSET_DOCS_URL}#github-probe-ground-truth"
    if cat.startswith("mermaid-"):
        return f"{SAFE_SUBSET_DOCS_URL}#mermaid-diagrams"
    if cat.startswith("table-"):
        return f"{SAFE_SUBSET_DOCS_URL}#inline-math-and-tables"
    if cat.startswith(("katex-", "latex-", "unrendered-", "tag-")):
        return f"{SAFE_SUBSET_DOCS_URL}#letter-named-macros"
    return SAFE_SUBSET_DOCS_URL


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

    def check(self, lines: Sequence[str], zones: list[DocumentZone], file_path: str = "") -> list[Violation]:
        """Execute rule checks against the tokenized document."""
        ...
