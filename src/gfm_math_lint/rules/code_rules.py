"""GFM Code Block and Inline Code Span rules (GFM-C01, GFM-C02, GFM-C03)."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from gfm_math_lint.fixer import LintEdit
from gfm_math_lint.rules.base import Rule, Violation
from gfm_math_lint.tokenizer import DocumentZone, Zone, scan_inline_spans

if TYPE_CHECKING:
    from collections.abc import Sequence

FENCE_INNER_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
FENCE_LINE_RE = re.compile(r"^( {0,3})(`{3,}|~{3,})(.*)$")
NESTED_MATH_SPAN_RE = re.compile(r"(?<!`)`(\$`[^`*\s][^`*\n]*[^`*\s]`\$)`(?!`)")
NESTED_FENCE_SPAN_RE = re.compile(r"(?<!`)`( {1,3}`{3,}[^`]*?)`(?!`)")
BACKTICK_RUN_RE = re.compile(r"`+")

_PLAIN_FENCE_INFO: frozenset[str] = frozenset({"", "text", "plaintext", "txt"})
_TREE_LISTING_RE = re.compile(r"[\u251c\u2514]\u2500\u2500")
_BOX_ARROW_RE = re.compile(r"(?:[\u25ba\u25c4\u25b2\u25bc\u2192\u2190\u2191\u2193]|->|<-|==>)")
_ASCII_BOX_BORDER_RE = re.compile(r"\+-{3,}\+")
_ASCII_BOX_PIPE_RE = re.compile(r"\|[^|\n]+\|")
_EQ_REL_RE = re.compile(r"(?:=|[\u2248\u2264\u2265\u2261])")
_UNICODE_MATH_GLYPH_RE = re.compile(
    r"[\u0391-\u03a9\u03b1-\u03c9\u2202\u2207\u2211\u220f\u221a\u222b\u00b1\u00b7\u2212\u00b2\u00b3\u00b9\u00bd\u00bc\u00be]"
)
_DIFF_RATIO_RE = re.compile(r"\bd[A-Za-z_]\w*/d[A-Za-z_]\w*\b")
_RAW_LATEX_CMD_RE = re.compile(
    r"\\(?:frac|sqrt|sum|int|partial|alpha|beta|gamma|delta|Delta|Sigma|omega|begin|mathrm|text)\b"
)
_BQ_PREFIX_RE = re.compile(r"^\s*(?:>\s*)+")


class RuleC01(Rule):
    """GFM-C01: Code Block Fence Nesting Length (N_outer > N_inner)."""

    id: str = "GFM-C01"
    name: str = "fence-nesting-length"
    description: str = "Enforce that outer code fence length is strictly greater than any enclosed inner fence"
    severity: str = "error"

    def check(self, lines: Sequence[str], zones: list[DocumentZone], file_path: str = "") -> list[Violation]:
        violations: list[Violation] = []

        for zone in zones:
            if zone.zone_type != Zone.FENCED_CODE or not zone.is_closed or len(zone.lines) < 2 or zone.fence_len < 3:
                continue

            outer_char = zone.fence_char
            outer_len = zone.fence_len
            max_inner_len = 0

            # Scan inner lines for fences using the same character
            for inner_line in zone.lines[1:-1]:
                m = FENCE_INNER_RE.match(inner_line)
                if m and m.group(1)[0] == outer_char:
                    inner_len = len(m.group(1))
                    if inner_len > max_inner_len:
                        max_inner_len = inner_len

            if max_inner_len >= outer_len:
                needed_len = max_inner_len + 1
                # Auto-fix: lengthen opening fence and closing fence
                # Opening fence
                open_line = zone.lines[0]
                m_open = FENCE_LINE_RE.match(open_line)
                if m_open:
                    indent, _, rest = m_open.groups()
                    new_open = f"{indent}{outer_char * needed_len}{rest}"
                    if not new_open.endswith("\n"):
                        new_open += "\n"

                    # Closing fence
                    close_line = zone.lines[-1]
                    m_close = FENCE_LINE_RE.match(close_line)
                    close_indent = m_close.group(1) if m_close else ""
                    close_rest = m_close.group(3) if m_close else "\n"
                    new_close = f"{close_indent}{outer_char * needed_len}{close_rest}"
                    if not new_close.endswith("\n"):
                        new_close += "\n"

                    # Replace entire zone from start_line to end_line
                    new_content = new_open + "".join(zone.lines[1:-1]) + new_close
                    last_line_len = len(zone.lines[-1])

                    edit = LintEdit(
                        rule_id=self.id,
                        start_line=zone.start_line,
                        start_col=1,
                        end_line=zone.end_line,
                        end_col=last_line_len + 1,
                        replacement=new_content,
                    )
                    violations.append(
                        Violation(
                            rule_id=self.id,
                            message=(
                                f"Outer code fence length ({outer_len}) must be strictly greater than "
                                f"inner fence length ({max_inner_len}). Lengthen to {needed_len} backticks."
                            ),
                            line=zone.start_line,
                            col=1,
                            severity=self.severity,
                            edit=edit,
                        )
                    )

        return violations


class RuleC02(Rule):
    """GFM-C02: Inline Code Span Backtick Nesting."""

    id: str = "GFM-C02"
    name: str = "inline-code-backtick-nesting"
    description: str = "Inline code spans containing backticks must use multi-backtick delimiters per CommonMark §6.3"
    severity: str = "error"

    def check(self, lines: Sequence[str], zones: list[DocumentZone], file_path: str = "") -> list[Violation]:
        violations: list[Violation] = []

        for zone in zones:
            if zone.zone_type in (Zone.PROSE, Zone.TABLE):
                for line_idx, line in enumerate(zone.lines):
                    line_no = zone.start_line + line_idx
                    handled_cols: set[int] = set()

                    spans = scan_inline_spans(line, line_no)
                    multi_bt_spans = [s for s in spans if s.zone_type == Zone.INLINE_CODE and len(s.delimiter) >= 2]

                    # Search for single-backtick spans wrapping backticks or math
                    # E.g. (`$`\text{shift}`$`) or (` ```math `)
                    # Pattern 1: (`$`...`$`) -> (``$`...`$``)
                    for m in NESTED_MATH_SPAN_RE.finditer(line):
                        col_start = m.start() + 1
                        if any(s.start_col <= col_start <= s.end_col for s in multi_bt_spans):
                            continue
                        col_end = m.end() + 1
                        handled_cols.add(col_start)
                        inner = m.group(1)
                        replacement = f"``{inner}``"
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
                                message="Inline code span containing backticks must use double backticks (`` ... ``).",
                                line=line_no,
                                col=col_start,
                                severity=self.severity,
                                edit=edit,
                            )
                        )

                    # Pattern 2: (` ```math `) -> (`` ```math ``)
                    for m in NESTED_FENCE_SPAN_RE.finditer(line):
                        col_start = m.start() + 1
                        if any(s.start_col <= col_start <= s.end_col for s in multi_bt_spans):
                            continue
                        col_end = m.end() + 1
                        handled_cols.add(col_start)
                        inner = m.group(1)
                        # Ensure space padding per CommonMark §6.3
                        replacement = f"`` {inner.strip()} ``"
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
                                message=("Inline code span containing code fence backticks must use double backticks."),
                                line=line_no,
                                col=col_start,
                                severity=self.severity,
                                edit=edit,
                            )
                        )

        return violations


def _is_ascii_box_diagram(text: str) -> bool:
    """Return True if `text` looks like a 2D ASCII/Unicode box-drawing diagram (excluding file trees)."""
    has_unicode_top = (
        ("\u250c" in text and "\u2510" in text)
        or ("\u2554" in text and "\u2557" in text)
        or ("\u256d" in text and "\u256e" in text)
    )
    has_unicode_bottom = (
        ("\u2514" in text and "\u2518" in text)
        or ("\u255a" in text and "\u255d" in text)
        or ("\u2570" in text and "\u256f" in text)
    )
    ascii_borders = len(_ASCII_BOX_BORDER_RE.findall(text))
    has_ascii_box = ascii_borders >= 1 and bool(_ASCII_BOX_PIPE_RE.search(text))

    if _TREE_LISTING_RE.search(text) and not (has_unicode_top or has_ascii_box):
        return False

    has_flow = bool(_BOX_ARROW_RE.search(text))
    if has_unicode_top and (has_unicode_bottom or has_flow):
        return True
    return has_ascii_box and (ascii_borders >= 2 or has_flow)


def _has_unrendered_math(lines: Sequence[str]) -> bool:
    """Return True if plain-text fence lines contain mathematical equations or LaTeX macros."""
    for ln in lines:
        if "gfm-math-lint" in ln:
            continue
        if _RAW_LATEX_CMD_RE.search(ln):
            return True
        if _EQ_REL_RE.search(ln) and (_UNICODE_MATH_GLYPH_RE.search(ln) or _DIFF_RATIO_RE.search(ln)):
            return True
    return False


class RuleC03(Rule):
    """GFM-C03: Unrendered Math or 2D ASCII Box Diagram Inside Plain-Text Code Fence."""

    id: str = "GFM-C03"
    name: str = "unrendered-math-or-diagram-fence"
    description: str = "Detect mathematical equations or 2D ASCII box-drawing diagrams inside plain-text code fences"
    severity: str = "warning"

    def check(self, lines: Sequence[str], zones: list[DocumentZone], file_path: str = "") -> list[Violation]:
        violations: list[Violation] = []

        for zone in zones:
            if zone.zone_type != Zone.FENCED_CODE or not zone.is_closed or zone.fence_len < 3:
                continue
            if zone.info.strip().lower() not in _PLAIN_FENCE_INFO:
                continue

            inner_lines = zone.lines[1:-1] if len(zone.lines) >= 2 else []
            if not inner_lines:
                continue

            cleaned = [
                _BQ_PREFIX_RE.sub("", ln) if (zone.parent_block == "blockquote" or ln.lstrip().startswith(">")) else ln
                for ln in inner_lines
            ]
            body = "".join(cleaned)

            if _is_ascii_box_diagram(body):
                violations.append(
                    Violation(
                        rule_id=self.id,
                        message=(
                            "Plain-text code fence contains a 2D ASCII box-drawing diagram. "
                            "Convert to a '```mermaid' diagram or suppress with "
                            "'<!-- gfm-math-lint-disable GFM-C03 -->'."
                        ),
                        line=zone.start_line,
                        col=1,
                        severity=self.severity,
                        edit=None,
                    )
                )
            elif _has_unrendered_math(cleaned):
                violations.append(
                    Violation(
                        rule_id=self.id,
                        message=(
                            "Plain-text code fence contains unrendered mathematical equations. "
                            "Convert to '$$ ... $$' display math or suppress with "
                            "'<!-- gfm-math-lint-disable GFM-C03 -->'."
                        ),
                        line=zone.start_line,
                        col=1,
                        severity=self.severity,
                        edit=None,
                    )
                )

        return violations
