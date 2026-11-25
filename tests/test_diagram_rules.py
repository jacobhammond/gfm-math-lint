"""Unit tests for GFM diagram rules (GFM-D01 through GFM-D05)."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

from gfm_math_lint.fixer import apply_edits
from gfm_math_lint.rules.diagram_rules import (
    RuleD01,
    RuleD02,
    RuleD03,
    RuleD04,
    RuleD05,
    RuleD06,
    build_puppeteer_config,
    render_mermaid_previews,
)
from gfm_math_lint.tokenizer import scan_document_zones

if TYPE_CHECKING:
    from gfm_math_lint.rules.base import Rule


def check_and_fix(rule: Rule, content: str) -> tuple[str, int]:
    """Run a rule on content, apply its edits, and return (fixed_content, violation_count)."""
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

    fixed2, count2 = check_and_fix(rule, fixed)
    assert count2 == 0
    assert fixed2 == fixed


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


def test_rule_d01_mermaid_bang_arrow() -> None:
    rule = RuleD01()
    good = '```mermaid\ngraph TD\n    A["Node A"] --!> B["Node B"]\n```\n'
    lines = good.splitlines(keepends=True)
    zones = scan_document_zones(lines)
    assert len(rule.check(lines, zones)) == 0

    bad = "```mermaid\ngraph TD\n    Node A --!> Node B\n```\n"
    lines = bad.splitlines(keepends=True)
    zones = scan_document_zones(lines)
    violations = rule.check(lines, zones)
    assert len(violations) == 1
    assert "Node A" in violations[0].message


# ---------------------------------------------------------------------------
# GFM-D03: mermaid-newline-linebreak
# ---------------------------------------------------------------------------


def test_rule_d03_unquoted_and_quoted_labels() -> None:
    rule = RuleD03()
    bad = (
        "```mermaid\n"
        "graph TD\n"
        '    A[Channel 1\\nActive] --> B["Channel 2\\nStandby"]\n'
        "    C(Round\\nNode) --> D((Circle\\nNode))\n"
        "    E{Decision\\nCheck} --> F{{Hex\\nNode}}\n"
        "    subgraph Sub[Cluster\\nZone A]\n"
        '        G -- "Edge\\nLabel" --> H\n'
        "    end\n"
        "```\n"
    )
    expected = (
        "```mermaid\n"
        "graph TD\n"
        '    A[Channel 1<br>Active] --> B["Channel 2<br>Standby"]\n'
        "    C(Round<br>Node) --> D((Circle<br>Node))\n"
        "    E{Decision<br>Check} --> F{{Hex<br>Node}}\n"
        "    subgraph Sub[Cluster<br>Zone A]\n"
        '        G -- "Edge<br>Label" --> H\n'
        "    end\n"
        "```\n"
    )
    assert_idempotent(rule, bad, expected)


def test_rule_d03_multiple_newlines_and_double_backslash() -> None:
    rule = RuleD03()
    bad = '```mermaid\ngraph LR\n    A["Line 1\\nLine 2\\nLine 3"] --> B["Double\\\\nBackslash"]\n```\n'
    expected = '```mermaid\ngraph LR\n    A["Line 1<br>Line 2<br>Line 3"] --> B["Double<br>Backslash"]\n```\n'
    assert_idempotent(rule, bad, expected)


def test_rule_d03_blockquote_and_list_indented_mermaid() -> None:
    rule = RuleD03()
    bad = '- Item:\n  > ```mermaid\n  > graph TD\n  >     A[Line 1\\nLine 2] --> B["Line 3\\nLine 4"]\n  > ```\n'
    expected = '- Item:\n  > ```mermaid\n  > graph TD\n  >     A[Line 1<br>Line 2] --> B["Line 3<br>Line 4"]\n  > ```\n'
    assert_idempotent(rule, bad, expected)


def test_rule_d03_ignores_code_tags_outside_labels_and_non_mermaid() -> None:
    rule = RuleD03()
    clean = (
        "```mermaid\n"
        "graph TD\n"
        '    A["Use <code>\\n</code> for newline"] --> B[Clean<br>Label]\n'
        '    C[\\name\\] --> D["Price $5\\nTax $1"]\n'
        "    %% Comment with \\n outside labels\n"
        "```\n\n"
        "```python\n"
        'msg = "hello\\nworld"\n'
        "```\n"
    )
    # Price $5\nTax $1 SHOULD be fixed while <code>\n</code>, C[\name\], comment, and python are untouched.
    lines = clean.splitlines(keepends=True)
    zones = scan_document_zones(lines)
    violations = rule.check(lines, zones)
    assert len(violations) == 1
    assert violations[0].line == 4
    fixed = apply_edits(clean, [v.edit for v in violations if v.edit is not None])
    assert 'A["Use <code>\\n</code> for newline"]' in fixed
    assert "C[\\name\\]" in fixed
    assert 'D["Price $5<br>Tax $1"]' in fixed
    assert 'msg = "hello\\nworld"' in fixed


def test_rule_d03_preserves_latex_nu_in_math() -> None:
    rule = RuleD03()
    content = '```mermaid\ngraph TD\n    A["$\\nu = 5$"] --> B["$\\nabla T$"]\n```\n'
    lines = content.splitlines(keepends=True)
    zones = scan_document_zones(lines)
    assert len(rule.check(lines, zones)) == 0


# ---------------------------------------------------------------------------
# GFM-D04: mermaid-label-special-chars
# ---------------------------------------------------------------------------


def test_rule_d04_internal_pipe_in_edge_label_reg18() -> None:
    rule = RuleD04()
    bad = '```mermaid\ngraph LR\n    A -->|"U = |a|²"| B\n```\n'
    lines = bad.splitlines(keepends=True)
    zones = scan_document_zones(lines)
    violations = rule.check(lines, zones)
    assert len(violations) == 1
    assert violations[0].rule_id == "GFM-D04"
    assert violations[0].severity == "error"
    assert violations[0].edit is None
    assert '-- "..." -->' in violations[0].message


def test_rule_d04_unquoted_label_special_chars_autofix() -> None:
    rule = RuleD04()
    bad = (
        "```mermaid\n"
        "graph TD\n"
        "    A[Value (dB)] --> B[Set {1, 2}]\n"
        "    C[x | y] --> D[(Postgres (v16))]\n"
        "    E[[Process (fast)]]\n"
        "```\n"
    )
    expected = (
        "```mermaid\n"
        "graph TD\n"
        '    A["Value (dB)"] --> B["Set {1, 2}"]\n'
        '    C["x | y"] --> D[("Postgres (v16)")]\n'
        '    E[["Process (fast)"]]\n'
        "```\n"
    )
    assert_idempotent(rule, bad, expected)


def test_rule_d04_blockquote_indented_unquoted_label() -> None:
    rule = RuleD04()
    bad = "  > ```mermaid\n  > graph TD\n  >     A[Gain (dB)]\n  > ```\n"
    expected = '  > ```mermaid\n  > graph TD\n  >     A["Gain (dB)"]\n  > ```\n'
    assert_idempotent(rule, bad, expected)


def test_rule_d04_clean_shapes_and_quoted_labels_no_violations() -> None:
    rule = RuleD04()
    good = (
        "```mermaid\n"
        "graph TD\n"
        "    Start(Sensor Init<br>Self-Test) --> Check{Voltages Normal<br>Rail OK?}\n"
        "    Check -->|Yes| Run[Operational<br>Telemetry Active]\n"
        '    Run --> Note["Label (extra)"]\n'
        "    Note --> DB[(Postgres)]\n"
        "    DB --> Sub[[Worker]]\n"
        '    subgraph MA ["Module Alpha"]\n'
        "        Run --> DB\n"
        "    end\n"
        "```\n"
    )
    lines = good.splitlines(keepends=True)
    zones = scan_document_zones(lines)
    assert len(rule.check(lines, zones)) == 0


# ---------------------------------------------------------------------------
# GFM-D05: math-in-mermaid
# ---------------------------------------------------------------------------


def test_rule_d05_inline_math_and_macros_warn_reg19() -> None:
    rule = RuleD05()
    bad = (
        "```mermaid\n"
        "graph TD\n"
        '    A["$\\Delta T$"] --> B["\\alpha + \\beta"]\n'
        '    C["\\frac{1}{\\sqrt{2}} \\text{rad} \\mathrm{s}"]\n'
        '    D["\\gamma \\omega \\mu \\pi \\sigma \\theta \\lambda"]\n'
        "```\n"
    )
    lines = bad.splitlines(keepends=True)
    zones = scan_document_zones(lines)
    violations = rule.check(lines, zones)
    assert len(violations) >= 4
    assert all(v.rule_id == "GFM-D05" for v in violations)
    assert all(v.severity == "warning" for v in violations)
    assert all(v.edit is None for v in violations)
    # Line 3 should have 1 warning for $\Delta T$, plus 2 for \alpha and \beta (not 2 for $\Delta T$ + \Delta)
    line3_violations = [v for v in violations if v.line == 3]
    assert len(line3_violations) == 3


def test_rule_d05_clean_unicode_and_currency_no_violations() -> None:
    rule = RuleD05()
    good = (
        "```mermaid\n"
        "graph TD\n"
        '    A["ΔT"] --> B["α + β"]\n'
        '    C["Cost: $50"] --> D["Total: $100"]\n'
        '    E["Price $5 to $10"] --> F[$5]\n'
        "    %% $\\Delta T$ inside comment\n"
        "```\n\n"
        "Prose math $\\Delta T$ outside Mermaid.\n"
    )
    lines = good.splitlines(keepends=True)
    zones = scan_document_zones(lines)
    assert len(rule.check(lines, zones)) == 0


# ---------------------------------------------------------------------------
# GFM-D06: mermaid-parse & desktop-quiet preview renderer
# ---------------------------------------------------------------------------


def test_rule_d06_skips_when_mmdc_absent() -> None:
    rule = RuleD06()
    content = "```mermaid\ngraph TD\n    A --> B\n```\n"
    lines = content.splitlines(keepends=True)
    zones = scan_document_zones(lines)
    with patch("gfm_math_lint.rules.diagram_rules.find_mmdc_binary", return_value=None):
        assert rule.check(lines, zones) == []


def test_rule_d06_passes_on_zero_exit() -> None:
    import subprocess

    rule = RuleD06()
    content = "```mermaid\ngraph TD\n    A --> B\n```\n"
    lines = content.splitlines(keepends=True)
    zones = scan_document_zones(lines)
    ok_proc = subprocess.CompletedProcess(args=["mmdc"], returncode=0, stdout=b"", stderr=b"")
    with (
        patch("gfm_math_lint.rules.diagram_rules.find_mmdc_binary", return_value="/usr/bin/mmdc"),
        patch("subprocess.run", return_value=ok_proc),
    ):
        assert rule.check(lines, zones) == []


def test_rule_d06_reports_syntax_error_and_skips_browser_missing() -> None:
    import subprocess

    rule = RuleD06()
    content = "```mermaid\ngraph TD\n    A --->|bad|\n```\n\n```mermaid\ngraph LR\n    B --> C\n```\n"
    lines = content.splitlines(keepends=True)
    zones = scan_document_zones(lines)

    syntax_err = subprocess.CompletedProcess(
        args=["mmdc"], returncode=1, stdout=b"", stderr=b"Error: Parse error on line 2\n"
    )
    ok_proc = subprocess.CompletedProcess(args=["mmdc"], returncode=0, stdout=b"", stderr=b"")
    with (
        patch("gfm_math_lint.rules.diagram_rules.find_mmdc_binary", return_value="/usr/bin/mmdc"),
        patch("subprocess.run", side_effect=[syntax_err, ok_proc]),
    ):
        violations = rule.check(lines, zones)
        assert len(violations) == 1
        assert violations[0].rule_id == "GFM-D06"
        assert "Parse error on line 2" in violations[0].message

    # Timeout on first block continues to validate second block
    with (
        patch("gfm_math_lint.rules.diagram_rules.find_mmdc_binary", return_value="/usr/bin/mmdc"),
        patch("subprocess.run", side_effect=[subprocess.TimeoutExpired("mmdc", 30), syntax_err]),
    ):
        violations_after_timeout = rule.check(lines, zones)
        assert len(violations_after_timeout) == 1

    # Browser-missing error breaks immediately without retrying remaining blocks
    browser_err = subprocess.CompletedProcess(
        args=["mmdc"], returncode=1, stdout=b"", stderr=b"Error: Could not find Chrome\n"
    )
    with (
        patch("gfm_math_lint.rules.diagram_rules.find_mmdc_binary", return_value="/usr/bin/mmdc"),
        patch("subprocess.run", return_value=browser_err) as mock_run,
    ):
        assert rule.check(lines, zones) == []
        assert mock_run.call_count == 1


def test_rule_d06_skipped_in_linter_intermediate_fix_passes() -> None:
    from gfm_math_lint.linter import Linter
    from gfm_math_lint.rules.math_rules import RuleM04

    doc = "$ x $\n\n```mermaid\ngraph TD\n    A --> B\n```\n"
    d06 = RuleD06()
    linter = Linter(rules=[RuleM04(), d06])
    with patch.object(d06, "check", return_value=[]) as mock_d06:
        res = linter.lint_string(doc, fix=True)
        assert res.modified is True
        # Called once initially and once on final changed content (NOT in intermediate passes)
        assert mock_d06.call_count == 2


def test_build_puppeteer_config_and_preview_renderer(tmp_path: Path) -> None:
    import subprocess

    cfg = build_puppeteer_config(executable_path="/usr/bin/chrome-headless-shell")
    assert cfg["headless"] == "shell"
    assert cfg["executablePath"] == "/usr/bin/chrome-headless-shell"

    # No mermaid blocks -> returns [] without needing mmdc
    assert render_mermaid_previews("# Plain markdown\n", tmp_path) == []

    md = "```mermaid\ngraph LR\n    A --> B\n```\n"
    ok_proc = subprocess.CompletedProcess(args=["mmdc"], returncode=0, stdout=b"", stderr=b"")
    with (
        patch("gfm_math_lint.rules.diagram_rules.find_mmdc_binary", return_value="/usr/bin/mmdc"),
        patch("subprocess.run", return_value=ok_proc) as mock_run,
    ):
        written = render_mermaid_previews(md, tmp_path / "previews", stem="report")
        assert len(written) == 1
        assert written[0].name == "report_mermaid_01.png"
        env_passed = mock_run.call_args.kwargs["env"]
        assert env_passed["PUPPETEER_SKIP_DOWNLOAD"] == "1"
