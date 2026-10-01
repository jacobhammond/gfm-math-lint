"""Unit tests for inline comment suppression system."""

from __future__ import annotations

from gfm_math_lint.linter import Linter


def test_block_suppression() -> None:
    content = (
        "# Title\n\n"
        "<!-- gfm-math-lint-disable GFM-M03 -->\n"
        "$\\text{ave\\_shift}$\n"
        "<!-- gfm-math-lint-enable GFM-M03 -->\n\n"
        "$\\text{another\\_bad}$\n"
    )
    linter = Linter()
    res = linter.lint_string(content)
    # The first \text{ave\_shift} should be suppressed.
    # The second \text{another\_bad} after enable should be flagged.
    assert len(res.violations) == 1
    assert res.violations[0].line == 7
    assert res.violations[0].rule_id == "GFM-M03"


def test_next_line_suppression() -> None:
    content = (
        "| Header 1 | Header 2 |\n"
        "| :--- | :--- |\n"
        "<!-- gfm-math-lint-disable-next-line GFM-T01 -->\n"
        "| Norm | $||x|| < 1e-9$ |\n"
    )
    linter = Linter()
    res = linter.lint_string(content)
    assert len(res.violations) == 0


def test_multi_rule_comma_separation_suppression() -> None:
    content = (
        "<!-- gfm-math-lint-disable-next-line GFM-M05, GFM-M06 -->\n"
        "$$\\phi \\in \\left\\{ 1 \\right\\}, \\quad W_{<i}$$\n"
    )
    linter = Linter()
    res = linter.lint_string(content)
    # GFM-M05 and GFM-M06 should be suppressed
    rule_ids = [v.rule_id for v in res.violations]
    assert "GFM-M05" not in rule_ids
    assert "GFM-M06" not in rule_ids


def test_suppress_all_rules_on_next_line() -> None:
    content = "<!-- gfm-math-lint-disable-next-line -->\n| Metric | $||x|| < 1e-9$ |\n"
    linter = Linter()
    res = linter.lint_string(content)
    assert len(res.violations) == 0


def test_next_line_suppression_does_not_leak_to_subsequent_lines() -> None:
    content = (
        "<!-- gfm-math-lint-disable-next-line GFM-M03 -->\n"
        "$\\text{suppressed\\_first}$\n"
        "$\\text{unsuppressed\\_second}$\n"
    )
    linter = Linter()
    res = linter.lint_string(content)
    # Line 2 is suppressed, but line 3 must NOT be suppressed
    assert len(res.violations) == 1
    assert res.violations[0].line == 3
    assert res.violations[0].rule_id == "GFM-M03"
