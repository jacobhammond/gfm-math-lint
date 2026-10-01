"""Unit tests for math rules GFM-M01 through GFM-M10."""

from __future__ import annotations

from typing import TYPE_CHECKING

from gfm_math_lint.fixer import apply_edits

if TYPE_CHECKING:
    from gfm_math_lint.rules.base import Rule
from gfm_math_lint.rules.math_rules import (
    RuleM01,
    RuleM02,
    RuleM03,
    RuleM04,
    RuleM05,
    RuleM06,
    RuleM07,
    RuleM08,
    RuleM09,
    RuleM10,
    RuleM11,
    RuleM12,
    RuleM13,
)
from gfm_math_lint.tokenizer import scan_document_zones


def check_and_fix(rule: Rule, content: str) -> tuple[str, int]:
    """Helper to run a rule on content, apply its edits, and return (fixed_content, violation_count)."""
    lines = content.splitlines(keepends=True)
    zones = scan_document_zones(lines)
    violations = rule.check(lines, zones)
    edits = [v.edit for v in violations if v.edit is not None]
    fixed = apply_edits(content, edits)
    return fixed, len(violations)


def assert_idempotent(rule: Rule, bad_content: str, expected_fixed: str) -> None:
    """Verify that fixing produces expected output and a second fix pass is a no-op."""
    fixed, count = check_and_fix(rule, bad_content)
    assert count > 0
    assert fixed == expected_fixed

    # Second pass must produce 0 violations and identical content
    fixed2, count2 = check_and_fix(rule, fixed)
    assert count2 == 0
    assert fixed2 == fixed


def test_rule_m01_math_code_fence() -> None:
    rule = RuleM01()
    bad = "```math\nx = \\frac{-b \\pm \\sqrt{b^2-4ac}}{2a}\n```\n"
    expected = "$$\nx = \\frac{-b \\pm \\sqrt{b^2-4ac}}{2a}\n$$\n"
    assert_idempotent(rule, bad, expected)


def test_rule_m02_block_math_isolation() -> None:
    rule = RuleM02()
    bad = "Some text above\n$$x = y + 1$$\nSome text below\n"
    expected = "Some text above\n\n$$\nx = y + 1\n$$\n\nSome text below\n"
    assert_idempotent(rule, bad, expected)


def test_rule_m02_internal_blank_lines() -> None:
    rule = RuleM02()
    bad = "\n$$\na = b\n\nc = d\n$$\n\n"
    expected = "\n$$\na = b\nc = d\n$$\n\n"
    fixed, count = check_and_fix(rule, bad)
    assert count > 0
    assert fixed == expected
    _fixed2, count2 = check_and_fix(rule, fixed)
    assert count2 == 0


def test_rule_m02_internal_blank_lines_and_padding_combined() -> None:
    rule = RuleM02()
    bad = "Text above\n$$\na = b\n\nc = d\n$$\nText below\n"
    expected = "Text above\n\n$$\na = b\nc = d\n$$\n\nText below\n"
    assert_idempotent(rule, bad, expected)


def test_rule_m03_text_mode_underscore_escape() -> None:
    rule = RuleM03()
    # Bad with single escaped underscore
    bad = "Here is $\\text{ave\\_shift}$ in equation.\n"
    expected = "Here is $\\text{ave\\\\_shift}$ in equation.\n"
    assert_idempotent(rule, bad, expected)

    # Bad with raw underscore
    bad_raw = "Here is $\\text{ave_shift}$ in equation.\n"
    assert_idempotent(rule, bad_raw, expected)


def test_rule_m04_inline_math_whitespace() -> None:
    rule = RuleM04()
    bad = "The result is $ x + y $ for all inputs.\n"
    expected = "The result is $x + y$ for all inputs.\n"
    assert_idempotent(rule, bad, expected)


def test_rule_m05_curly_brace_escape() -> None:
    rule = RuleM05()
    bad = "$$\\phi \\in \\left\\{ \\frac{3\\pi}{2} \\right\\}$$\n"
    expected = "$$\\phi \\in \\left\\lbrace \\frac{3\\pi}{2} \\right\\rbrace$$\n"
    assert_idempotent(rule, bad, expected)


