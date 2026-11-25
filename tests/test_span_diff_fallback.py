"""Tests for unexplained span-diff fallback (GFM-E01) and telemetry in Linter."""

from __future__ import annotations

from gfm_math_lint import LintConfig, Linter


def test_span_diff_fallback_emits_gfm_e01_for_unexplained_mutation() -> None:
    # '\#' in inline math is stripped by CommonMark to '#', not covered by M01-M18
    res = Linter().lint_string(r"Value $a\#b$ here." + "\n", fix=False)
    assert res.span_diff.intended_count == 1
    assert res.span_diff.received_count == 1
    assert len(res.span_diff.diffs) == 1
    assert any(v.rule_id == "GFM-E01" for v in res.violations)


def test_span_diff_fallback_does_not_duplicate_explained_rules() -> None:
    # GFM-M05 explains \, ; GFM-M17 explains '+ Z'; GFM-M13 explains base-$e$
    for doc in (
        r"Inline $x\,y$." + "\n",
        "$$\nP = U\n+ Z\n$$\n",
        "the base-$e$ error\n",
    ):
        res = Linter().lint_string(doc, fix=False)
        assert not any(v.rule_id == "GFM-E01" for v in res.violations), f"Unexpected GFM-E01 on: {doc}"


def test_span_diff_fallback_respects_suppressed_specific_rule_and_e01_ignore() -> None:
    doc = "<!-- gfm-math-lint-disable GFM-M05 -->\n$x\\,y$\n"
    res = Linter().lint_string(doc, fix=False)
    assert not any(v.rule_id in ("GFM-M05", "GFM-E01") for v in res.violations)

    res_ignored = Linter(config=LintConfig(ignore=["GFM-E01"])).lint_string(r"$a\#b$" + "\n", fix=False)
    assert not any(v.rule_id == "GFM-E01" for v in res_ignored.violations)


def test_span_diff_telemetry_on_clean_and_fixed_document() -> None:
    clean = Linter().lint_string("Clean $a_1 + b_2$.\n", fix=False)
    assert clean.violations == []
    assert clean.span_diff.intended_count == 1
    assert clean.span_diff.received_count == 1
    assert clean.span_diff.diffs == []
