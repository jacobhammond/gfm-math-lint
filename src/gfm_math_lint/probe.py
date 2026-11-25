"""Synthetic ground-truth calibrator for GitHub GFM math rendering (`gfm-math-lint probe`)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from gfm_math_lint.emulator import emulate_gfm_document
from gfm_math_lint.verifier import GFMHTMLValidator, render_gfm

if TYPE_CHECKING:
    from collections.abc import Sequence


@dataclass(frozen=True)
class ProbeCase:
    """A single synthetic ground-truth probe case (never contains user content)."""

    probe_id: str
    name: str
    description: str
    markdown: str
    expected_spans: tuple[str, ...]
    display: bool = False


@dataclass(frozen=True)
class ProbeResult:
    """Result of evaluating a single probe case against the emulator and optional live API."""

    probe_id: str
    name: str
    passed: bool
    expected_spans: tuple[str, ...]
    emulated_spans: tuple[str, ...]
    github_spans: tuple[str, ...] | None
    detail: str


@dataclass
class ProbeReport:
    """Aggregated probe calibration report."""

    mode: str
    results: list[ProbeResult]

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def passed_count(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def all_passed(self) -> bool:
        return self.total > 0 and self.passed_count == self.total

    def format_text(self) -> str:
        lines = [f"GFM Probe Calibration ({self.mode} mode): {self.passed_count}/{self.total} passed"]
        for r in self.results:
            status = "PASS" if r.passed else "FAIL"
            lines.append(f"  [{status}] {r.probe_id} ({r.name}): {r.detail}")
        return "\n".join(lines)

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "total": self.total,
            "passed": self.passed_count,
            "all_passed": self.all_passed,
            "results": [
                {
                    "probe_id": r.probe_id,
                    "name": r.name,
                    "passed": r.passed,
                    "expected_spans": list(r.expected_spans),
                    "emulated_spans": list(r.emulated_spans),
                    "github_spans": list(r.github_spans) if r.github_spans is not None else None,
                    "detail": r.detail,
                }
                for r in self.results
            ],
        }


PROBE_CASES: tuple[ProbeCase, ...] = (
    ProbeCase(
        probe_id="P1",
        name="intra-word-underscore",
        description="Intra-word underscores in inline math are safe under CommonMark §6.2",
        markdown="$a_1 + b_2$ and $c_3$",
        expected_spans=("a_1 + b_2", "c_3"),
    ),
    ProbeCase(
        probe_id="P2",
        name="escaped-underscore-unescape",
        description="GitHub CommonMark unescapes \\_ to _ before MathJax",
        markdown=r"$a\_1 + b_2$ and $c_3$",
        expected_spans=("a_1 + b_2", "c_3"),
    ),
    ProbeCase(
        probe_id="P3",
        name="inline-backslash-punctuation",
        description="Inline \\, and \\{ are stripped while letter macros (\\lvert, \\ast) survive",
        markdown=r"$x\,y \{z\} \lvert w \rvert \ast$",
        expected_spans=(r"x,y {z} \lvert w \rvert \ast",),
    ),
    ProbeCase(
        probe_id="P4",
        name="table-lvert-delimiters",
        description="\\lvert and \\rvert render cleanly inside GFM table cells",
        markdown="| Col |\n| :--- |\n| $\\lvert a \\rvert^2 + b_k$ |",
        expected_spans=(r"\lvert a \rvert^2 + b_k",),
    ),
    ProbeCase(
        probe_id="P5",
        name="display-eol-double-backslash",
        description="Trailing \\\\ at end of line in $$ display math is preserved",
        markdown="$$\n\\begin{aligned}\na &= b \\\\\nc &= d\n\\end{aligned}\n$$",
        expected_spans=("\\begin{aligned}\na &= b \\\\\nc &= d\n\\end{aligned}",),
        display=True,
    ),
    ProbeCase(
        probe_id="P6",
        name="display-backslash-punctuation",
        description="Backslash-punctuation escapes are stripped in $$ display math too",
        markdown="$$\n\\{d\\} \\, e\n$$",
        expected_spans=("{d} , e",),
        display=True,
    ),
    ProbeCase(
        probe_id="P7",
        name="display-midline-linebreak-collapse",
        description="Mid-line \\\\ inside $$ collapses to a single \\",
        markdown="$$\n\\begin{bmatrix} a \\\\ b \\end{bmatrix}\n$$",
        expected_spans=(r"\begin{bmatrix} a \ b \end{bmatrix}",),
        display=True,
    ),
    ProbeCase(
        probe_id="P8",
        name="indented-list-display-math-rejected",
        description="Indented $$ block inside a list item is not compiled as display math",
        markdown="* Item 1:\n  $$\n  \\text{SNR} = 10\n  $$",
        expected_spans=(),
        display=True,
    ),
    ProbeCase(
        probe_id="P9",
        name="display-block-interruption",
        description="Lines starting with '+ ' or '- ' inside $$ interrupt the display math block",
        markdown="$$\nP = U\n+ Z\n- 2R\n$$",
        expected_spans=(),
        display=True,
    ),
    ProbeCase(
        probe_id="P10",
        name="glued-opening-delimiter",
        description="Opening $ preceded by hyphen (base-$e$) is rejected as a math delimiter",
        markdown="the base-$e$ error",
        expected_spans=(),
    ),
    ProbeCase(
        probe_id="P11",
        name="fenced-math-bypass",
        description="Fenced ```math block bypasses CommonMark inline backslash stripping",
        markdown="```math\n\\{i\\} \\, x\n```",
        expected_spans=(r"\{i\} \, x",),
        display=True,
    ),
)


def build_combined_probe_document(cases: Sequence[ProbeCase]) -> str:
    """Build a single synthetic Markdown document containing all probe cases."""
    sections: list[str] = []
    for case in cases:
        sections.append(f"GFM-PROBE-START-{case.probe_id}\n\n{case.markdown.strip()}\n\nGFM-PROBE-END-{case.probe_id}")
    return "\n\n".join(sections) + "\n"


def slice_probe_html(combined_html: str, probe_id: str) -> str:
    """Extract the rendered HTML segment belonging to `probe_id`."""
    start_marker = f"GFM-PROBE-START-{probe_id}"
    end_marker = f"GFM-PROBE-END-{probe_id}"
    pattern = re.compile(
        rf"(?:<p>)?{re.escape(start_marker)}(?:</p>)?([\s\S]*?)(?:<p>)?{re.escape(end_marker)}(?:</p>)?"
    )
    m = pattern.search(combined_html)
    if not m:
        return ""
    return m.group(1).strip()


def _normalize_spans(spans: Sequence[str]) -> tuple[str, ...]:
    return tuple(s.replace("\r\n", "\n").strip() for s in spans)


def run_probes(
    token: str | None = None,
    offline: bool = False,
    cases: Sequence[ProbeCase] = PROBE_CASES,
) -> ProbeReport:
    """Run synthetic probes against the local emulator and (unless offline=True) GitHub /markdown API."""
    combined_html = ""
    if not offline:
        combined_md = build_combined_probe_document(cases)
        combined_html = render_gfm(combined_md, token=token)

    results: list[ProbeResult] = []
    for case in cases:
        expected = _normalize_spans(case.expected_spans)
        emu = emulate_gfm_document(case.markdown)
        emulated = _normalize_spans([s.content for s in emu.received_spans])

        github_spans: tuple[str, ...] | None = None
        if not offline:
            probe_html = slice_probe_html(combined_html, case.probe_id)
            validator = GFMHTMLValidator(file_path=f"probe:{case.probe_id}")
            validator.feed(probe_html)
            validator.close()
            github_spans = _normalize_spans([s.content for s in validator.received_math_spans])

        if offline:
            passed = emulated == expected
            detail = (
                f"Emulator matched expected ({len(emulated)} span(s))"
                if passed
                else f"Emulator drift: expected={expected!r}, emulated={emulated!r}"
            )
        else:
            passed = emulated == expected and github_spans == expected
            if passed:
                detail = f"Live GitHub and emulator matched ({len(expected)} span(s))"
            elif github_spans != expected:
                detail = f"GitHub API drift: expected={expected!r}, github={github_spans!r}, emulated={emulated!r}"
            else:
                detail = f"Emulator drift: expected={expected!r}, emulated={emulated!r}"

        results.append(
            ProbeResult(
                probe_id=case.probe_id,
                name=case.name,
                passed=passed,
                expected_spans=expected,
                emulated_spans=emulated,
                github_spans=github_spans,
                detail=detail,
            )
        )

    return ProbeReport(mode="offline" if offline else "remote", results=results)