def test_rule_m06_relational_operator_collision() -> None:
    rule = RuleM06()
    bad = "$$W_{<i}$$\n"
    expected = "$$W_{\\lt i}$$\n"
    assert_idempotent(rule, bad, expected)


def test_rule_m07_asterisk_emphasis_collision() -> None:
    rule = RuleM07()
    bad = "$$y^*[n] = \\delta \\cdot y^*[n]$$\n"
    expected = "$$y^{\\ast}[n] = \\delta \\cdot y^{\\ast}[n]$$\n"
    assert_idempotent(rule, bad, expected)

    # Test subscript with braces: y_{*}
    bad_sub = "$$y_{*} = 1$$\n"
    expected_sub = "$$y_{\\ast} = 1$$\n"
    assert_idempotent(rule, bad_sub, expected_sub)

    # Empty subscript should not be flagged
    empty_sub = "$$y_{} = 0$$\n"
    lines = empty_sub.splitlines(keepends=True)
    zones = scan_document_zones(lines)
    assert len(rule.check(lines, zones)) == 0


def test_rule_m08_disallowed_macro() -> None:
    rule = RuleM08()
    bad = "$$I[n+1] = \\operatorname{clamp}(I[n])$$\n"
    expected = "$$I[n+1] = \\mathop{\\mathrm{clamp}}(I[n])$$\n"
    assert_idempotent(rule, bad, expected)


def test_rule_m09_align_environment() -> None:
    rule = RuleM09()
    bad = "$$\n\\begin{align}\na &= b \\\\\nc &= d\n\\end{align}\n$$\n"
    expected = "$$\n\\begin{aligned}\na &= b \\\\\nc &= d\n\\end{aligned}\n$$\n"
    assert_idempotent(rule, bad, expected)


def test_rule_m10_currency_dollar_sign() -> None:
    rule = RuleM10()
    bad = "The price increased from $10 to $20 per unit.\n"
    expected = "The price increased from \\$10 to \\$20 per unit.\n"
    assert_idempotent(rule, bad, expected)


def test_rule_m10_single_dollar_not_flagged() -> None:
    rule = RuleM10()
    single = "The item costs $10 only.\n"
    lines = single.splitlines(keepends=True)
    zones = scan_document_zones(lines)
    violations = rule.check(lines, zones)
    assert len(violations) == 0


def test_rule_m10_currency_coexisting_with_inline_math() -> None:
    rule = RuleM10()
    bad = "To split $100 in half, we calculate $100/2$.\n"
    expected = "To split \\$100 in half, we calculate $100/2$.\n"
    assert_idempotent(rule, bad, expected)


def test_rule_m11_inline_latex_delimiters() -> None:
    rule = RuleM11()
    bad = "In equation \\( x + y = z \\), all terms are non-negative.\n"
    expected = "In equation $x + y = z$, all terms are non-negative.\n"
    assert_idempotent(rule, bad, expected)


def test_rule_m11_inline_latex_multiple_per_line() -> None:
    rule = RuleM11()
    bad = "Here \\( a \\) and \\( b \\) are coefficients.\n"
    expected = "Here $a$ and $b$ are coefficients.\n"
    assert_idempotent(rule, bad, expected)


def test_rule_m11_display_latex_delimiters_single_line() -> None:
    rule = RuleM11()
    bad = "Text above\n\\[ x = y + 1 \\]\nText below\n"
    expected = "Text above\n\n$$\nx = y + 1\n$$\n\nText below\n"
    assert_idempotent(rule, bad, expected)


def test_rule_m11_display_latex_delimiters_multiline() -> None:
    rule = RuleM11()
    bad = "Text above\n\\[\na = b \\\\\nc = d\n\\]\nText below\n"
    expected = "Text above\n\n$$\na = b \\\\\nc = d\n$$\n\nText below\n"
    assert_idempotent(rule, bad, expected)


def test_rule_m11_ignored_in_code_fence() -> None:
    rule = RuleM11()
    content = "```latex\n\\[\nx = 1\n\\]\nHere is \\( y \\)\n```\n"
    lines = content.splitlines(keepends=True)
    zones = scan_document_zones(lines)
    violations = rule.check(lines, zones)
    assert len(violations) == 0


