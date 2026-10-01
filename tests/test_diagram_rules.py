"""Unit tests for GFM diagram rules (GFM-D01, GFM-D02)."""

from __future__ import annotations

from gfm_math_lint.rules.diagram_rules import RuleD01, RuleD02
from gfm_math_lint.tokenizer import scan_document_zones


def test_rule_d01_mermaid_identifier_spaces() -> None:
    rule = RuleD01()
    bad = "```mermaid\nsubgraph Module Alpha --> Module Beta\n    Module Alpha --> Module Beta\nend\n```\n"
    lines = bad.splitlines(keepends=True)
    zones = scan_document_zones(lines)
    violations = rule.check(lines, zones)
    assert len(violations) >= 1
    assert any("subgraph" in v.message for v in violations)


def test_rule_d01_mermaid_valid_subgraph() -> None:
    rule = RuleD01()
    good = '```mermaid\nsubgraph MA ["Module Alpha"]\n    MB ["Module Beta"]\n    MA --> MB\nend\n```\n'
    lines = good.splitlines(keepends=True)
    zones = scan_document_zones(lines)
    assert len(rule.check(lines, zones)) == 0


def test_rule_d02_unclosed_fence() -> None:
    rule = RuleD02()
    bad = "```python\ndef broken():\n    pass\n"
    lines = bad.splitlines(keepends=True)
    zones = scan_document_zones(lines)
    violations = rule.check(lines, zones)
    assert len(violations) == 1
    assert violations[0].rule_id == "GFM-D02"
