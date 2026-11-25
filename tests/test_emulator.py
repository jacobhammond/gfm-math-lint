"""Tests for the zero-dependency GFM CommonMark math emulator and span comparator."""

from __future__ import annotations

from gfm_math_lint.emulator import (
    MathSpan,
    compare_math_spans,
    emulate_gfm_document,
    extract_intended_math_spans,
)


def test_emulator_p1_intraword_underscore_clean() -> None:
    res = emulate_gfm_document("$a_1 + b_2$ and $c_3$\n")
    assert len(res.intended_spans) == 2
    assert len(res.received_spans) == 2
    assert res.diffs == []
    assert "<em>" not in res.rendered_html


def test_emulator_p2_escaped_underscore_unescaped_clean() -> None:
    res = emulate_gfm_document(r"$a\_1 + b_2$ and $c_3$" + "\n")
    assert len(res.intended_spans) == 2
    assert [s.content for s in res.received_spans] == ["a_1 + b_2", "c_3"]
    assert res.diffs == []


def test_emulator_p3_p6_backslash_punctuation_stripped() -> None:
    res = emulate_gfm_document(r"$x\,y \{z\} \lvert w \rvert \ast$" + "\n\n$$\n\\{d\\} \\, e\n$$\n")
    assert [s.content for s in res.received_spans] == [r"x,y {z} \lvert w \rvert \ast", "{d} , e"]
    assert any(d.category == "span-mutated" for d in res.diffs)


def test_emulator_p5_p7_display_linebreak_eol_vs_midline() -> None:
    eol_md = "$$\n\\begin{aligned}\na &= b \\\\\nc &= d\n\\end{aligned}\n$$\n"
    res_eol = emulate_gfm_document(eol_md)
    assert res_eol.diffs == []

    midline_md = "$$\n\\begin{bmatrix} a \\\\ b \\end{bmatrix}\n$$\n"
    res_mid = emulate_gfm_document(midline_md)
    assert len(res_mid.diffs) == 1
    assert res_mid.diffs[0].category == "span-mutated"
    assert res_mid.diffs[0].received == r"\begin{bmatrix} a \ b \end{bmatrix}"


def test_emulator_p8_p9_p10_dropped_spans() -> None:
    # P8: indented $$ in list
    res_p8 = emulate_gfm_document("* Item:\n  $$\n  x = 1\n  $$\n")
    assert len(res_p8.intended_spans) == 1
    assert len(res_p8.received_spans) == 0
    assert any(d.category == "span-count-mismatch" for d in res_p8.diffs)
    assert any(d.category == "span-dropped" for d in res_p8.diffs)

    # P9: display block interruption
    res_p9 = emulate_gfm_document("$$\nP = U\n+ Z\n- 2R\n$$\n")
    assert len(res_p9.received_spans) == 0
    assert any(d.category == "span-dropped" for d in res_p9.diffs)

    # P10: glued opening delimiter
    res_p10 = emulate_gfm_document("the base-$e$ error\n")
    assert len(res_p10.intended_spans) == 1
    assert len(res_p10.received_spans) == 0
    assert any(d.category == "span-dropped" for d in res_p10.diffs)


def test_emulator_p11_fenced_math_and_backtick_math_bypass() -> None:
    md = "Inline $`P_{\\text{primary}}`$ and:\n\n```math\n\\{i\\} \\, x\n```\n"
    res = emulate_gfm_document(md)
    assert len(res.intended_spans) == 2
    assert len(res.received_spans) == 2
    assert res.diffs == []


def test_emulator_ignores_code_spans_and_detects_flanking_emphasis() -> None:
    spans = extract_intended_math_spans("Use `$x$` in prose, and $P_{\\text{a}}$ + $P_{\\text{b}}$.\n")
    assert len(spans) == 2
    res = emulate_gfm_document("Let $P_{\\text{a}}$ and $P_{\\text{b}}$ be powers.\n")
    assert "<em>" in res.rendered_html


def test_compare_math_spans_detects_escaped_underscore_in_text_macro() -> None:
    intended = [MathSpan(content=r"\text{a\_b}", display=False, delimiter="$", line=1)]
    received = [MathSpan(content=r"\text{a_b}", display=False, delimiter="$", line=1)]
    diffs = compare_math_spans(intended, received)
    assert len(diffs) == 1
    assert diffs[0].category == "span-mutated"


def test_emulator_indented_display_math_and_many_dropped_spans() -> None:
    indented_md = "$$\n\\begin{aligned}\n  a &= b \\\\\n  c &= d\n\\end{aligned}\n$$\n"
    res = emulate_gfm_document(indented_md)
    assert res.diffs == []

    intended = [
        MathSpan(content=x, display=False, delimiter="$", line=idx)
        for idx, x in enumerate(["A", "B", "C", "D", "E"], 1)
    ]
    received = [MathSpan(content="E", display=False, delimiter="$", line=5)]
    diffs = compare_math_spans(intended, received)
    assert diffs[0].category == "span-count-mismatch"
    dropped = [d for d in diffs if d.category == "span-dropped"]
    assert [d.intended for d in dropped] == ["A", "B", "C", "D"]
    assert not any(d.category == "span-mutated" for d in diffs)


def test_emulator_currency_range_and_heading_blockquote_html() -> None:
    res = emulate_gfm_document("# Heading $x_1$\n\n> Quote $y_2$\n\nThe price is $10-$20.\n")
    assert len(res.intended_spans) == 2
    assert len(res.received_spans) == 2
    assert res.diffs == []
    assert "<h1>Heading " in res.rendered_html
    assert "<h1># " not in res.rendered_html
    assert "<blockquote><p>Quote " in res.rendered_html
    assert "<p>> " not in res.rendered_html
