"""Unit tests for GFM HTML verification engine."""

from __future__ import annotations

import argparse
from pathlib import Path
from unittest.mock import patch

import pytest

from gfm_math_lint.cli import cmd_verify
from gfm_math_lint.verifier import (
    GFMHTMLValidator,
    build_preview_html,
    open_in_browser,
    verify_file,
    verify_markdown,
)


def test_validator_clean_math() -> None:
    html = (
        "<p>Valid math: "
        '<math-renderer class="js-inline-math" style="display: inline-block">$x + y = z$</math-renderer>'
        ".</p>"
    )
    validator = GFMHTMLValidator("test.md")
    validator.feed(html)
    assert len(validator.issues) == 0


def test_validator_unrendered_math() -> None:
    html = "<p>Broken math: $0.759$dB and \u2013$V$ and $x = \\alpha + 1$.</p>"
    validator = GFMHTMLValidator("test.md")
    validator.feed(html)
    assert len(validator.issues) >= 1
    categories = [i.category for i in validator.issues]
    assert "unrendered-math" in categories


def test_validator_tag_pollution() -> None:
    html = '<math-renderer class="js-inline-math">$\\text{A}<em>{\\text{B}}</em>$</math-renderer>'
    validator = GFMHTMLValidator("test.md")
    validator.feed(html)
    assert len(validator.issues) == 1
    assert validator.issues[0].category == "tag-pollution"


def test_validator_katex_error() -> None:
    html = '<p><span class="katex-error" title="KaTeX parse error: Expected EOF">\\bad</span></p>'
    validator = GFMHTMLValidator("test.md")
    validator.feed(html)
    assert len(validator.issues) == 1
    assert validator.issues[0].category == "katex-error"


def test_validator_table_column_mismatch() -> None:
    html = "<table><tr><th>Col 1</th><th>Col 2</th></tr><tr><td>Val 1</td><td>Val 2</td><td>Val 3</td></tr></table>"
    validator = GFMHTMLValidator("test.md")
    validator.feed(html)
    assert len(validator.issues) == 1
    assert validator.issues[0].category == "table-mismatch"


def test_validator_currency_not_flagged() -> None:
    html = "<p>The cost is $100 and tax is $5.</p>"
    validator = GFMHTMLValidator("test.md")
    validator.feed(html)
    assert len(validator.issues) == 0


def test_build_preview_html() -> None:
    body = "<p>Hello world</p>"
    preview = build_preview_html(body, title="Test Preview")
    assert "<!DOCTYPE html>" in preview
    assert "<title>Test Preview</title>" in preview
    assert "katex.render" in preview
    assert 'output: "html"' in preview
    assert ".katex-mathml {" in preview
    assert "decodeHTMLEntities" in preview
    assert "<p>Hello world</p>" in preview


def test_build_preview_html_unescapes_math_entities() -> None:
    body = '<p><math-renderer class="js-inline-math">$x &amp;gt; 0$ and $y &amp;lt; 1$ and $a &amp;amp; b$</math-renderer></p>'
    preview = build_preview_html(body, title="Math Preview")
    assert "$x &gt; 0$ and $y &lt; 1$ and $a &amp; b$" in preview
    assert "&amp;gt;" not in preview
    assert "&amp;lt;" not in preview


def test_verify_markdown_clean() -> None:
    clean_html = '<p><math-renderer class="js-inline-math">$a + b$</math-renderer></p>'
    with patch("gfm_math_lint.verifier.render_gfm", return_value=clean_html):
        rendered, issues = verify_markdown("$a + b$", "sample.md")
        assert rendered == clean_html
        assert len(issues) == 0


def test_cmd_verify_clean(tmp_path: Path) -> None:
    doc = tmp_path / "clean.md"
    doc.write_text("# Clean\n\n$x = y$\n", encoding="utf-8")
    clean_html = '<p><math-renderer class="js-inline-math">$x = y$</math-renderer></p>'

    args = argparse.Namespace(
        paths=[str(doc)],
        token=None,
        html=None,
        browser=False,
        format="text",
    )

    with patch("gfm_math_lint.verifier.render_gfm", return_value=clean_html):
        code = cmd_verify(args)
        assert code == 0


def test_cmd_verify_violations(tmp_path: Path) -> None:
    doc = tmp_path / "broken.md"
    doc.write_text("# Broken\n\n$0.759$dB\n", encoding="utf-8")
    broken_html = "<p>Broken: $0.759$dB</p>"

    args = argparse.Namespace(
        paths=[str(doc)],
        token=None,
        html=None,
        browser=False,
        format="text",
    )

    with patch("gfm_math_lint.verifier.render_gfm", return_value=broken_html):
        code = cmd_verify(args)
        assert code == 1


