"""gfm-math-lint package.

Linter and auto-fixer for GitHub-Flavored Markdown math (MathJax), tables, code fences, and Mermaid.
"""

from __future__ import annotations

from importlib import metadata
from typing import Any

from gfm_math_lint.config import LintConfig, load_config
from gfm_math_lint.linter import Linter, LintResult
from gfm_math_lint.rules.base import Rule, Violation

try:
    __version__ = metadata.version("gfm-math-lint")
except metadata.PackageNotFoundError:
    __version__ = "0.1.1"

__all__: list[str] = [
    "LintConfig",
    "LintResult",
    "Linter",
    "Rule",
    "Violation",
    "__version__",
    "load_config",
]

_LAZY_EXPORTS = {
    "VerificationIssue": "gfm_math_lint.verifier",
    "build_preview_html": "gfm_math_lint.verifier",
    "verify_file": "gfm_math_lint.verifier",
    "verify_markdown": "gfm_math_lint.verifier",
}


def __getattr__(name: str) -> Any:
    if name in _LAZY_EXPORTS:
        import importlib

        mod = importlib.import_module(_LAZY_EXPORTS[name])
        val = getattr(mod, name)
        globals()[name] = val
        return val
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
