"""Unit tests for the reverse-offset fixer engine and diff generator."""

from __future__ import annotations

from gfm_math_lint.fixer import LintEdit, apply_edits, generate_unified_diff


def test_apply_single_line_edit() -> None:
    content = "Hello world!\n"
    # Replace "world" with "GitHub"
    # "world" is at col 7..12
    edit = LintEdit("TEST", start_line=1, start_col=7, end_line=1, end_col=12, replacement="GitHub")
    fixed = apply_edits(content, [edit])
    assert fixed == "Hello GitHub!\n"


def test_apply_multiple_edits_same_line_reverse_order() -> None:
    content = "foo and bar\n"
    # Replace "bar" with "qux" (col 9..12)
    # Replace "foo" with "baz" (col 1..4)
    edit1 = LintEdit("TEST", start_line=1, start_col=1, end_line=1, end_col=4, replacement="baz")
    edit2 = LintEdit("TEST", start_line=1, start_col=9, end_line=1, end_col=12, replacement="qux")

    # Pass in forward order, verify fixer applies in reverse order correctly
    fixed = apply_edits(content, [edit1, edit2])
    assert fixed == "baz and qux\n"


def test_apply_multiline_edit() -> None:
    content = "line 1\nline 2\nline 3\nline 4\n"
    # Replace line 2 and line 3 with "replaced\n"
    edit = LintEdit("TEST", start_line=2, start_col=1, end_line=3, end_col=8, replacement="replaced\n")
    fixed = apply_edits(content, [edit])
    assert fixed == "line 1\nreplaced\nline 4\n"


def test_generate_unified_diff() -> None:
    original = "Hello world\n"
    fixed = "Hello GitHub\n"
    diff = generate_unified_diff(original, fixed, "example.md")
    assert "--- a/example.md" in diff
    assert "+++ b/example.md" in diff
    assert "-Hello world" in diff
    assert "+Hello GitHub" in diff


def test_apply_empty_edits() -> None:
    content = "No changes\n"
    assert apply_edits(content, []) == content
