"""Unit tests for GFM HTML verification engine."""

from __future__ import annotations

import argparse
from typing import TYPE_CHECKING
from unittest.mock import patch

from gfm_math_lint.cli import cmd_verify
from gfm_math_lint.verifier import (
    GFMHTMLValidator,
    build_preview_html,
    open_in_browser,
    verify_markdown,
)

if TYPE_CHECKING:
    from pathlib import Path


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
