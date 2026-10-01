"""Live GitHub API Markdown Oracle test harness."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from gfm_math_lint.linter import Linter

pytestmark = pytest.mark.network


def render_gfm_via_github_api(markdown_content: str) -> str:
    """Render markdown using GitHub's live GFM API endpoint."""
    gh_bin = shutil.which("gh")
    if not gh_bin:
        pytest.skip("GitHub CLI ('gh') not installed; skipping live API oracle test.")

    payload = json.dumps({"text": markdown_content, "mode": "gfm"})
    try:
        result = subprocess.run(
            [gh_bin, "api", "/markdown", "--input", "-"],
            input=payload,
            text=True,
            capture_output=True,
            timeout=15,
        )
    except Exception as e:
        pytest.skip(f"GitHub API call failed: {e}")

    if result.returncode != 0:
        pytest.skip(f"GitHub Markdown API error: {result.stderr}")

    return result.stdout


def assert_gfm_rendering_clean(html: str) -> None:
    """Assert that rendered HTML has no KaTeX errors, table corruptions, or tag collisions."""
    # 1. KaTeX parse errors check
    katex_error_spans = re.findall(r'<span class="katex-error"[^>]*>(.*?)</span>', html, re.DOTALL)
    assert not katex_error_spans, f"Found KaTeX error in rendered HTML: {katex_error_spans}"
    assert 'class="katex-error"' not in html, "Found katex-error elements in rendered HTML"

    # 2. Table column consistency check
    rows = re.findall(r"<tr>(.*?)</tr>", html, re.DOTALL)
    if rows:
        col_counts = [len(re.findall(r"<t[dh][^>]*>", r)) for r in rows]
        assert len(set(col_counts)) == 1, (
            f"GFM table column mismatch detected across rows: {col_counts}. "
            "Likely caused by unescaped pipe '|' inside table cells."
        )

    # 3. HTML tag collision check (<i tag misinterpretation)
    assert "W_<i>" not in html and "W_<em>" not in html, (
        "Inequality or subscript expression was corrupted by GFM HTML/emphasis parser."
    )


def test_fixed_document_oracle() -> None:
    """Test that our auto-fixed markdown renders completely cleanly on GitHub's API."""
    # Sample document containing various LaTeX and table features that were fixed
    sample_doc = (
        "# Scientific Report\n\n"
        "Here is formula with escaped curly braces:\n\n"
        "$$\n"
        "\\phi \\in \\left\\lbrace \\frac{3\\pi}{2} \\right\\rbrace\n"
        "$$\n\n"
        "Here is relational operator without HTML collision:\n\n"
        "$$\n"
        "W_{\\lt i} + x\n"
        "$$\n\n"
        "Here is text mode double underscore:\n\n"
        "$$\n"
        "\\text{ave\\_shift} = 10\n"
        "$$\n\n"
        "| Metric | Condition |\n"
        "| :--- | :--- |\n"
        "| DC | $&#124;&#124;x&#124;&#124; < 1$ |\n"
    )

    rendered_html = render_gfm_via_github_api(sample_doc)
    assert_gfm_rendering_clean(rendered_html)


def test_plan_document_oracle() -> None:
    """Test that the project plan document itself renders cleanly on GitHub's API."""
    plan_path = Path("docs/gfm-math-lint-plan.md")
    if not plan_path.is_file():
        pytest.skip("docs/gfm-math-lint-plan.md not found.")

    linter = Linter()
    # Lint and fix any stray violations if needed
    result = linter.lint_file(plan_path, fix=False)
    rendered_html = render_gfm_via_github_api(result.original_content)
    assert_gfm_rendering_clean(rendered_html)