def test_cmd_verify_html_export(tmp_path: Path) -> None:
    doc = tmp_path / "doc.md"
    doc.write_text("$x$\n", encoding="utf-8")
    out_html = tmp_path / "out.html"
    clean_html = '<p><math-renderer class="js-inline-math">$x$</math-renderer></p>'

    args = argparse.Namespace(
        paths=[str(doc)],
        token=None,
        html=str(out_html),
        browser=False,
        format="text",
    )

    with patch("gfm_math_lint.verifier.render_gfm", return_value=clean_html):
        code = cmd_verify(args)
        assert code == 0
        assert out_html.exists()
        assert "katex.render" in out_html.read_text(encoding="utf-8")


def test_open_in_browser() -> None:
    with patch("webbrowser.open") as mock_open:
        temp_path = open_in_browser("<p>Test math</p>", title="Unit Test Browser")
        try:
            assert temp_path.exists()
            assert "katex.render" in temp_path.read_text(encoding="utf-8")
            assert mock_open.called
            opened_url = mock_open.call_args[0][0]
            assert opened_url.startswith("file://")
            assert opened_url == temp_path.resolve().as_uri()
        finally:
            if temp_path.exists():
                temp_path.unlink()


def test_validator_buffered_split_delimiters() -> None:
    # Delimiters split across inline formatting tags inside block containers
    html_p = "<p>Split $$<em>formula</em>$$ leak</p>"
    v1 = GFMHTMLValidator("test.md")
    v1.feed(html_p)
    v1.close()
    assert any(i.category == "unrendered-math" and "$$formula$$" in i.message for i in v1.issues)

    html_li = "<li>Item with $<strong>x = 1</strong>$ leak</li>"
    v2 = GFMHTMLValidator("test.md")
    v2.feed(html_li)
    v2.close()
    assert any(i.category == "unrendered-math" and "$x = 1$" in i.message for i in v2.issues)

    html_td = "<td>Cell $$<span>alpha</span>$$ broken</td>"
    v3 = GFMHTMLValidator("test.md")
    v3.feed(html_td)
    v3.close()
    assert any(i.category == "unrendered-math" and "$$alpha$$" in i.message for i in v3.issues)

    html_quote = "<blockquote>Quote $<em>z</em>$ leak</blockquote>"
    v4 = GFMHTMLValidator("test.md")
    v4.feed(html_quote)
    v4.close()
    assert any(i.category == "unrendered-math" and "$z$" in i.message for i in v4.issues)

    # Negative control: code span with dollar should not trigger unrendered-math
    html_code = "<p>Run command <code>$var</code> in bash</p>"
    v5 = GFMHTMLValidator("test.md")
    v5.feed(html_code)
    v5.close()
    assert len(v5.issues) == 0


def test_validator_pseudo_code_stacking_positive() -> None:
    expected_msg = (
        "Formula contains code function composition in math delimiters; "
        "causes vertical MathML stacking in environments without KaTeX CSS."
    )

    # 1. MathML with consecutive <mi> elements
    html1 = '<p><math-renderer class="js-inline-math"><math><mi>f</mi><mi>o</mi><mi>o</mi><mo>(</mo><mi>b</mi><mi>a</mi><mi>r</mi><mo>(</mo><mi>x</mi><mo>)</mo><mo>)</mo></math></math-renderer></p>'
    v1 = GFMHTMLValidator("test.md")
    v1.feed(html1)
    v1.close()
    assert len(v1.issues) == 1
    assert v1.issues[0].category == "pseudo-code-stacking"
    assert v1.issues[0].message == expected_msg

    # 2. MathML with multi-letter <mi> identifiers
    html2 = '<p><math-renderer class="js-inline-math"><math><mi>foo</mi><mo>(</mo><mi>bar</mi><mo>(</mo><mi>x</mi><mo>)</mo><mo>)</mo></math></math-renderer></p>'
    v2 = GFMHTMLValidator("test.md")
    v2.feed(html2)
    v2.close()
    assert len(v2.issues) == 1
    assert v2.issues[0].category == "pseudo-code-stacking"

    # 3. Raw TeX inline formula
    html3 = '<p><math-renderer class="js-inline-math">$calculate_total(get_items(order))$</math-renderer></p>'
    v3 = GFMHTMLValidator("test.md")
    v3.feed(html3)
    v3.close()
    assert len(v3.issues) == 1
    assert v3.issues[0].category == "pseudo-code-stacking"

    # 4. Raw TeX display formula
    html4 = '<p><math-renderer class="js-display-math">$$funcA(funcB(x))$$</math-renderer></p>'
    v4 = GFMHTMLValidator("test.md")
    v4.feed(html4)
    v4.close()
    assert len(v4.issues) == 1
    assert v4.issues[0].category == "pseudo-code-stacking"

    # 5. TeX with \\text{...} wrappers
    html5 = '<p><math-renderer class="js-inline-math">$\\text{fix}(\\text{fix}(c))$</math-renderer></p>'
    v5 = GFMHTMLValidator("test.md")
    v5.feed(html5)
    v5.close()
    assert len(v5.issues) == 1
    assert v5.issues[0].category == "pseudo-code-stacking"


