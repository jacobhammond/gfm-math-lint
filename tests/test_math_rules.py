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
    RuleM14,
    RuleM15,
    RuleM16,
    RuleM17,
    RuleM18,
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
    expected = "Here is $\\text{ave-shift} = 10$ in equation.\n"

    # Bad with single escaped underscore
    bad = "Here is $\\text{ave\\_shift} = 10$ in equation.\n"
    assert_idempotent(rule, bad, expected)

    # Bad with raw underscore
    bad_raw = "Here is $\\text{ave_shift} = 10$ in equation.\n"
    assert_idempotent(rule, bad_raw, expected)

    # Bad with legacy double-escaped underscore
    bad_double = "Here is $\\text{ave\\\\_shift} = 10$ in equation.\n"
    assert_idempotent(rule, bad_double, expected)

    # Also catches underscores inside backtick math text macros
    bad_bt = "Here is $`\\text{sensor_ref_in} \\ge 0.5`$ in equation.\n"
    expected_bt = "Here is $`\\text{sensor-ref-in} \\ge 0.5`$ in equation.\n"
    assert_idempotent(rule, bad_bt, expected_bt)


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


def test_rule_m02_breaks_out_indented_list_display_math() -> None:
    rule = RuleM02()
    bad = "* List item:\n   $$n_g = 1$$\n"
    expected = "* List item:\n\n$$\nn_g = 1\n$$\n"
    assert_idempotent(rule, bad, expected)


def test_rule_m01_preserves_list_and_blockquote_math_fences() -> None:
    rule = RuleM01()
    list_fence = "* Item 1:\n  ```math\n  x = 1\n  ```\n"
    bq_fence = "> ```math\n> x = 1\n> ```\n"
    guard_fence = "```math\nA = B\n===\n```\n"
    for content in (list_fence, bq_fence, guard_fence):
        lines = content.splitlines(keepends=True)
        zones = scan_document_zones(lines)
        assert len(rule.check(lines, zones)) == 0


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
    bad = r"Compare $x_{0}$ and $\text{my_var}$ and $y_{0}$." + "\n"
    # Rule M12 escapes x_{0} and y_{0}, but does not escape inside \text{}
    expected = r"Compare $x\_{0}$ and $\text{my_var}$ and $y\_{0}$." + "\n"
    assert_idempotent(rule, bad, expected)


def test_rule_m12_intraword_subscripts_and_vscode_target() -> None:
    rule = RuleM12()
    clean_intra = "Values $a_1 + b_2$ and $c_3$ are safe.\n"
    lines = clean_intra.splitlines(keepends=True)
    assert len(rule.check(lines, scan_document_zones(lines))) == 0

    rule_vs = RuleM12()
    rule_vs.target = "vscode"
    bad = r"Let $P_{\text{primary}}$ and $P_{\text{secondary}}$ be powers." + "\n"
    expected_vs = r"Let $P _ {\text{primary}}$ and $P _ {\text{secondary}}$ be powers." + "\n"
    assert_idempotent(rule_vs, bad, expected_vs)


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


def test_rule_m13_glued_opening_delimiter() -> None:
    rule = RuleM13()
    bad = "The base-$e$ error and x$y$ term.\n"
    expected = "The base $e$ error and x $y$ term.\n"
    assert_idempotent(rule, bad, expected)


def test_rule_m05_backslash_punctuation_generalized() -> None:
    rule = RuleM05()
    bad = r"Spacing $x\,y + a\:b + c\;d + e\!f$ and $\|v\|$." + "\n"
    expected = r"Spacing $x\thinspace y + a\medspace b + c\thickspace d + e\negthinspace f$ and $\Vert v\Vert$." + "\n"
    assert_idempotent(rule, bad, expected)


def test_rule_m06_ignores_closed_html_tags() -> None:
    rule = RuleM06()
    html_snippet = "$$\n\\text{SNR}<br><em>x</em>\n$$\n"
    lines = html_snippet.splitlines(keepends=True)
    assert len(rule.check(lines, scan_document_zones(lines))) == 0


def test_rule_m14_function_identities_and_snake_case() -> None:
    rule = RuleM14()
    bad1 = "$\\text{fix}(\\text{fix}(c)) \\equiv \\text{fix}(c)$\n"
    assert_idempotent(rule, bad1, "`fix(fix(c)) == fix(c)`\n")

    bad2 = "$\\text{parse}(\\text{str}) == \\text{ast}$\n"
    assert_idempotent(rule, bad2, "`parse(str) == ast`\n")

    bad3 = "Register $\\text{sensor_ref_in}$ is asserted.\n"
    assert_idempotent(rule, bad3, "Register `sensor_ref_in` is asserted.\n")

    # Embedded snake_case in equation is flagged (edit=None; RuleM03 provides non-overlapping edit)
    embedded = "Threshold $\\text{sensor_ref_in} \\ge 0.5$ holds.\n"
    lines = embedded.splitlines(keepends=True)
    assert len(rule.check(lines, scan_document_zones(lines))) == 1

    # Valid mathematical notation must NOT be flagged
    valid = (
        "$f(x) = x^2 + 2x + 1$\n"
        "$\\lim_{x \\to 0} \\frac{\\sin x}{x} = 1$\n"
        "$\\text{Probability}(A \\mid B) = \\frac{P(B \\mid A) P(A)}{P(B)}$\n"
    )
    valid_lines = valid.splitlines(keepends=True)
    assert len(rule.check(valid_lines, scan_document_zones(valid_lines))) == 0


def test_rule_m15_percent_and_unicode_dash() -> None:
    rule = RuleM15()
    bad_pct = "Settle $86.5\\%$ and $t_{99\\%}$ and $D \\le 50%$.\n"
    expected_pct = "Settle $`86.5\\%`$ and $`t_{99\\%}`$ and $`D \\le 50\\%`$.\n"
    assert_idempotent(rule, bad_pct, expected_pct)

    bad_dash = "Range $20\u201325^\\circ\\text{C}$.\n"
    expected_dash = "Range $20-25^\\circ\\text{C}$.\n"
    assert_idempotent(rule, bad_dash, expected_dash)


def test_rule_m16_display_linebreak_eol() -> None:
    rule = RuleM16()
    bad = "$$\nS = \\begin{bmatrix} 0 & T \\\\ T & 0 \\end{bmatrix}\n$$\n"
    expected = "$$\nS = \\begin{bmatrix} 0 & T \\\\\nT & 0 \\end{bmatrix}\n$$\n"
    assert_idempotent(rule, bad, expected)


def test_rule_m17_display_block_start() -> None:
    rule = RuleM17()
    bad = "$$\nP = U\n+ Z\n- 2R\n$$\n"
    expected = "$$\nP = U\n{}+ Z\n{}- 2R\n$$\n"
    assert_idempotent(rule, bad, expected)

    # REG-11: setext underline inside $$ is flagged as unfixable error
    bad_setext = "$$\nA = B\n===\n$$\n"
    lines = bad_setext.splitlines(keepends=True)
    violations = rule.check(lines, scan_document_zones(lines))
    assert len(violations) == 1
    assert violations[0].severity == "error"
    assert violations[0].edit is None


def test_rule_m18_non_ascii_in_math() -> None:
    rule = RuleM18()
    bad = "Pulse $8.5\\ \\text{µs}$ at $25°\\text{C}$ and $α + β$.\n"
    expected = "Pulse $8.5\\ \\mu\\text{s}$ at $25^\\circ\\text{C}$ and $\\alpha + \\beta$.\n"
    assert_idempotent(rule, bad, expected)
