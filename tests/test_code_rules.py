"""Unit tests for GFM code block and inline code rules (GFM-C01, GFM-C02)."""

from __future__ import annotations

from gfm_math_lint.fixer import apply_edits
from gfm_math_lint.linter import Linter
from gfm_math_lint.rules.code_rules import RuleC01, RuleC02, RuleC03
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


def test_rule_c03_unrendered_math_in_plain_fence_reg16() -> None:
    rule = RuleC03()
    bad = "```\ndU/dt = -\u03b3 U + \u03a3 P_k\nU = |a|\u00b2\n```\n\n```text\nx = \\frac{1}{2}\n```\n"
    lines = bad.splitlines(keepends=True)
    zones = scan_document_zones(lines)
    violations = rule.check(lines, zones)
    assert len(violations) == 2
    assert all(v.rule_id == "GFM-C03" and v.severity == "warning" for v in violations)


def test_rule_c03_ascii_box_diagram_reg17() -> None:
    rule = RuleC03()
    bad = "```\n\u250c\u2500\u2500\u2500\u2510     \u250c\u2500\u2500\u2500\u2510\n\u2502 A \u2502\u2500\u2500\u2500\u25ba\u2502 B \u2502\n\u2514\u2500\u2500\u2500\u2518     \u2514\u2500\u2500\u2500\u2518\n```\n"
    lines = bad.splitlines(keepends=True)
    zones = scan_document_zones(lines)
    violations = rule.check(lines, zones)
    assert len(violations) == 1
    assert violations[0].rule_id == "GFM-C03"
    assert "mermaid" in violations[0].message


def test_rule_c03_negative_controls_and_suppression() -> None:
    rule = RuleC03()
    clean = (
        "```text\n"
        "src/\n"
        "\u251c\u2500\u2500 cli.py\n"
        "\u2514\u2500\u2500 linter.py\n"
        "```\n\n"
        "```python\n"
        "dU_dt = -gamma * U\n"
        "```\n\n"
        "```\n"
        "x = 10\n"
        "FOO = bar\n"
        "```\n"
    )
    lines = clean.splitlines(keepends=True)
    zones = scan_document_zones(lines)
    assert rule.check(lines, zones) == []

    suppressed = "<!-- gfm-math-lint-disable GFM-C03 -->\n```\ndU/dt = -\u03b3 U\n```\n"
    res = Linter().lint_string(suppressed, fix=False)
    assert not any(v.rule_id == "GFM-C03" for v in res.violations)
