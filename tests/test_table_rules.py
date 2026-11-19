"""Unit tests for GFM Table rules (GFM-T01)."""

from __future__ import annotations

from gfm_math_lint.fixer import apply_edits
from gfm_math_lint.rules.table_rules import RuleT01
from gfm_math_lint.tokenizer import scan_document_zones


def _assert_rule_t01_fix(bad: str, expected: str, expected_violations: int = 1) -> None:
    rule = RuleT01()
    lines = bad.splitlines(keepends=True)
    zones = scan_document_zones(lines)
    violations = rule.check(lines, zones)
    assert len(violations) == expected_violations
    for violation in violations:
        if violation.edit is not None:
            assert "&#124;" not in violation.edit.replacement or "`" in bad
    edits = [v.edit for v in violations if v.edit is not None]
    fixed = apply_edits(bad, edits)
    assert fixed == expected

    # Idempotency
    lines2 = fixed.splitlines(keepends=True)
    zones2 = scan_document_zones(lines2)
    assert len(rule.check(lines2, zones2)) == 0


def test_rule_t01_table_math_pipe() -> None:
    bad = "| Metric | Condition |\n| :--- | :--- |\n| Norm | $||x|| < 1e-9$ |\n"
    expected = "| Metric | Condition |\n| :--- | :--- |\n| Norm | $\\lVert x\\rVert < 1e-9$ |\n"
    _assert_rule_t01_fix(bad, expected)


def test_rule_t01_table_math_single_raw_pipes() -> None:
    bad = "| Metric | Condition |\n| :--- | :--- |\n| Diff | $|x - y| \\le 0.01$ |\n"
    expected = "| Metric | Condition |\n| :--- | :--- |\n| Diff | $\\lvert x - y\\rvert \\le 0.01$ |\n"
    _assert_rule_t01_fix(bad, expected)


def test_rule_t01_table_math_norm_bars() -> None:
    bad = "| Metric | Condition |\n| :--- | :--- |\n| Norm | $\\|x\\|_2$ |\n"
    expected = "| Metric | Condition |\n| :--- | :--- |\n| Norm | $\\lVert x\\rVert_2$ |\n"
    _assert_rule_t01_fix(bad, expected)


def test_rule_t01_table_math_html_pipe_entities() -> None:
    bad = (
        "| Expr | Form |\n"
        "| :--- | :--- |\n"
        "| Dec | $&#124;x&#124;^2$ |\n"
        "| Hex | $&#x7c;x&#x7c;$ |\n"
        "| HexUpper | $&#x7C;x&#x7C;$ |\n"
        "| Verbar | $&verbar;x&verbar;$ |\n"
        "| Vert | $&vert;x&vert;$ |\n"
        "| Double | $&#124;&#124;x&#124;&#124;$ |\n"
    )
    expected = (
        "| Expr | Form |\n"
        "| :--- | :--- |\n"
        "| Dec | $\\lvert x\\rvert^2$ |\n"
        "| Hex | $\\lvert x\\rvert$ |\n"
        "| HexUpper | $\\lvert x\\rvert$ |\n"
        "| Verbar | $\\lvert x\\rvert$ |\n"
        "| Vert | $\\lvert x\\rvert$ |\n"
        "| Double | $\\lVert x\\rVert$ |\n"
    )
    _assert_rule_t01_fix(bad, expected, expected_violations=6)


def test_rule_t01_table_math_conditional_probability() -> None:
    bad = "| Metric | Condition |\n| :--- | :--- |\n| Prob | $P(A | B)$ |\n"
    expected = "| Metric | Condition |\n| :--- | :--- |\n| Prob | $P(A \\vert B)$ |\n"
    _assert_rule_t01_fix(bad, expected)


def test_rule_t01_table_math_preserves_clean_macros() -> None:
    rule = RuleT01()
    clean = "| Metric | Condition |\n| :--- | :--- |\n| Diff | $\\lvert x - y \\rvert \\le 0.01$ |\n"
    lines = clean.splitlines(keepends=True)
    zones = scan_document_zones(lines)
    assert len(rule.check(lines, zones)) == 0


def test_rule_t01_table_code_pipe() -> None:
    bad = "| Command | Output |\n| :--- | :--- |\n| Pipe | `cat | grep` |\n"
    expected = "| Command | Output |\n| :--- | :--- |\n| Pipe | `cat \\| grep` |\n"
    _assert_rule_t01_fix(bad, expected)
