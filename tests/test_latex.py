"""Tests for zero-dependency LaTeX structural validator and local KaTeX runner."""

from __future__ import annotations

import json
import subprocess
from unittest.mock import patch

from gfm_math_lint.latex import (
    _get_node_env,
    is_katex_available,
    run_local_katex_verification,
    validate_latex,
)


def test_validate_latex_clean_expressions() -> None:
    clean_cases = [
        (r"x^2 + y_1^2 = r^2", False),
        (r"\sum_{i=1}^n x_{i, j} \le \frac{a}{b}", False),
        (r"\left\lbrace \frac{1}{2} \right\rbrace", False),
        (r"x \leftarrow y \rightarrow z", False),
        ("\\begin{aligned}\na &= b \\\\\nc &= d\n\\end{aligned}", True),
        (r"\begin{bmatrix} 1 & 2 \\ 3 & 4 \end{bmatrix}", True),
        (r"\text{escaped\_underscore} + \mathrm{x_1}", False),
        (r"\{a, b\} \text{ and } \left. x \right|", False),
    ]
    for tex, display in clean_cases:
        assert validate_latex(tex, display=display) == [], f"Unexpected issues on: {tex}"


def test_validate_latex_unbalanced_braces() -> None:
    issues_open = validate_latex(r"\frac{a}{b")
    assert any(i.category == "unbalanced-braces" for i in issues_open)

    issues_close = validate_latex(r"x + y}")
    assert any(i.category == "unbalanced-braces" for i in issues_close)

    # \\} is a linebreak followed by a closing brace, NOT an escaped brace
    assert validate_latex(r"\text{a\\}") == []

    # Escaped \{ and \} do not affect brace balance
    assert validate_latex(r"\{x + y\}") == []


def test_validate_latex_comment_hides_closing_brace() -> None:
    issues = validate_latex("x_{86.5%}\n", display=False)
    assert any(i.category == "unbalanced-braces" for i in issues)


def test_validate_latex_environments() -> None:
    unclosed = validate_latex(r"\begin{bmatrix} 1 & 2", display=True)
    assert any(i.category == "unmatched-environment" for i in unclosed)

    unexpected_end = validate_latex(r"x + y \end{aligned}", display=True)
    assert any(i.category == "unmatched-environment" for i in unexpected_end)

    mismatched = validate_latex(r"\begin{bmatrix} 1 \end{aligned}", display=True)
    assert any(i.category == "unmatched-environment" and "Mismatched" in i.message for i in mismatched)


def test_validate_latex_left_right_delimiters() -> None:
    unclosed_left = validate_latex(r"\left( x + y")
    assert any(i.category == "unmatched-delimiter" for i in unclosed_left)

    unexpected_right = validate_latex(r"x + y \right)")
    assert any(i.category == "unmatched-delimiter" for i in unexpected_right)

    missing_delim = validate_latex(r"\left x + y \right.")
    assert any(i.category == "unmatched-delimiter" for i in missing_delim)


def test_validate_latex_text_underscore_and_scripts() -> None:
    text_us = validate_latex(r"\text{sensor_out}")
    assert any(i.category == "latex-syntax" and "\\text" in i.message for i in text_us)

    # \\_ inside \text is a linebreak followed by raw '_' -> still invalid
    double_bs_us = validate_latex(r"\text{sensor\\_out}")
    assert any(i.category == "latex-syntax" for i in double_bs_us)

    dangling_sub = validate_latex(r"x_")
    assert any(i.category == "latex-syntax" and "Dangling" in i.message for i in dangling_sub)

    double_sub = validate_latex(r"x_1_2")
    assert any(i.category == "latex-syntax" and "Double subscript" in i.message for i in double_sub)

    double_sup = validate_latex(r"x^a^b")
    assert any(i.category == "latex-syntax" and "Double superscript" in i.message for i in double_sup)

    missing_frac = validate_latex(r"\frac{1}")
    assert any(i.category == "latex-syntax" and "\\frac" in i.message for i in missing_frac)


def test_katex_runner_missing_node() -> None:
    with patch("shutil.which", return_value=None):
        assert is_katex_available() is False
        assert run_local_katex_verification([("x + 1", False)]) == []


def test_katex_runner_parse_error_and_strict_warnings() -> None:
    fake_output = json.dumps(
        [
            {"math": r"\text{µm}", "display": False, "error": "", "warnings": ["unknownSymbol: Unrecognized 'µ'"]},
            {"math": r"\bad{", "display": True, "error": "ParseError: Expected '}'", "warnings": []},
        ]
    ).encode("utf-8")
    completed = subprocess.CompletedProcess(args=["node"], returncode=0, stdout=fake_output, stderr=b"")

    with (
        patch("shutil.which", return_value="/usr/bin/node"),
        patch("subprocess.run", return_value=completed),
    ):
        diags_strict = run_local_katex_verification([(r"\text{µm}", False), (r"\bad{", True)], strict_warnings=True)
        assert len(diags_strict) == 2
        assert diags_strict[0].warnings == ["unknownSymbol: Unrecognized 'µ'"]
        assert diags_strict[1].error_message == "ParseError: Expected '}'"

        diags_nonstrict = run_local_katex_verification([(r"\text{µm}", False), (r"\bad{", True)], strict_warnings=False)
        assert len(diags_nonstrict) == 1
        assert diags_nonstrict[0].error_message == "ParseError: Expected '}'"


def test_validate_latex_nested_text_inside_math_and_delimiters() -> None:
    # Nested \text{id} inside $...$ inside \text{...} must not reset outer math state
    assert validate_latex(r"\text{let $f(x) = \text{id} + x_1$}") == []
    # \lbrack / \rbrack and \lt / \gt are valid \left / \right delimiters
    assert validate_latex(r"\left\lbrack 0, 1 \right\rbrack + \left\lt x \right\gt") == []
    # Comments before macro/script arguments
    assert validate_latex("\\frac{1} % comment\n {2} + x_ % comment\n 2") == []


def test_validate_latex_compound_double_subscripts_and_node_pathsep() -> None:
    issues_compound = validate_latex(r"x_1^2_3")
    assert any(i.category == "latex-syntax" and "Double subscript" in i.message for i in issues_compound)

    issues_nested_group = validate_latex(r"a_{b_1}_2")
    assert any(i.category == "latex-syntax" and "Double subscript" in i.message for i in issues_nested_group)

    with patch("os.pathsep", ";"):
        env = _get_node_env()
        assert ";" in env["NODE_PATH"]
