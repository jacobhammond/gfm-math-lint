"""gfm-math-lint package.

Linter and auto-fixer for GitHub-Flavored Markdown math (MathJax), tables, code fences, and Mermaid.
"""

from __future__ import annotations

from importlib import metadata
from typing import TYPE_CHECKING, Any

from gfm_math_lint.config import LintConfig, load_config
from gfm_math_lint.linter import Linter, LintResult, SpanDiffTelemetry
from gfm_math_lint.rules.base import Rule, Violation

if TYPE_CHECKING:
    from gfm_math_lint.latex import LaTeXIssue, validate_latex
    from gfm_math_lint.probe import ProbeReport, run_probes
    from gfm_math_lint.verifier import (
        VerificationIssue,
        VerificationReport,
        build_preview_html,
        verify_file,
        verify_file_detailed,
        verify_markdown,
        verify_markdown_detailed,
    )

try:
    __version__ = metadata.version("gfm-math-lint")
except metadata.PackageNotFoundError:
    __version__ = "0.4.0"

__all__: list[str] = [
    "LaTeXIssue",
    "LintConfig",
    "LintResult",
    "Linter",
    "ProbeReport",
    "Rule",
    "SpanDiffTelemetry",
    "VerificationIssue",
    "VerificationReport",
    "Violation",
    "__version__",
    "build_preview_html",
    "load_config",
    "run_probes",
    "validate_latex",
    "verify_file",
    "verify_file_detailed",
    "verify_markdown",
    "verify_markdown_detailed",
]

_LAZY_EXPORTS = {
    "LaTeXIssue": "gfm_math_lint.latex",
    "ProbeReport": "gfm_math_lint.probe",
    "VerificationIssue": "gfm_math_lint.verifier",
    "VerificationReport": "gfm_math_lint.verifier",
    "build_preview_html": "gfm_math_lint.verifier",
    "run_probes": "gfm_math_lint.probe",
    "validate_latex": "gfm_math_lint.latex",
    "verify_file": "gfm_math_lint.verifier",
    "verify_file_detailed": "gfm_math_lint.verifier",
    "verify_markdown": "gfm_math_lint.verifier",
    "verify_markdown_detailed": "gfm_math_lint.verifier",
}


def __getattr__(name: str) -> Any:
    if name in _LAZY_EXPORTS:
        import importlib

        mod = importlib.import_module(_LAZY_EXPORTS[name])
        val = getattr(mod, name)
        globals()[name] = val
        return val
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
