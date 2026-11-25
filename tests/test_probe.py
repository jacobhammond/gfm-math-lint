"""Tests for synthetic ground-truth GFM probe calibrator (`gfm-math-lint probe`)."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from gfm_math_lint.cli import main
from gfm_math_lint.probe import PROBE_CASES, build_combined_probe_document, run_probes


def test_run_probes_offline_all_pass() -> None:
    report = run_probes(offline=True)
    assert report.mode == "offline"
    assert report.total == len(PROBE_CASES)
    assert report.passed_count == report.total
    assert report.all_passed is True


def test_run_probes_remote_matching_github_html() -> None:
    # Build synthetic GitHub-like HTML matching all probe expectations
    parts: list[str] = []
    for case in PROBE_CASES:
        parts.append(f"<p>GFM-PROBE-START-{case.probe_id}</p>")
        for sp in case.expected_spans:
            if case.display:
                parts.append(f'<math-renderer class="js-display-math">$${sp}$$</math-renderer>')
            else:
                parts.append(f'<math-renderer class="js-inline-math">${sp}$</math-renderer>')
        parts.append(f"<p>GFM-PROBE-END-{case.probe_id}</p>")
    fake_html = "\n".join(parts)

    with patch("gfm_math_lint.probe.render_gfm", return_value=fake_html) as mock_render:
        report = run_probes(offline=False)
        assert mock_render.called
        combined_sent = mock_render.call_args[0][0]
        assert combined_sent == build_combined_probe_document(PROBE_CASES)
        assert report.mode == "remote"
        assert report.all_passed is True
        assert report.passed_count == len(PROBE_CASES)


def test_run_probes_detects_github_drift() -> None:
    # Simulate GitHub API changing P7 behavior (not collapsing mid-line \\)
    parts: list[str] = []
    for case in PROBE_CASES:
        parts.append(f"<p>GFM-PROBE-START-{case.probe_id}</p>")
        if case.probe_id == "P7":
            parts.append(
                r'<math-renderer class="js-display-math">$$\begin{bmatrix} a \\ b \end{bmatrix}$$</math-renderer>'
            )
        else:
            for sp in case.expected_spans:
                cls = "js-display-math" if case.display else "js-inline-math"
                delim = "$$" if case.display else "$"
                parts.append(f'<math-renderer class="{cls}">{delim}{sp}{delim}</math-renderer>')
        parts.append(f"<p>GFM-PROBE-END-{case.probe_id}</p>")
    fake_html = "\n".join(parts)

    with patch("gfm_math_lint.probe.render_gfm", return_value=fake_html):
        report = run_probes(offline=False)
        assert report.all_passed is False
        p7 = next(r for r in report.results if r.probe_id == "P7")
        assert p7.passed is False
        assert "GitHub API drift" in p7.detail


def test_cli_probe_offline_text_and_json(capsys: pytest.CaptureFixture[str]) -> None:
    ret_text = main(["probe", "--offline"])
    assert ret_text == 0
    out_text = capsys.readouterr().out
    assert "GFM Probe Calibration (offline mode)" in out_text
    assert f"{len(PROBE_CASES)}/{len(PROBE_CASES)} passed" in out_text

    ret_json = main(["probe", "--offline", "--format", "json"])
    assert ret_json == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["mode"] == "offline"
    assert payload["all_passed"] is True
    assert payload["total"] == len(PROBE_CASES)
