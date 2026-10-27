"""Unit tests for the synthetic matrix generator."""

from __future__ import annotations

from scripts.generate_conformance_matrix import (
    generate_all_synthetic_scenarios,
    generate_diagram_variations,
    generate_display_construct_variations,
    generate_inline_construct_variations,
    generate_list_math_variations,
)


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