def test_rule_m02_preserves_indented_list_display_math() -> None:
    rule = RuleM02()
    content = "* List item:\n   $$n_g = 1$$\n"
    lines = content.splitlines(keepends=True)
    zones = scan_document_zones(lines)
    violations = rule.check(lines, zones)
    assert len(violations) == 0


def test_rule_m11_preserves_indented_list_display_math() -> None:
    rule = RuleM11()
    bad = "* List item:\n   \\[ n_g = 1 \\]\n"
    expected = "* List item:\n   $$n_g = 1$$\n"
    assert_idempotent(rule, bad, expected)


def test_rule_m12_inline_math_underscore_collision() -> None:
    rule = RuleM12()
    bad = r"Header | $a_0$ at $b_{\text{max}}$ |" + "\n"
    expected = r"Header | $a\_0$ at $b\_{\text{max}}$ |" + "\n"
    assert_idempotent(rule, bad, expected)


def test_rule_m12_single_formula_multiple_subscripts() -> None:
    rule = RuleM12()
    bad = r"Equation $\langle x\rangle = y_0 z_{\text{ref}}$ holds true." + "\n"
    expected = r"Equation $\langle x\rangle = y\_0 z\_{\text{ref}}$ holds true." + "\n"
    assert_idempotent(rule, bad, expected)


def test_rule_m12_single_underscore_no_violation() -> None:
    rule = RuleM12()
    content = "Let $x_0$ be initial value.\n"
    lines = content.splitlines(keepends=True)
    zones = scan_document_zones(lines)
    violations = rule.check(lines, zones)
    assert len(violations) == 0


def test_rule_m12_text_macro_underscores_preserved() -> None:
    rule = RuleM12()
    bad = r"Compare $x_0$ and $\text{my_var}$ and $y_0$." + "\n"
    # Rule M12 escapes x_0 and y_0, but does not escape inside \text{}
    expected = r"Compare $x\_0$ and $\text{my_var}$ and $y\_0$." + "\n"
    assert_idempotent(rule, bad, expected)


def test_rule_m12_backtick_math_ignored() -> None:
    rule = RuleM12()
    content = "Compare $`x_0`$ and $`y_0`$.\n"
    lines = content.splitlines(keepends=True)
    zones = scan_document_zones(lines)
    violations = rule.check(lines, zones)
    assert len(violations) == 0


def test_rule_m12_single_line_display_math_underscores() -> None:
    rule = RuleM12()
    bad = r"   $$\text{VAL}_{\text{dB}} = 10\log_{10}(a_1 + b_1)$$" + "\n"
    expected = r"   $$\text{VAL}\_{\text{dB}} = 10\log\_{10}(a\_1 + b\_1)$$" + "\n"
    assert_idempotent(rule, bad, expected)


def test_rule_m13_compound_math_en_dash() -> None:
    rule = RuleM13()
    bad = "The $A$\u2013$B$ curve and $1.0$\u2013$2.5$ range.\n"
    expected = "The $A\\text{\u2013}B$ curve and $1.0\\text{\u2013}2.5$ range.\n"
    assert_idempotent(rule, bad, expected)


def test_rule_m13_compound_math_hyphen() -> None:
    rule = RuleM13()
    bad = "The $x$-$y$ plane.\n"
    expected = "The $x\\text{-}y$ plane.\n"
    assert_idempotent(rule, bad, expected)


def test_rule_m13_glued_closing_unit() -> None:
    rule = RuleM13()
    bad = r"Values from $15\ ^\circ$C to $85\ ^\circ$C and $0.5$dB." + "\n"
    expected = r"Values from $15\ ^\circ$ C to $85\ ^\circ$ C and $0.5$ dB." + "\n"
    assert_idempotent(rule, bad, expected)


def test_rule_m13_parenthesis_collision() -> None:
    rule = RuleM13()
    bad = "($A = B$ instead of $G(L)$)\n"
    expected = "($A = B$ instead of $G(L)$ )\n"
    assert_idempotent(rule, bad, expected)
