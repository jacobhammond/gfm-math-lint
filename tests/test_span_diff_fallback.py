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


def test_span_diff_fallback_same_line_mixed_spans_and_safefix_guard() -> None:
    # Line has BOTH GFM-M05 ($x\,y$) AND unexplained ($a\#b$).
    # GFM-E01 must still be emitted for $a\#b$, and fix=True must fix GFM-M05 without rolling back!
    doc = r"Both $x\,y$ and $a\#b$ here." + "\n"
    res_check = Linter().lint_string(doc, fix=False)
    rule_ids = {v.rule_id for v in res_check.violations}
    assert "GFM-M05" in rule_ids
    assert "GFM-E01" in rule_ids

    res_fix = Linter().lint_string(doc, fix=True)
    assert res_fix.modified is True
    assert r"\thinspace" in res_fix.fixed_content
    assert any(v.rule_id == "GFM-E01" for v in res_fix.remaining_violations)


def test_span_diff_fallback_display_math_m18_does_not_mask_unexplained_diff() -> None:
    # GFM-M18 (non-ascii µ) is NOT a CommonMark-mutation explainer, so GFM-E01 still flags \#
    doc = "$$\n\\text{µm} + a\\#b\n$$\n"
    res = Linter().lint_string(doc, fix=False)
    rule_ids = {v.rule_id for v in res.violations}
    assert "GFM-M18" in rule_ids
    assert "GFM-E01" in rule_ids


def test_span_diff_fallback_respects_config_ignore_and_rule_map() -> None:
    from gfm_math_lint.rules import get_rule_by_id

    assert get_rule_by_id("GFM-E01") is not None

    # Ignoring GFM-M05 via config must not cause GFM-E01 to override the user's ignore
    res = Linter(config=LintConfig(ignore=["GFM-M05"])).lint_string(r"$x\,y$" + "\n", fix=False)
    assert res.violations == []
