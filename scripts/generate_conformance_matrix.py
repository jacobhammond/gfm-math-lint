#!/usr/bin/env python3
"""Synthetic Combinatorial Matrix Generator for GFM Math Lint Conformance Benchmark.

Generates multi-feature Markdown torture scenarios crossing orthogonal axes:
- Containers: root prose, bullet list, nested ordered list, blockquote, table cell, blockquote in list
- Math Constructs: single subscript, dual subscript, logarithmic index, multiline display,
  fractional ratio, register identifier
- Delimiters: inline dollar ($), display dollar ($$), code fence (```math```), backtick math ($`...`$)
- Diagrams: Mermaid flowchart with \\n in node labels, subgraph links, unquoted labels
- Blueprint 3: List-math fuzzer variations crossing indentation, delimiter, and blank lines
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

try:
    import yaml  # type: ignore[import-untyped]
except ImportError:
    import json as _json

    # Minimal YAML dumper fallback if pyyaml is not available
    class _YamlFallback:
        @staticmethod
        def dump(data: Any, stream: Any = None, **kwargs: Any) -> str | None:
            text = _json.dumps(data, indent=2)
            if stream:
                stream.write(text)
                return None
            return text

    yaml = _YamlFallback()


def generate_list_math_variations() -> list[dict[str, Any]]:
    """Generate combinatorial variations crossing list depth, blank lines, and math delimiters (Blueprint 3)."""
    variations: list[dict[str, Any]] = []
    indents = [0, 2, 4, 6]
    delimiters = [("$$", "$$"), ("```math", "```")]

    for indent in indents:
        pad = " " * indent
        for open_delim, close_delim in delimiters:
            for blank_above in [True, False]:
                blank = "\n" if blank_above else ""
                delim_type = "display_dollar" if open_delim == "$$" else "code_fence"
                delim_tag = open_delim[:3].replace("`", "fence")
                tag = f"list_math_indent_{indent}_{delim_tag}_blank_{blank_above}"

                md = (
                    f"# List Math Test: Indent {indent}, Delim {open_delim}, Blank Above: {blank_above}\n\n"
                    f"1. **Primary Item:**\n"
                    f"   * Sub-bullet header:{blank}\n"
                    f"{pad}{open_delim}\n"
                    f"{pad}\\text{{SNR}}_{{\\mathrm{{meas}}}} = 10 \\log_{{10}}(X) \\ge 20\\text{{ dB}}\n"
                    f"{pad}{close_delim}\n"
                )

                expected_rules: list[str] = []
                # In lists, indented $$ is GFM-M02 violation; indented ```math is valid/clean in GFM
                if delim_type == "display_dollar" and indent > 0:
                    expected_rules.append("GFM-M02")

                variations.append(
                    {
                        "filename_slug": tag,
                        "title": f"List Math Indent {indent} with {open_delim}",
                        "content": md,
                        "expected_rules": expected_rules,
                        "structural_tags": [
                            "container:nested_list",
                            f"indent:{indent}",
                            f"delimiter:{delim_type}",
                            f"blank_above:{blank_above}",
                        ],
                    }
                )
    return variations


def generate_inline_construct_variations() -> list[dict[str, Any]]:
    """Generate inline math constructs crossed with containers and delimiters."""
    variations: list[dict[str, Any]] = []

    constructs = [
        ("single_subscript", r"P_{\text{primary}} = 1.0\text{ mW}", []),
        ("dual_subscript", r"P_{\text{primary}} and P_{\text{secondary}}", ["GFM-M12"]),
        ("log_index", r"\log_2(X) \ge 10", []),
        ("fractional_ratio", r"\frac{A + B}{C - D} \le 1.5", []),
        ("register_identifier", r"\text{sensor_ref_in} \ge 0.5", ["GFM-M03", "GFM-M14"]),
    ]

    containers: list[tuple[str, Callable[[str], str]]] = [
        (
            "root_prose",
            lambda c: f"# Test in Root Prose\n\nTelemetry measurement shows {c} under normal conditions.\n",
        ),
        (
            "bullet_list",
            lambda c: f"# Test in Bullet List\n\n* Sensor calibration step:\n  Telemetry measurement shows {c}.\n",
        ),
        (
            "nested_ordered_list",
            lambda c: (
                f"# Test in Nested Ordered List\n\n"
                f"1. Channel verification:\n"
                f"   1. Substep measurement:\n"
                f"      Telemetry shows {c}.\n"
            ),
        ),
        (
            "blockquote",
            lambda c: f"# Test in Blockquote\n\n> Note: Telemetry measurement shows {c}.\n",
        ),
        (
            "table_cell",
            lambda c: (
                f"# Test in Table Cell\n\n"
                f"| Sensor ID | Calibration Metric | Status |\n"
                f"| :--- | :--- | :--- |\n"
                f"| SEN-001 | {c} | PASS |\n"
            ),
        ),
        (
            "blockquote_in_list",
            lambda c: (
                f"# Test in Blockquote Inside List\n\n"
                f"* Channel specification:\n"
                f"  > Note on power bounds:\n"
                f"  > Telemetry measurement shows {c}.\n"
            ),
        ),
    ]

    for c_name, c_latex, c_rules in constructs:
        for delim_type in ("inline_dollar", "backtick_math"):
            if delim_type == "inline_dollar":
                math_span = f"${c_latex}$"
                expected_rules = list(c_rules)
            else:
                math_span = f"$`{c_latex}`$"
                # Backtick math shields from GFM-M12 collision!
                expected_rules = [r for r in c_rules if r != "GFM-M12"]

            for cont_name, cont_fn in containers:
                tag = f"inline_{c_name}_{delim_type}_{cont_name}"
                content = cont_fn(math_span)
                variations.append(
                    {
                        "filename_slug": tag,
                        "title": f"Inline {c_name} with {delim_type} in {cont_name}",
                        "content": content,
                        "expected_rules": expected_rules,
                        "structural_tags": [
                            f"container:{cont_name}",
                            f"construct:{c_name}",
                            f"delimiter:{delim_type}",
                        ],
                    }
                )

    return variations


def generate_display_construct_variations() -> list[dict[str, Any]]:
    """Generate display math constructs crossed with containers and delimiters."""
    variations: list[dict[str, Any]] = []

    constructs = [
        (
            "multiline_snr",
            r"\text{SNR}_{\mathrm{meas}} = 10 \log_{10}\left(\frac{I_{\text{signal}}}"
            r"{I_{\text{noise}}}\right) \ge 20\text{ dB}",
        ),
        (
            "fractional_sum",
            r"\frac{\sum_{i=1}^n x_i}{\prod_{j=1}^m y_j} = 1.0",
        ),
        (
            "aligned_system",
            r"\begin{aligned}\Delta y &\le \text{cal_lock} \\ x &= 0\end{aligned}",
        ),
    ]

    containers: list[tuple[str, str, Callable[[str], str]]] = [
        (
            "root_prose",
            "",
            lambda d: f"# Display Math in Root Prose\n\nThe governing system formula:\n\n{d}\n",
        ),
        (
            "bullet_list",
            "  ",
            lambda d: f"# Display Math in Bullet List\n\n* Step 1: Compute ratio:\n{d}\n",
        ),
        (
            "nested_ordered_list",
            "      ",
            lambda d: f"# Display Math in Nested List\n\n1. Outer step:\n   1. Inner substep:\n{d}\n",
        ),
        (
            "blockquote",
            "> ",
            lambda d: f"# Display Math in Blockquote\n\n> System bound definition:\n{d}\n",
        ),
        (
            "blockquote_in_list",
            "  > ",
            lambda d: f"# Display Math in Blockquote Inside List\n\n* List step:\n  > Note formula:\n{d}\n",
        ),
    ]

    for c_name, c_math in constructs:
        for delim_type in ("display_dollar", "code_fence"):
            for cont_name, pad, cont_fn in containers:
                if delim_type == "display_dollar":
                    block = f"{pad}$$\n{pad}{c_math}\n{pad}$$"
                    # Indented $$ in lists triggers GFM-M02
                    expected = ["GFM-M02"] if "list" in cont_name and pad.strip() == "" else []
                    if "list" in cont_name:
                        expected = ["GFM-M02"]
                else:
                    block = f"{pad}```math\n{pad}{c_math}\n{pad}```"
                    # Fenced code math inside root prose triggers GFM-M01 conversion to $$
                    # But inside lists, GFM-M01 should preserve it
                    expected = ["GFM-M01"] if cont_name == "root_prose" else []

                tag = f"display_{c_name}_{delim_type}_{cont_name}"
                content = cont_fn(block)
                variations.append(
                    {
                        "filename_slug": tag,
                        "title": f"Display {c_name} with {delim_type} in {cont_name}",
                        "content": content,
                        "expected_rules": expected,
                        "structural_tags": [
                            f"container:{cont_name}",
                            f"construct:{c_name}",
                            f"delimiter:{delim_type}",
                        ],
                    }
                )

    return variations


def generate_diagram_variations() -> list[dict[str, Any]]:
    """Generate Mermaid diagram node linebreaks crossed with containers."""
    variations: list[dict[str, Any]] = []

    diagrams = [
        (
            "mermaid_newline",
            "```mermaid\n"
            "graph TD\n"
            "    A[Primary Channel\\nCalibration Active] --> B(Filter Settled\\nPoll Complete)\n"
            "```\n",
            ["GFM-D03"],
        ),
        (
            "mermaid_subgraph",
            "```mermaid\n"
            "graph TD\n"
            "    subgraph Sub[Calibration Cluster\\nZone A]\n"
            "        C[Node 1\\nActive] --> D[Node 2\\nIdle]\n"
            "    end\n"
            "```\n",
            ["GFM-D03"],
        ),
        (
            "mermaid_unquoted",
            "```mermaid\n"
            "flowchart LR\n"
            "    Start(Sensor Init\\nSelf-Test) --> Check{Voltages Normal\\nRail OK?}\n"
            "    Check -->|Yes| Run[Operational\\nTelemetry Active]\n"
            "```\n",
            ["GFM-D03"],
        ),
    ]

    containers: list[tuple[str, Callable[[str], str]]] = [
        ("root_prose", lambda d: f"# Diagram in Root Prose\n\nFlowchart definition:\n\n{d}\n"),
        ("bullet_list", lambda d: f"# Diagram in Bullet List\n\n* Subsystem Flowchart:\n\n{d}\n"),
        ("blockquote", lambda d: f"# Diagram in Blockquote\n\n> Subsystem Flowchart:\n\n{d}\n"),
        ("nested_list", lambda d: f"# Diagram in Nested List\n\n1. Sequence:\n   1. Stage:\n\n{d}\n"),
    ]

    for d_name, d_content, d_rules in diagrams:
        for cont_name, cont_fn in containers:
            tag = f"diagram_{d_name}_{cont_name}"
            content = cont_fn(d_content)
            variations.append(
                {
                    "filename_slug": tag,
                    "title": f"Diagram {d_name} in {cont_name}",
                    "content": content,
                    "expected_rules": list(d_rules),
                    "structural_tags": [
                        f"container:{cont_name}",
                        f"construct:{d_name}",
                        "diagram:mermaid",
                    ],
                }
            )

    return variations


def generate_mixed_torture_variations() -> list[dict[str, Any]]:
    """Generate complex multi-feature torture documents."""
    variations: list[dict[str, Any]] = [
        {
            "filename_slug": "torture_table_with_math_and_subscripts",
            "title": "Torture: Table with Inline Subscripts and Equations",
            "content": (
                "# Telemetry Calibration Summary Table\n\n"
                "| Sensor ID | Calibration Formula | Dual Subscript Check | SNR Target |\n"
                "| :--- | :--- | :--- | :--- |\n"
                "| SEN-A | $P_{\\text{primary}}$ | "
                "$P_{\\text{primary}}$ and $P_{\\text{secondary}}$ | $10\\log_{10}(X) \\ge 20$ |\n"
                "| SEN-B | $P_{\\text{secondary}}$ | $P_a$ and $P_b$ | $10\\log_{10}(Y) \\ge 15$ |\n"
            ),
            "expected_rules": ["GFM-M12"],
            "structural_tags": ["container:table", "construct:dual_subscript", "delimiter:inline_dollar"],
        },
        {
            "filename_slug": "torture_nested_list_blockquote_display_math",
            "title": "Torture: Nested List with Blockquote and Display Math",
            "content": (
                "# Hierarchical Specification\n\n"
                "1. Calibration Sequence:\n"
                "   * Inner Bullet Item:\n"
                "     > Warning: Ensure sensor SNR exceeds limit:\n"
                "     $$\n"
                "     \\text{SNR} = 10 \\log_{10}\\left(\\frac{A}{B}\\right) \\ge 20\\text{ dB}\n"
                "     $$\n"
            ),
            "expected_rules": ["GFM-M02"],
            "structural_tags": ["container:nested_list", "container:blockquote", "delimiter:display_dollar"],
        },
        {
            "filename_slug": "torture_mermaid_diagram_and_inline_subscripts",
            "title": "Torture: Mermaid Diagram Adjacent to Inline Subscripts",
            "content": (
                "# Telemetry Flow and Formulas\n\n"
                "Let $P_{\\text{primary}}$ and $P_{\\text{secondary}}$ be monitored.\n\n"
                "```mermaid\n"
                "graph TD\n"
                "    A[Acquisition\\nActive] --> B(Processing\\nComplete)\n"
                "```\n\n"
                "$$\n"
                "E = mc^2\n"
                "$$\n"
            ),
            "expected_rules": ["GFM-M12", "GFM-D03"],
            "structural_tags": ["construct:dual_subscript", "diagram:mermaid", "delimiter:inline_dollar"],
        },
        {
            "filename_slug": "torture_register_names_in_math_and_prose",
            "title": "Torture: Snake Case Register Identifiers in Math",
            "content": (
                "# Software Register Bounds\n\n"
                "The threshold $\\text{cal_lock_zone_r} \\ge 1.0$ controls stability.\n"
                "Signal offset $\\text{sensor_ref_in} \\le 0.05$ is asserted.\n"
            ),
            "expected_rules": ["GFM-M03", "GFM-M14"],
            "structural_tags": ["construct:register_identifier", "delimiter:inline_dollar"],
        },
        {
            "filename_slug": "torture_backtick_math_in_all_containers",
            "title": "Torture: Backtick Math Across Multiple Containers",
            "content": (
                "# Dual Subscripts Protected by Backticks\n\n"
                "In prose: $`P_{\\text{primary}}`$ and $`P_{\\text{secondary}}`$.\n\n"
                "* In list: $`P_{\\text{primary}}`$ and $`P_{\\text{secondary}}`$.\n"
                "> In quote: $`P_{\\text{primary}}`$ and $`P_{\\text{secondary}}`$.\n"
            ),
            "expected_rules": [],
            "structural_tags": ["construct:dual_subscript", "delimiter:backtick_math"],
        },
        {
            "filename_slug": "torture_code_fence_math_in_nested_list",
            "title": "Torture: Preserved Code Fence Math in Nested List",
            "content": (
                "# Clean List Fenced Math\n\n"
                "* Step 1: Compute ratio:\n"
                "  ```math\n"
                "  \\text{SNR} = 10 \\log_{10}(X) \\ge 20\\text{ dB}\n"
                "  ```\n"
            ),
            "expected_rules": [],
            "structural_tags": ["container:bullet_list", "delimiter:code_fence"],
        },
    ]
    return variations


def generate_edge_case_variations() -> list[dict[str, Any]]:
    """Generate specific edge cases and syntax boundary torture scenarios."""
    variations: list[dict[str, Any]] = [
        {
            "filename_slug": "edge_table_pipe_in_math",
            "title": "Edge: Table Cell with Unescaped Pipe in Math Mode",
            "content": (
                "# Table Cell with Raw Pipe in Math\n\n"
                "| Metric | Formula | Status |\n"
                "| :--- | :--- | :--- |\n"
                "| Absolute Error | $|x - y| \\le 0.01$ | PENDING |\n"
            ),
            "expected_rules": ["GFM-M15", "GFM-T01"],
            "structural_tags": ["container:table", "edge:table_pipe"],
        },
        {
            "filename_slug": "edge_table_pipe_escaped",
            "title": "Edge: Table Cell with Escaped Pipe Macros in Math Mode",
            "content": (
                "# Table Cell with Clean Pipe Macros\n\n"
                "| Metric | Formula | Status |\n"
                "| :--- | :--- | :--- |\n"
                "| Absolute Error | $\\lvert x - y \\rvert \\le 0.01$ | PASS |\n"
            ),
            "expected_rules": [],
            "structural_tags": ["container:table", "edge:table_pipe_clean"],
        },
        {
            "filename_slug": "edge_unicode_en_dash_math",
            "title": "Edge: Math Expression with Unicode En-Dash",
            "content": (
                "# Unicode En-Dash in Math Mode\n\nThe target temperature range is $20\u201325^\\circ\\text{C}$.\n"
            ),
            "expected_rules": ["GFM-M15"],
            "structural_tags": ["edge:unicode_dash", "delimiter:inline_dollar"],
        },
        {
            "filename_slug": "edge_unescaped_percent_math",
            "title": "Edge: Math Expression with Unescaped Percent Sign",
            "content": ("# Unescaped Percent Sign in Math\n\nDuty cycle bound: $D \\le 50%$.\n"),
            "expected_rules": ["GFM-M15"],
            "structural_tags": ["edge:percent_comment", "delimiter:inline_dollar"],
        },
        {
            "filename_slug": "edge_aligned_environment_display",
            "title": "Edge: Display Math Aligned Environment",
            "content": (
                "# Aligned Equation System\n\n"
                "$$\n"
                "\\begin{aligned}\n"
                "A &= 10 \\log_{10}(X) \\\\\n"
                "B &= 20 \\log_{10}(Y)\n"
                "\\end{aligned}\n"
                "$$\n"
            ),
            "expected_rules": [],
            "structural_tags": ["construct:aligned", "delimiter:display_dollar"],
        },
        {
            "filename_slug": "edge_cases_environment_display",
            "title": "Edge: Display Math Cases Environment",
            "content": (
                "# Piecewise Function in Display Math\n\n"
                "$$\n"
                "f(x) = \\begin{cases}\n"
                "1 & \\text{if } x \\ge 0 \\\\\n"
                "0 & \\text{if } x < 0\n"
                "\\end{cases}\n"
                "$$\n"
            ),
            "expected_rules": [],
            "structural_tags": ["construct:cases", "delimiter:display_dollar"],
        },
        {
            "filename_slug": "edge_consecutive_inline_math",
            "title": "Edge: Consecutive Inline Math Expressions on Single Line",
            "content": (
                "# Consecutive Math Spans\n\nGiven parameters $a = 1$, $b = 2$, and $c = 3$ without subscripts.\n"
            ),
            "expected_rules": [],
            "structural_tags": ["construct:consecutive_spans", "delimiter:inline_dollar"],
        },
        {
            "filename_slug": "edge_math_adjacent_to_code",
            "title": "Edge: Math Expression Immediately Adjacent to Inline Code",
            "content": (
                "# Math Adjacent to Code Span\n\nThe register `SENSOR_CR1` satisfies $P_a \\ge 0.5$ threshold.\n"
            ),
            "expected_rules": [],
            "structural_tags": ["construct:adjacent_code", "delimiter:inline_dollar"],
        },
        {
            "filename_slug": "edge_math_in_ordered_list_header",
            "title": "Edge: Math Expression in Ordered List Item Header",
            "content": (
                "# Math in Ordered List Header\n\n"
                "1. If power $P_a \\ge 1.0\\text{ mW}$ is observed, advance calibration.\n"
                "2. Else, wait for filter settling.\n"
            ),
            "expected_rules": [],
            "structural_tags": ["container:ordered_list", "delimiter:inline_dollar"],
        },
        {
            "filename_slug": "edge_math_in_task_list_item",
            "title": "Edge: Math Expression in GFM Task List Item",
            "content": (
                "# Math in GFM Task List\n\n"
                "- [x] Verify base voltage $V_0 = 3.3\\text{ V}$\n"
                "- [ ] Measure SNR bound $\\text{SNR} \\ge 20\\text{ dB}$\n"
            ),
            "expected_rules": [],
            "structural_tags": ["container:task_list", "delimiter:inline_dollar"],
        },
        {
            "filename_slug": "edge_math_with_currency_symbol",
            "title": "Edge: Document Mixing Prose Currency and Inline Math",
            "content": (
                "# Currency and Math Coexistence\n\n"
                "The test cost $50 per unit, and sensor model satisfies $x^2 + y^2 = 1$.\n"
            ),
            "expected_rules": [],
            "structural_tags": ["construct:currency_and_math", "delimiter:inline_dollar"],
        },
        {
            "filename_slug": "edge_mermaid_with_html_br",
            "title": "Edge: Mermaid Diagram Node Already Using Clean HTML Break",
            "content": (
                "# Mermaid with Compliant HTML Linebreaks\n\n"
                "```mermaid\n"
                "graph TD\n"
                "    A[Primary Channel<br>Calibration Active] --> B(Filter Settled<br>Poll Complete)\n"
                "```\n"
            ),
            "expected_rules": [],
            "structural_tags": ["diagram:mermaid", "edge:compliant_break"],
        },
        {
            "filename_slug": "edge_mermaid_double_quoted_label",
            "title": "Edge: Mermaid Node with Double Quoted String Containing Newline",
            "content": (
                "# Mermaid with Quoted Label Newlines\n\n"
                "```mermaid\n"
                "graph TD\n"
                '    A["Primary Channel\\nCalibration Active"] --> B["Filter Settled\\nPoll Complete"]\n'
                "```\n"
            ),
            "expected_rules": ["GFM-D03"],
            "structural_tags": ["diagram:mermaid", "edge:quoted_newline"],
        },
    ]
    return variations


def generate_all_synthetic_scenarios() -> list[dict[str, Any]]:
    """Assemble all synthetic matrix variations."""
    all_scenarios: list[dict[str, Any]] = []
    all_scenarios.extend(generate_inline_construct_variations())
    all_scenarios.extend(generate_display_construct_variations())
    all_scenarios.extend(generate_list_math_variations())
    all_scenarios.extend(generate_diagram_variations())
    all_scenarios.extend(generate_mixed_torture_variations())
    all_scenarios.extend(generate_edge_case_variations())
    return all_scenarios


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Conformance Crucible Benchmark Matrix.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("conformance/corpus/synthetic"),
        help="Directory to write synthetic markdown scenarios.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("conformance/corpus/manifest.yaml"),
        help="Path to output manifest.yaml.",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Clean existing synthetic scenarios before generation.",
    )
    args = parser.parse_args()

    output_dir: Path = args.output_dir
    manifest_path: Path = args.manifest

    output_dir.mkdir(parents=True, exist_ok=True)
    if args.clean:
        for existing_file in output_dir.glob("*.md"):
            existing_file.unlink()

    scenarios = generate_all_synthetic_scenarios()
    manifest_scenarios: list[dict[str, Any]] = []

    for idx, sc in enumerate(scenarios, start=1):
        scenario_id = f"syn_{idx:03d}"
        filename = f"{scenario_id}_{sc['filename_slug']}.md"
        file_path = output_dir / filename
        file_path.write_text(sc["content"], encoding="utf-8")

        manifest_scenarios.append(
            {
                "id": scenario_id,
                "path": f"synthetic/{filename}",
                "category": "synthetic",
                "description": sc["title"],
                "expected_rules": sc["expected_rules"],
                "structural_tags": sc.get("structural_tags", []),
            }
        )

    # Add frozen regression fixtures from Table 8 in ROADMAP.md
    regression_fixtures = [
        {
            "id": "reg_01",
            "path": "regressions/reg_01_subscript_collision.md",
            "category": "regressions",
            "description": "REG-01: Dual subscript inline math underscore collision",
            "expected_rules": ["GFM-M12"],
            "structural_tags": ["regression", "construct:dual_subscript", "delimiter:inline_dollar"],
        },
        {
            "id": "reg_02",
            "path": "regressions/reg_02_indented_display_math_list.md",
            "category": "regressions",
            "description": "REG-02: Indented display math in list item",
            "expected_rules": ["GFM-M02"],
            "structural_tags": ["regression", "container:bullet_list", "delimiter:display_dollar"],
        },
        {
            "id": "reg_03",
            "path": "regressions/reg_03_code_fence_list_preserved.md",
            "category": "regressions",
            "description": "REG-03: Code fence math in list preserved without conversion",
            "expected_rules": [],
            "structural_tags": ["regression", "container:bullet_list", "delimiter:code_fence"],
        },
        {
            "id": "reg_04",
            "path": "regressions/reg_04_snake_case_math.md",
            "category": "regressions",
            "description": "REG-04: Snake case register identifier in math mode",
            "expected_rules": ["GFM-M03", "GFM-M14"],
            "structural_tags": ["regression", "construct:register_identifier"],
        },
        {
            "id": "reg_05",
            "path": "regressions/reg_05_unrendered_html_breakdown.md",
            "category": "regressions",
            "description": "REG-05: HTML parser slice breakdown with leaked tags",
            "expected_rules": [],
            "structural_tags": ["regression", "html:breakdown"],
        },
        {
            "id": "reg_06",
            "path": "regressions/reg_06_cleanable_file.md",
            "category": "regressions",
            "description": "REG-06: Cleanable file resolving to 0 violations",
            "expected_rules": ["GFM-M12"],
            "structural_tags": ["regression", "lifecycle:convergence"],
        },
        {
            "id": "reg_07",
            "path": "regressions/reg_07_mermaid_literal_newline.md",
            "category": "regressions",
            "description": "REG-07: Mermaid node label with literal \\n sequence",
            "expected_rules": ["GFM-D03"],
            "structural_tags": ["regression", "diagram:mermaid"],
        },
    ]
    manifest_scenarios.extend(regression_fixtures)

    # Add wild real-world fixture
    wild_fixtures = [
        {
            "id": "wild_01",
            "path": "wild/wild_01_telemetry_metric_report.md",
            "category": "wild",
            "description": "WILD-01: Scrubbed Hardware Telemetry Calibration Specification",
            "expected_rules": ["GFM-M02", "GFM-M03", "GFM-M12", "GFM-D03"],
            "structural_tags": ["wild", "telemetry", "composite"],
        }
    ]
    manifest_scenarios.extend(wild_fixtures)

    manifest_data = {
        "version": "1.0",
        "description": "GFM Math Lint Conformance Benchmark Corpus Manifest",
        "total_scenarios": len(manifest_scenarios),
        "scenarios": manifest_scenarios,
    }

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("w", encoding="utf-8") as f:
        yaml.dump(manifest_data, f, sort_keys=False)

    print(
        f"Synthesized {len(scenarios)} synthetic scenarios in '{output_dir}'.\n"
        f"Wrote manifest with {len(manifest_scenarios)} total scenarios to '{manifest_path}'."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
