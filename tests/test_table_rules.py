"""Unit tests for GFM Table rules (GFM-T01)."""

from __future__ import annotations

from gfm_math_lint.fixer import apply_edits
from gfm_math_lint.rules.table_rules import RuleT01
from gfm_math_lint.tokenizer import scan_document_zones


def test_rule_t01_table_math_pipe() -> None:
    rule = RuleT01()
    bad = "| Metric | Condition |\n| :--- | :--- |\n| Norm | $||x|| < 1e-9$ |\n"
    expected = "| Metric | Condition |\n| :--- | :--- |\n| Norm | $&#124;&#124;x&#124;&#124; < 1e-9$ |\n"

    lines = bad.splitlines(keepends=True)
    zones = scan_document_zones(lines)
    violations = rule.check(lines, zones)
    assert len(violations) == 4  # 4 pipes in ||x||
    edits = [v.edit for v in violations if v.edit is not None]
    fixed = apply_edits(bad, edits)
    assert fixed == expected

    # Idempotency
    lines2 = fixed.splitlines(keepends=True)
    zones2 = scan_document_zones(lines2)
    assert len(rule.check(lines2, zones2)) == 0


def test_rule_t01_table_code_pipe() -> None:
    rule = RuleT01()
    bad = "| Command | Output |\n| :--- | :--- |\n| Pipe | `cat | grep` |\n"
    expected = "| Command | Output |\n| :--- | :--- |\n| Pipe | `cat \\| grep` |\n"

    lines = bad.splitlines(keepends=True)
    zones = scan_document_zones(lines)
    violations = rule.check(lines, zones)
    assert len(violations) == 1
    edits = [v.edit for v in violations if v.edit is not None]
    fixed = apply_edits(bad, edits)
    assert fixed == expected

    # Idempotency
    lines2 = fixed.splitlines(keepends=True)
    zones2 = scan_document_zones(lines2)
    assert len(rule.check(lines2, zones2)) == 0