def test_validator_pseudo_code_stacking_negative_controls() -> None:
    cases = [
        # Standard trigonometric / math functions
        '<p><math-renderer class="js-inline-math">$\\sin(x)$</math-renderer></p>',
        '<p><math-renderer class="js-inline-math">$\\log(x)$</math-renderer></p>',
        '<p><math-renderer class="js-inline-math">$\\sin(\\log(x))$</math-renderer></p>',
        '<p><math-renderer class="js-inline-math">$\\cos(x) + \\tan(x)$</math-renderer></p>',
        # Single-letter functions
        '<p><math-renderer class="js-inline-math">$f(x)$</math-renderer></p>',
        '<p><math-renderer class="js-inline-math">$f(g(x))$</math-renderer></p>',
        # Polynomials
        '<p><math-renderer class="js-inline-math">$x^2 + 2x + 1$</math-renderer></p>',
        '<p><math-renderer class="js-inline-math">$P(x) = a x^2 + b x + c$</math-renderer></p>',
        # Sub/superscript notation
        '<p><math-renderer class="js-inline-math">$x_i + x^2$</math-renderer></p>',
        '<p><math-renderer class="js-inline-math">$a_1 + a_2 + a_3$</math-renderer></p>',
        '<p><math-renderer class="js-inline-math"><math><msub><mi>x</mi><mi>i</mi></msub></math></math-renderer></p>',
        '<p><math-renderer class="js-inline-math"><math><msup><mi>x</mi><mn>2</mn></msup></math></math-renderer></p>',
        # Integrals, fractions, summations
        '<p><math-renderer class="js-inline-math">$\\int f(x) dx$</math-renderer></p>',
        '<p><math-renderer class="js-inline-math">$\\frac{a}{b}$</math-renderer></p>',
        '<p><math-renderer class="js-inline-math">$\\frac{f(x)}{g(x)}$</math-renderer></p>',
        '<p><math-renderer class="js-inline-math">$\\sum_{i=1}^n x_i$</math-renderer></p>',
    ]
    for html in cases:
        validator = GFMHTMLValidator("test.md")
        validator.feed(html)
        validator.close()
        assert len(validator.issues) == 0, f"False positive on: {html}"


def test_verify_markdown_stdout(capsys: pytest.CaptureFixture[str]) -> None:
    html = "<p><math-renderer>$x$</math-renderer></p>"
    with patch("gfm_math_lint.verifier.render_gfm", return_value=html):
        rendered, issues = verify_markdown("$x$", "test.md", stdout=True)
        assert rendered == html
        assert len(issues) == 0
        captured = capsys.readouterr()
        assert captured.out == html + "\n"


