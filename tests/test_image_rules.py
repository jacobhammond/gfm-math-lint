"""Unit tests for GFM image format rules (GFM-I01)."""

from __future__ import annotations

from gfm_math_lint.rules.image_rules import RuleI01
from gfm_math_lint.tokenizer import scan_document_zones


def test_rule_i01_non_avif_image_detected() -> None:
    rule = RuleI01()
    content = "Here is a plot: ![Loss Curve](figs/loss_curve.png)\n"
    lines = content.splitlines(keepends=True)
    zones = scan_document_zones(lines)
    violations = rule.check(lines, zones)
    assert len(violations) == 1
    assert violations[0].rule_id == "GFM-I01"
    assert violations[0].severity == "warning"
    assert violations[0].edit is None  # Report-only warning to prevent breaking links


def test_rule_i01_avif_and_weblinks_ignored() -> None:
    rule = RuleI01()
    content = (
        "![Already AVIF](figs/photo.avif)\n"
        "![Remote](https://example.com/logo.png)\n"
        "![GIF animated](figs/anim.gif)\n"
        "![Vector logo](logo.svg)\n"
    )
    lines = content.splitlines(keepends=True)
    zones = scan_document_zones(lines)
    assert len(rule.check(lines, zones)) == 0


def test_rule_i01_image_with_title() -> None:
    rule = RuleI01()
    content = '![Architecture](diagram.png "System Diagram")\n'
    lines = content.splitlines(keepends=True)
    zones = scan_document_zones(lines)
    violations = rule.check(lines, zones)
    assert len(violations) == 1
    assert violations[0].edit is None


def test_rule_i01_inline_code_span_ignored() -> None:
    rule = RuleI01()
    content = "In code: `![x](y.png)` is shown.\n"
    lines = content.splitlines(keepends=True)
    zones = scan_document_zones(lines)
    assert len(rule.check(lines, zones)) == 0
