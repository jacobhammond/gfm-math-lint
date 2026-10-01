"""Reverse-offset edit algebra and diff generator for gfm-math-lint."""

from __future__ import annotations

import difflib
from dataclasses import dataclass


@dataclass(frozen=True)
class LintEdit:
    """Atomic edit record with 1-indexed coordinates."""

    rule_id: str
    start_line: int  # 1-indexed
    start_col: int  # 1-indexed
    end_line: int  # 1-indexed
    end_col: int  # 1-indexed (exclusive)
    replacement: str


def apply_edits(content: str, edits: list[LintEdit]) -> str:
    """Apply atomic edits in reverse coordinate order to maintain offset validity."""
    if not edits:
        return content

    # Splitlines keepends=True preserves all exact newlines
    lines = content.splitlines(keepends=True)
    if not lines:
        return content

    # Sort descending: (start_line, start_col, end_line, end_col)
    # This guarantees bottom-up, right-to-left application
    sorted_edits = sorted(
        edits,
        key=lambda e: (e.start_line, e.start_col, e.end_line, e.end_col),
        reverse=True,
    )

    last_applied_start: tuple[int, int] | None = None

    for edit in sorted_edits:
        s_line = edit.start_line - 1
        s_col = edit.start_col - 1
        e_line = edit.end_line - 1
        e_col = edit.end_col - 1

        if (
            s_line < 0
            or e_line >= len(lines)
            or s_col < 0
            or e_col < 0
            or s_line > e_line
            or (s_line == e_line and s_col > e_col)
        ):
            continue

        # Prevent overlapping edits
        if last_applied_start is not None:
            prev_s_line, prev_s_col = last_applied_start
            if (e_line > prev_s_line) or (e_line == prev_s_line and e_col > prev_s_col):
                # Overlaps with an already-applied edit further down/right; skip
                continue

        last_applied_start = (s_line, s_col)

        if s_line == e_line:
            # Single-line substitution
            target_line = lines[s_line]
            lines[s_line] = target_line[:s_col] + edit.replacement + target_line[e_col:]
        else:
            # Multi-line block substitution
            first_line = lines[s_line][:s_col]
            last_line = lines[e_line][e_col:]
            lines[s_line : e_line + 1] = [first_line + edit.replacement + last_line]

    return "".join(lines)


def generate_unified_diff(original: str, fixed: str, filename: str) -> str:
    """Generate unified diff for inspection (--diff)."""
    orig_lines = original.splitlines(keepends=True)
    fixed_lines = fixed.splitlines(keepends=True)
    diff = list(
        difflib.unified_diff(
            orig_lines,
            fixed_lines,
            fromfile=f"a/{filename.lstrip('/')}",
            tofile=f"b/{filename.lstrip('/')}",
        )
    )
    return "".join(diff)
