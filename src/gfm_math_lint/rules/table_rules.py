"""GFM Table rules (GFM-T01)."""

from __future__ import annotations

import re

from gfm_math_lint.fixer import LintEdit
from gfm_math_lint.rules.base import Rule, Violation
from gfm_math_lint.tokenizer import DocumentZone, Zone, is_escaped, scan_inline_spans

RAW_PIPE_RE = re.compile(r"\|")


class RuleT01(Rule):
    """GFM-T01: Table Math & Code Pipe Collision."""

    id: str = "GFM-T01"
    name: str = "table-pipe-collision"
    description: str = "Escape raw pipes in table math spans (&#124;) and code spans (\\|) to prevent column fracturing"
    severity: str = "error"

    def check(self, lines: list[str], zones: list[DocumentZone], file_path: str = "") -> list[Violation]:
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
                        # Find raw pipes in math content
                        # Replace raw | with &#124;
                        for m in RAW_PIPE_RE.finditer(span.content):
                            col_start = span.start_col + len(span.delimiter) + m.start()
                            col_end = col_start + 1
                            edit = LintEdit(
                                rule_id=self.id,
                                start_line=line_no,
                                start_col=col_start,
                                end_line=line_no,
                                end_col=col_end,
                                replacement="&#124;",
                            )
                            violations.append(
                                Violation(
                                    rule_id=self.id,
                                    message=(
                                        "Raw pipe '|' inside table math span fractures table columns. "
                                        "Use '&#124;' instead."
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
