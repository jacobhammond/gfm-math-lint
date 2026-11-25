"""Validation tests for Phase 5 distribution artifacts, documentation links, and release metadata."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING

import yaml  # type: ignore[import-untyped]

from gfm_math_lint import SAFE_SUBSET_DOCS_URL, __version__, get_safe_subset_url
from gfm_math_lint.cli import get_version, main
from gfm_math_lint.linter import format_violation_text, violation_to_dict
from gfm_math_lint.rules.base import Violation, get_verification_docs_url
from gfm_math_lint.rules.shell_rules import RuleS01
from gfm_math_lint.tokenizer import DocumentZone, Zone, scan_document_zones, scan_inline_spans

if TYPE_CHECKING:
    from collections.abc import Sequence

    import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_pre_commit_hooks_yaml_valid() -> None:
    """Verify .pre-commit-hooks.yaml declares all v1.0.0 hooks cleanly."""
    hooks_path = REPO_ROOT / ".pre-commit-hooks.yaml"
    data = yaml.safe_load(hooks_path.read_text(encoding="utf-8"))
    assert isinstance(data, list)
    by_id = {entry["id"]: entry for entry in data}

    assert {"gfm-math-lint", "gfm-math-fix", "gfm-math-verify", "gfm-shell-lint"} <= set(by_id)
    assert by_id["gfm-math-lint"]["entry"] == "gfm-math-lint check"
    assert by_id["gfm-math-fix"]["entry"] == "gfm-math-lint fix"
    assert by_id["gfm-math-verify"]["entry"] == "gfm-math-lint verify"
    assert by_id["gfm-shell-lint"]["entry"] == "gfm-math-lint check-shell"
    for hook in by_id.values():
        assert hook["language"] == "python"
        assert hook.get("description")


def test_github_action_yaml_structure_and_security() -> None:
    """Verify composite GitHub Action YAML pins SHAs, runs once, and avoids CodeQL script injection."""
    action_path = REPO_ROOT / "actions" / "gfm-math-lint-action" / "action.yml"
    raw = action_path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw)

    assert data["runs"]["using"] == "composite"
    assert data["inputs"]["version"]["default"] == "1.0.0"
    expected_inputs = {
        "mode",
        "paths",
        "target",
        "format",
        "config",
        "version",
        "python-version",
        "remote-verify",
        "offline-probe",
        "strict-katex",
        "no-katex",
        "json-output",
        "post-comment",
        "github-token",
    }
    assert expected_inputs <= set(data["inputs"])
    assert {"exit-code", "report-path"} <= set(data["outputs"])

    sha_re = re.compile(r"@[0-9a-f]{40}$")
    run_step_script = ""
    for step in data["runs"]["steps"]:
        if "uses" in step:
            assert sha_re.search(step["uses"]), f"Step uses unpinned ref: {step['uses']}"
        if "run" in step:
            assert "${{ inputs." not in step["run"]
            assert "${{ github.event." not in step["run"]
            if step.get("id") == "run":
                run_step_script = step["run"]

    # Single-execution guarantee & GITHUB_OUTPUT written before PR comment
    assert "json_cmd" not in run_step_script
    assert run_step_script.index('>> "$GITHUB_OUTPUT"') < run_step_script.index("comment --pr")

    # Must pass RuleS01 shell expansion check
    lines = raw.splitlines(keepends=True)
    assert RuleS01().check(lines, [], str(action_path)) == []


def test_safe_subset_docs_urls_and_violation_payload() -> None:
    """Verify Safe Subset Cheat Sheet URL mapping and JSON docs_url enrichment."""
    assert get_safe_subset_url() == SAFE_SUBSET_DOCS_URL
    assert get_safe_subset_url("GFM-M05").endswith("#letter-named-macros")
    assert get_safe_subset_url("GFM-M16").endswith("#display-math-structure")
    assert get_safe_subset_url("GFM-T01").endswith("#inline-math-and-tables")
    assert get_safe_subset_url("GFM-D04").endswith("#mermaid-diagrams")
    assert get_safe_subset_url("GFM-C03").endswith("#code-fences-and-shell")
    assert get_safe_subset_url("GFM-E01").endswith("#github-probe-ground-truth")

    assert get_verification_docs_url("span-dropped").endswith("#github-probe-ground-truth")
    assert get_verification_docs_url("mermaid-parse").endswith("#mermaid-diagrams")
    assert get_verification_docs_url("table-mismatch").endswith("#inline-math-and-tables")
    assert get_verification_docs_url("katex-error").endswith("#letter-named-macros")

    v = Violation(rule_id="GFM-M05", message="Use \\thinspace", line=3, col=4)
    payload = violation_to_dict(v)
    assert payload["docs_url"] == get_safe_subset_url("GFM-M05")
    assert "docs/safe-subset-cheatsheet.md" not in format_violation_text(v, "doc.md")
    assert get_safe_subset_url("GFM-M05") in format_violation_text(v, "doc.md", include_docs_url=True)


def test_docs_custom_rule_example_pattern() -> None:
    """Verify the documented custom Rule pattern from docs/rules.md executes without AttributeError."""

    class RuleCustom01:
        id: str = "GFM-X01"
        name: str = "custom-math-check"
        description: str = "Example custom rule checking math expressions."
        severity: str = "warning"

        def check(self, lines: Sequence[str], zones: list[DocumentZone], file_path: str = "") -> list[Violation]:
            violations: list[Violation] = []
            for zone in zones:
                if zone.zone_type in (Zone.PROSE, Zone.TABLE):
                    for idx, line in enumerate(zone.lines):
                        line_no = zone.start_line + idx
                        for span in scan_inline_spans(line, line_no):
                            if span.zone_type == Zone.INLINE_MATH and "\\foo" in span.content:
                                violations.append(
                                    Violation(
                                        rule_id=self.id,
                                        message="Use of \\foo is deprecated in math formulas.",
                                        line=line_no,
                                        col=span.start_col,
                                        severity=self.severity,
                                    )
                                )
            return violations

    content = "Here is $\\foo + 1$.\n"
    lines = content.splitlines(keepends=True)
    zones = scan_document_zones(lines)
    found = RuleCustom01().check(lines, zones, "doc.md")
    assert len(found) == 1
    assert found[0].rule_id == "GFM-X01"


def test_cli_verify_and_check_shell_docs_hints_and_json_docs_url(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Verify check-shell and verify emit Safe Subset hints in text mode and docs_url in verify JSON."""
    sh = tmp_path / "bad.sh"
    sh.write_text('#!/usr/bin/env bash\ngh pr comment 1 -b "$x$"\n', encoding="utf-8")
    assert main(["check-shell", str(sh)]) == 1
    assert f"Hint: Safe Subset Cheat Sheet: {SAFE_SUBSET_DOCS_URL}" in capsys.readouterr().err

    md = tmp_path / "bad.md"
    md.write_text("$$\n\\begin{bmatrix} a \\\\ b \\end{bmatrix}\n$$\n", encoding="utf-8")
    assert main(["verify", "--no-katex", str(md)]) == 1
    assert f"Hint: Safe Subset Cheat Sheet: {SAFE_SUBSET_DOCS_URL}" in capsys.readouterr().err

    assert main(["verify", "--no-katex", "--format", "json", str(md)]) == 1
    data = json.loads(capsys.readouterr().out)
    issues = data["files"][0]["issues"]
    assert issues
    assert all("docs_url" in iss and iss["docs_url"].startswith(SAFE_SUBSET_DOCS_URL) for iss in issues)


def test_markdown_relative_links_resolve() -> None:
    """Verify all relative Markdown links across documentation resolve to existing files."""
    doc_files = [
        REPO_ROOT / "README.md",
        REPO_ROOT / "ROADMAP.md",
        REPO_ROOT / "CHANGELOG.md",
        REPO_ROOT / "CONTRIBUTING.md",
        *sorted((REPO_ROOT / "docs").rglob("*.md")),
        *sorted((REPO_ROOT / "actions").rglob("*.md")),
    ]
    link_re = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
    for md_file in doc_files:
        text = md_file.read_text(encoding="utf-8")
        for target in link_re.findall(text):
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            rel_path = target.split("#", 1)[0]
            if not rel_path:
                continue
            resolved = (md_file.parent / rel_path).resolve()
            assert resolved.exists(), f"Broken relative link {target!r} in {md_file}"


def test_package_version_matches_pyproject() -> None:
    """Verify pyproject.toml, __version__, and CLI get_version() match."""
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    expected = pyproject["project"]["version"]
    assert expected == "1.0.0"
    assert __version__ == expected
    assert get_version() == expected
