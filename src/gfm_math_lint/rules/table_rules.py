"""GFM Table rules (GFM-T01)."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from gfm_math_lint.fixer import LintEdit
from gfm_math_lint.rules.base import Rule, Violation
from gfm_math_lint.tokenizer import DocumentZone, Zone, is_escaped, scan_inline_spans

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

RAW_PIPE_RE = re.compile(r"\|")
_HTML_PIPE_ENTITY = r"(?:&#124;|&#x7c;|&verbar;|&vert;)"
MATH_PIPE_DETECT_RE = re.compile(rf"\\?\||{_HTML_PIPE_ENTITY}", re.IGNORECASE)
PAIRED_ESCAPED_NORM_RE = re.compile(r"(?<!\\)\\\|(.+?)(?<!\\)\\\|")
PAIRED_DOUBLE_PIPE_RE = re.compile(r"\|\|(.+?)\|\|")
PAIRED_DOUBLE_ENTITY_RE = re.compile(
    rf"{_HTML_PIPE_ENTITY}{{2}}(.+?){_HTML_PIPE_ENTITY}{{2}}",
    re.IGNORECASE,
)
PAIRED_SINGLE_ENTITY_RE = re.compile(
    rf"{_HTML_PIPE_ENTITY}(.+?){_HTML_PIPE_ENTITY}",
    re.IGNORECASE,
)
PAIRED_SINGLE_PIPE_RE = re.compile(r"(?<!\\)\|([^|]+?)(?<!\\)\|")
UNPAIRED_PIPE_OR_ENTITY_RE = re.compile(
    rf"(?:(?<!\\)\\\||\|)|{_HTML_PIPE_ENTITY}",
    re.IGNORECASE,
)


def _following_space(text: str, end_idx: int) -> str:
    """Return a single space if the next char is an ASCII letter, to avoid fusing TeX macros."""
    if end_idx < len(text) and text[end_idx].isascii() and text[end_idx].isalpha():
        return " "
    return ""


def _replace_paired_delims(left: str, right: str) -> Callable[[re.Match[str]], str]:
    def _repl(match: re.Match[str]) -> str:
        inner = match.group(1).strip()
        tail = _following_space(match.string, match.end())
        return f"{left} {inner}{right}{tail}"

    return _repl


def _replace_unpaired_pipe(match: re.Match[str]) -> str:
    tail = _following_space(match.string, match.end())
    return f"\\vert{tail}"


def _convert_math_pipes(content: str) -> str:
    """Convert raw pipes and HTML pipe entities inside table math spans to LaTeX macros."""
    updated = PAIRED_ESCAPED_NORM_RE.sub(_replace_paired_delims(r"\lVert", r"\rVert"), content)
    updated = PAIRED_DOUBLE_PIPE_RE.sub(_replace_paired_delims(r"\lVert", r"\rVert"), updated)
    updated = PAIRED_DOUBLE_ENTITY_RE.sub(_replace_paired_delims(r"\lVert", r"\rVert"), updated)
    updated = PAIRED_SINGLE_ENTITY_RE.sub(_replace_paired_delims(r"\lvert", r"\rvert"), updated)
    updated = PAIRED_SINGLE_PIPE_RE.sub(_replace_paired_delims(r"\lvert", r"\rvert"), updated)
    updated = UNPAIRED_PIPE_OR_ENTITY_RE.sub(_replace_unpaired_pipe, updated)
    return updated


class RuleT01(Rule):
    """GFM-T01: Table Math & Code Pipe Collision."""

    id: str = "GFM-T01"
    name: str = "table-pipe-collision"
    description: str = (
        "Replace raw pipes and HTML pipe entities in table math spans with LaTeX delimiter macros "
        "and escape pipes in table code spans"
    )
    severity: str = "error"

    def check(self, lines: Sequence[str], zones: list[DocumentZone], file_path: str = "") -> list[Violation]:
        violations: list[Violation] = []

        for zone in zones:
            if zone.zone_type != Zone.TABLE:
                continue

            for line_idx, line in enumerate(zone.lines):
                line_no = zone.start_line + line_idx
                # We scan for inline spans in this table row
                spans = scan_inline_spans(line, line_no)

                for span in spans:
                    if span.zone_type in (Zone.INLINE_MATH, Zone.DISPLAY_MATH):
                        if MATH_PIPE_DETECT_RE.search(span.content) is None:
                            continue
                        replacement = _convert_math_pipes(span.content)
                        col_start = span.start_col + len(span.delimiter)
                        col_end = span.end_col - len(span.delimiter)
                        edit = LintEdit(
                            rule_id=self.id,
                            start_line=line_no,
                            start_col=col_start,
                            end_line=line_no,
                            end_col=col_end,
                            replacement=replacement,
                        )
                        violations.append(
                            Violation(
                                rule_id=self.id,
                                message=(
                                    "Raw pipe '|' or HTML pipe entity inside table math span fractures table columns "
                                    "or breaks GitHub MathJax. Use LaTeX delimiter macros "
                                    "('\\lvert ... \\rvert', '\\lVert ... \\rVert', '\\mid', or '\\vert') instead."
                                ),
                                line=line_no,
                                col=col_start,
                                severity=self.severity,
                                edit=edit,
                            )
                        )

                    elif span.zone_type == Zone.INLINE_CODE:
                        # Find unescaped pipes in code spans in table cells
                        # Replace unescaped | with \|
                        for m in RAW_PIPE_RE.finditer(span.content):
                            if is_escaped(span.content, m.start()):
                                continue
                            col_start = span.start_col + len(span.delimiter) + m.start()
                            col_end = col_start + 1
                            edit = LintEdit(
                                rule_id=self.id,
                                start_line=line_no,
                                start_col=col_start,
                                end_line=line_no,
                                end_col=col_end,
                                replacement="\\|",
                            )
                            violations.append(
                                Violation(
                                    rule_id=self.id,
                                    message=(
                                        "Raw pipe '|' inside table code span fractures table columns. Escape as '\\|'."
                                    ),
                                    line=line_no,
                                    col=col_start,
                                    severity=self.severity,
                                    edit=edit,
                                )
                            )

        return violations
