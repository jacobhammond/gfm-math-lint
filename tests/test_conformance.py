"""Tests for the Conformance Crucible benchmark infrastructure, oracles, and runner."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from conformance.extractor import extract_math_blocks
from conformance.oracles.github_oracle import (
    BufferedGFMVerifier,
    render_gfm_offline_or_online,
    verify_rendered_gfm,
)
from conformance.oracles.katex_oracle import (
    is_katex_available,
    run_local_katex_verification,
)
from conformance.runner import (
    ConformanceRunner,
    CrucibleScorecard,
    StageFailure,
)
from conformance.runner import (
    main as runner_main,
)
from scripts.generate_conformance_matrix import (
    generate_all_synthetic_scenarios,
    generate_diagram_variations,
    generate_display_construct_variations,
    generate_inline_construct_variations,
    generate_list_math_variations,
)


def test_extract_math_blocks() -> None:
    doc = """# Test Document
Inline formula $x + y = z$ and protected backtick $`P_{\\text{ref}}`$.

$$
\\text{SNR} = 10 \\log_{10}(X)
$$

```math
\\frac{A}{B} \\ge 1.0
```

```python
x = 10
```
"""
    blocks = extract_math_blocks(doc)
    assert len(blocks) == 4
    assert blocks[0] == ("x + y = z", False)
    assert blocks[1] == ("P_{\\text{ref}}", False)
    assert blocks[2] == ("\\text{SNR} = 10 \\log_{10}(X)", True)
    assert blocks[3] == ("\\frac{A}{B} \\ge 1.0", True)


def test_extract_math_blocks_empty() -> None:
    assert extract_math_blocks("") == []
    assert extract_math_blocks("# Just a title\nNo math here.\n") == []


def test_katex_oracle_valid() -> None:
    if not is_katex_available():
        return
    errors = run_local_katex_verification([("x^2 + y^2 = r^2", True), ("\\alpha + \\beta = 1", False)])
    assert errors == []


def test_katex_oracle_syntax_error() -> None:
    if not is_katex_available():
        return
    # Snake_case inside \text crashes KaTeX with Expected 'EOF', got '_'
    errors = run_local_katex_verification([("\\text{invalid_snake_case}", False)])
    assert len(errors) == 1
    assert "Expected 'EOF', got '_'" in errors[0].error_message
    assert errors[0].display_mode is False


def test_katex_oracle_empty_blocks() -> None:
    assert run_local_katex_verification([]) == []


def test_github_oracle_clean_html() -> None:
    html = "<p>Standard text with <math-renderer>$x = 1$</math-renderer>.</p>"
    anomalies = verify_rendered_gfm(html)
    assert anomalies == []


def test_github_oracle_unrendered_display_math() -> None:
    html = "<p>Prose containing raw $$ delimiter outside math renderer.</p>"
    anomalies = verify_rendered_gfm(html)
    assert any("Unrendered '$$' delimiter" in a for a in anomalies)


def test_github_oracle_tag_pollution_in_math_renderer() -> None:
    html = "<math-renderer>\\text{SNR}<em>{meas}</em> = 10</math-renderer>"
    verifier = BufferedGFMVerifier()
    verifier.feed(html)
    verifier.close()
    assert any("Markdown syntax collision" in a for a in verifier.anomalies)


def test_github_oracle_table_column_mismatch() -> None:
    html = "<table><tr><td>A</td><td>B</td></tr><tr><td>A</td><td>B</td><td>C</td></tr></table>"
    anomalies = verify_rendered_gfm(html)
    assert any("Table column count mismatch" in a for a in anomalies)


def test_github_oracle_mermaid_literal_newline() -> None:
    html = '<pre><code class="language-mermaid">graph TD\n    A[Channel 1\\nActive] --> B(Complete)\n</code></pre>'
    anomalies = verify_rendered_gfm(html)
    assert any("Literal '\\n' sequence found in Mermaid node label" in a for a in anomalies)


def test_render_gfm_offline_fallback() -> None:
    md = "# Title\nProse text with $x = 1$.\n\n$$\ny = 2\n$$"
    html = render_gfm_offline_or_online(md, offline=True)
    assert "<p>" in html
    assert "<math-renderer>" in html


def test_stage_failure_opaque_formatting() -> None:
    failure = StageFailure(
        scenario_id="syn_042",
        stage=2,
        stage_name="Fix Convergence",
        rule_id="GFM-M02",
        structural_description="Indented display math in bullet list",
        failure_detail="Did not converge cleanly",
    )
    opaque = failure.to_opaque_summary()
    assert "syn_042" in opaque
    assert "Stage 2 (Fix Convergence)" in opaque
    assert "GFM-M02" in opaque
    assert "Indented display math in bullet list" in opaque
    # Must not contain raw markdown formatting blocks
    assert "```markdown" not in opaque


def test_crucible_scorecard_metrics() -> None:
    scorecard = CrucibleScorecard(
        total_scenarios=10,
        stage_1_passed=8,
        stage_2_passed=9,
        stage_3_passed=10,
        stage_4_passed=7,
        all_stages_passed=6,
    )
    assert scorecard.detection_rate == 80.0
    assert scorecard.convergence_rate == 90.0
    assert scorecard.katex_rate == 100.0
    assert scorecard.github_rate == 70.0
    assert scorecard.final_score == 60.0
    assert scorecard.gating_pass is False

    text_report = scorecard.format_text()
    assert "Conformance Crucible Scorecard" in text_report
    assert "60.0% [GATING FAIL]" in text_report

    json_dict = scorecard.to_json_dict()
    assert json_dict["total_scenarios"] == 10
    assert json_dict["final_score"] == 60.0


def test_matrix_generator_scenario_counts() -> None:
    all_scenarios = generate_all_synthetic_scenarios()
    assert len(all_scenarios) >= 120

    list_math = generate_list_math_variations()
    assert len(list_math) == 16  # 4 indents * 2 delimiters * 2 blank lines (Blueprint 3)

    inline_vars = generate_inline_construct_variations()
    assert len(inline_vars) >= 60

    display_vars = generate_display_construct_variations()
    assert len(display_vars) >= 30

    diagram_vars = generate_diagram_variations()
    assert len(diagram_vars) >= 12


def test_conformance_runner_execution(tmp_path: Path) -> None:
    # Setup miniature test corpus
    corpus_dir = tmp_path / "corpus"
    corpus_dir.mkdir()
    syn_dir = corpus_dir / "synthetic"
    syn_dir.mkdir()

    # Clean file
    clean_file = syn_dir / "test_clean.md"
    clean_file.write_text("# Clean\n\nSimple prose without errors.\n", encoding="utf-8")

    manifest = corpus_dir / "manifest.yaml"
    manifest_data = {
        "version": "1.0",
        "scenarios": [
            {
                "id": "t_001",
                "path": "synthetic/test_clean.md",
                "category": "synthetic",
                "description": "Miniature clean test scenario",
                "expected_rules": [],
                "structural_tags": ["test"],
            }
        ],
    }
    with manifest.open("w", encoding="utf-8") as f:
        json.dump(manifest_data, f)

    runner = ConformanceRunner(
        corpus_dir=corpus_dir,
        manifest_path=manifest,
        offline=True,
    )
    scorecard = runner.run()
    assert scorecard.total_scenarios == 1
    assert scorecard.all_stages_passed == 1
    assert scorecard.gating_pass is True


def test_runner_cli_help() -> None:
    with patch("sys.argv", ["conformance.runner", "--help"]):
        try:
            runner_main()
        except SystemExit as exc:
            assert exc.code == 0


def test_runner_cli_regressions_category() -> None:
    manifest_path = Path("conformance/corpus/manifest.yaml")
    if not manifest_path.exists():
        return
    with patch("sys.argv", ["conformance.runner", "--category", "regressions", "--offline", "--format", "json"]):
        exit_code = runner_main()
        assert exit_code == 0
