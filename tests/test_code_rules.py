"""Unit tests for GFM code block and inline code rules (GFM-C01, GFM-C02)."""

from __future__ import annotations

from gfm_math_lint.fixer import apply_edits
from gfm_math_lint.rules.code_rules import RuleC01, RuleC02
from gfm_math_lint.tokenizer import scan_document_zones


def test_rule_c01_fence_nesting_length() -> None:
    rule = RuleC01()
    bad = "```markdown\n```math\nx = y + 1\n```\n```\n"
    expected = "````markdown\n```math\nx = y + 1\n```\n````\n"

    lines = bad.splitlines(keepends=True)
    zones = scan_document_zones(lines)
    violations = rule.check(lines, zones)
    assert len(violations) == 1
    assert violations[0].rule_id == "GFM-C01"
    edits = [v.edit for v in violations if v.edit is not None]
    fixed = apply_edits(bad, edits)
    assert fixed == expected

    # Idempotency
    lines2 = fixed.splitlines(keepends=True)
    zones2 = scan_document_zones(lines2)
    assert len(rule.check(lines2, zones2)) == 0


def test_rule_c02_inline_code_span_backtick_nesting() -> None:
    rule = RuleC02()
    bad = "Use (`$`\\text{shift}`$`) and (` ```math `) in text.\n"
    expected = "Use (``$`\\text{shift}`$``) and (`` ```math ``) in text.\n"

    lines = bad.splitlines(keepends=True)
    zones = scan_document_zones(lines)
    violations = rule.check(lines, zones)
    assert len(violations) == 2
    edits = [v.edit for v in violations if v.edit is not None]
    fixed = apply_edits(bad, edits)
    assert fixed == expected

    # Idempotency
    lines2 = fixed.splitlines(keepends=True)
    zones2 = scan_document_zones(lines2)
    assert len(rule.check(lines2, zones2)) == 0
