"""GFM Code Block and Inline Code Span rules (GFM-C01, GFM-C02)."""

from __future__ import annotations

import re

from gfm_math_lint.fixer import LintEdit
from gfm_math_lint.rules.base import Rule, Violation
from gfm_math_lint.tokenizer import DocumentZone, Zone, scan_inline_spans

FENCE_INNER_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
FENCE_LINE_RE = re.compile(r"^( {0,3})(`{3,}|~{3,})(.*)$")
NESTED_MATH_SPAN_RE = re.compile(r"(?<!`)`(\$`[^`*\s][^`*\n]*[^`*\s]`\$)`(?!`)")
NESTED_FENCE_SPAN_RE = re.compile(r"(?<!`)`( {1,3}`{3,}[^`]*?)`(?!`)")
BACKTICK_RUN_RE = re.compile(r"`+")


class RuleC01(Rule):
    """GFM-C01: Code Block Fence Nesting Length (N_outer > N_inner)."""

    id: str = "GFM-C01"
    name: str = "fence-nesting-length"
    description: str = "Enforce that outer code fence length is strictly greater than any enclosed inner fence"
    severity: str = "error"

    def check(self, lines: list[str], zones: list[DocumentZone], file_path: str = "") -> list[Violation]:
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

    def check(self, lines: list[str], zones: list[DocumentZone], file_path: str = "") -> list[Violation]:
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