def test_verify_file_stdout(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    doc = tmp_path / "test.md"
    doc.write_text("$x$\n", encoding="utf-8")
    html = "<p><math-renderer>$x$</math-renderer></p>"
    with patch("gfm_math_lint.verifier.render_gfm", return_value=html):
        rendered, issues = verify_file(doc, stdout=True)
        assert rendered == html
        assert len(issues) == 0
        captured = capsys.readouterr()
        assert captured.out == html + "\n"


def test_cmd_verify_stdin_clean(capsys: pytest.CaptureFixture[str]) -> None:
    clean_html = '<p><math-renderer class="js-inline-math">$x = y$</math-renderer></p>'
    args = argparse.Namespace(
        paths=["-"],
        token=None,
        html=None,
        browser=False,
        stdout=False,
        format="text",
    )
    with (
        patch("sys.stdin.read", return_value="$x = y$\n"),
        patch("gfm_math_lint.verifier.render_gfm", return_value=clean_html),
    ):
        code = cmd_verify(args)
        assert code == 0
        captured = capsys.readouterr()
        assert "Auditing <stdin>" in captured.out
        assert "0 rendering anomalies detected" in captured.out


def test_cmd_verify_stdin_violations(capsys: pytest.CaptureFixture[str]) -> None:
    broken_html = "<p>Broken: $0.759$dB</p>"
    args = argparse.Namespace(
        paths=["-"],
        token=None,
        html=None,
        browser=False,
        stdout=False,
        format="text",
    )
    with (
        patch("sys.stdin.read", return_value="$0.759$dB\n"),
        patch("gfm_math_lint.verifier.render_gfm", return_value=broken_html),
    ):
        code = cmd_verify(args)
        assert code == 1
        captured = capsys.readouterr()
        assert "<stdin>: [unrendered-math]" in captured.out
        assert "Verification failed" in captured.err


def test_cmd_verify_stdin_conflicting_paths(capsys: pytest.CaptureFixture[str]) -> None:
    args = argparse.Namespace(
        paths=["-", "file.md"],
        token=None,
        html=None,
        browser=False,
        stdout=False,
        format="text",
    )
    code = cmd_verify(args)
    assert code == 2
    captured = capsys.readouterr()
    assert "Cannot combine stdin ('-') with file paths." in captured.err


def test_cmd_verify_stdin_read_error(capsys: pytest.CaptureFixture[str]) -> None:
    args = argparse.Namespace(
        paths=["-"],
        token=None,
        html=None,
        browser=False,
        stdout=False,
        format="text",
    )
    with patch("sys.stdin.read", side_effect=OSError("Read failure")):
        code = cmd_verify(args)
        assert code == 2
        captured = capsys.readouterr()
        assert "Error reading stdin" in captured.err


def test_cmd_verify_stdout_streams_raw_html_only(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    doc = tmp_path / "doc.md"
    doc.write_text("$x$\n", encoding="utf-8")
    rendered_html = '<p><math-renderer class="js-inline-math">$x$</math-renderer></p>'

    args = argparse.Namespace(
        paths=[str(doc)],
        token=None,
        html=None,
        browser=False,
        stdout=True,
        format="text",
    )
    with patch("gfm_math_lint.verifier.render_gfm", return_value=rendered_html):
        code = cmd_verify(args)
        assert code == 0
        captured = capsys.readouterr()
        # stdout must ONLY have rendered HTML stream
        assert captured.out.strip() == rendered_html.strip()
        # Diagnostics must go to stderr
        assert "Auditing 1 file(s)" in captured.err
        assert "0 rendering anomalies detected" in captured.err


def test_cmd_verify_stdin_render_exception(capsys: pytest.CaptureFixture[str]) -> None:
    args = argparse.Namespace(
        paths=["-"],
        token=None,
        html=None,
        browser=False,
        stdout=False,
        format="text",
    )
    with (
        patch("sys.stdin.read", return_value="$x$\n"),
        patch("gfm_math_lint.verifier.render_gfm", side_effect=RuntimeError("API timeout")),
    ):
        code = cmd_verify(args)
        assert code == 2
        captured = capsys.readouterr()
        assert "Error verifying <stdin>: API timeout" in captured.err


def test_cmd_verify_stdin_html_and_browser(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out_html = tmp_path / "stdin_out.html"
    args = argparse.Namespace(
        paths=["-"],
        token=None,
        html=str(out_html),
        browser=True,
        stdout=False,
        format="text",
    )
    clean_html = '<p><math-renderer class="js-inline-math">$x$</math-renderer></p>'
    with (
        patch("sys.stdin.read", return_value="$x$\n"),
        patch("gfm_math_lint.verifier.render_gfm", return_value=clean_html),
        patch("webbrowser.open"),
    ):
        code = cmd_verify(args)
        assert code == 0
        assert out_html.exists()
        captured = capsys.readouterr()
        assert "Wrote rendered HTML preview" in captured.out
        assert "Opened preview in browser" in captured.out


def test_cmd_verify_stdout_with_github_format(capsys: pytest.CaptureFixture[str]) -> None:
    broken_html = "<p>Broken: $0.759$dB</p>"
    args = argparse.Namespace(
        paths=["-"],
        token=None,
        html=None,
        browser=False,
        stdout=True,
        format="github",
    )
    with (
        patch("sys.stdin.read", return_value="$0.759$dB\n"),
        patch("gfm_math_lint.verifier.render_gfm", return_value=broken_html),
    ):
        code = cmd_verify(args)
        assert code == 1
        captured = capsys.readouterr()
        # stdout must ONLY contain rendered HTML
        assert captured.out.strip() == broken_html.strip()
        # Github annotation must go to stderr
        assert "::error file=<stdin>,title=unrendered-math" in captured.err
        assert "Verification failed" in captured.err
