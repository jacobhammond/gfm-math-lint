"""GFM Shell Argument Scanner rules (GFM-S01)."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from gfm_math_lint.rules.base import Rule, Violation

if TYPE_CHECKING:
    from gfm_math_lint.tokenizer import DocumentZone

GH_CALL_PATTERN = re.compile(
    r"\bgh\s+(?:pr\s+comment|issue\s+comment|release\s+create)\b.*?(?:-b|--body|--notes)(?:=|\s+)\"((?:\\\"|[^\"])*?)\""
)
BODY_EXPANSION_PATTERN = re.compile(r"\$[a-zA-Z_]|\$\{|\$\(")


class RuleS01(Rule):
    """GFM-S01: Unsafe Shell Argument Scanner."""

    id: str = "GFM-S01"
    name: str = "unsafe-shell-expansion"
    description: str = "Scan shell scripts and workflows for unsafe double-quoted body arguments in gh CLI calls"
    severity: str = "error"

    def check(self, lines: list[str], zones: list[DocumentZone], file_path: str = "") -> list[Violation]:
        violations: list[Violation] = []

        # Assemble logical lines by combining backslash continuations
        logical_lines: list[tuple[int, int, str]] = []
        idx = 0
        total = len(lines)
        while idx < total:
            start_line = idx + 1
            cmd_parts = []
            while idx < total:
                raw = lines[idx]
                idx += 1
                stripped_end = raw.rstrip("\r\n")
                if stripped_end.endswith("\\"):
                    cmd_parts.append(stripped_end[:-1] + " ")
                else:
                    cmd_parts.append(raw)
                    break
            logical_cmd = "".join(cmd_parts)
            logical_lines.append((start_line, 1, logical_cmd))

        for start_line, _start_col, cmd_text in logical_lines:
            for m in GH_CALL_PATTERN.finditer(cmd_text):
                body_arg = m.group(1)
                # Check if body argument contains $var or $(...)
                if BODY_EXPANSION_PATTERN.search(body_arg):
                    col_no = m.start() + 1
                    violations.append(
                        Violation(
                            rule_id=self.id,
                            message=(
                                "Unsafe double-quoted body argument in 'gh' command. Shell parameter expansion ($var) "
                                "or command substitution ($(..)) causes equation loss. Use '--body-file -' with "
                                "single-quoted HEREDOC: 'cat << \\'EOF\\''."
                            ),
                            line=start_line,
                            col=col_no,
                            severity=self.severity,
                        )
                    )

        return violations
