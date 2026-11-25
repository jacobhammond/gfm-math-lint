"""Local KaTeX AST verification oracle using host node/katex runtime."""

from __future__ import annotations

from dataclasses import dataclass, field

from gfm_math_lint.latex import (
    _get_node_env,
    is_katex_available,
)
from gfm_math_lint.latex import (
    run_local_katex_verification as _run_katex_strict,
)


@dataclass(frozen=True)
class KaTeXParseError:
    """Represents a KaTeX parser exception or strict warning with context."""

    math_content: str
    display_mode: bool
    error_message: str
    warnings: list[str] = field(default_factory=list)


def run_local_katex_verification(
    math_blocks: list[tuple[str, bool]],
    strict_warnings: bool = False,
) -> list[KaTeXParseError]:
    """Validate a list of (math_content, is_display) tuples against KaTeX.

    Returns a list of parse errors (and strict warnings when `strict_warnings=True`).
    Returns empty list if KaTeX is unavailable.
    """
    diagnostics = _run_katex_strict(math_blocks, strict_warnings=strict_warnings)
    return [
        KaTeXParseError(
            math_content=d.math_content,
            display_mode=d.display_mode,
            error_message=d.error_message,
            warnings=d.warnings,
        )
        for d in diagnostics
    ]


__all__ = [
    "KaTeXParseError",
    "_get_node_env",
    "is_katex_available",
    "run_local_katex_verification",
]
