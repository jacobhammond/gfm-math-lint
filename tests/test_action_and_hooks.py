"""Validation tests for Phase 5 distribution artifacts, documentation links, and release metadata."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import yaml  # type: ignore[import-untyped]

from gfm_math_lint import SAFE_SUBSET_DOCS_URL, __version__, get_safe_subset_url
from gfm_math_lint.cli import get_version
from gfm_math_lint.linter import format_violation_text, violation_to_dict
from gfm_math_lint.rules.base import Violation
from gfm_math_lint.rules.shell_rules import RuleS01

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
    """Verify composite GitHub Action YAML pins SHAs and avoids CodeQL script injection."""
    action_path = REPO_ROOT / "actions" / "gfm-math-lint-action" / "action.yml"
    raw = action_path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw)

    assert data["runs"]["using"] == "composite"
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
    for step in data["runs"]["steps"]:
        if "uses" in step:
            assert sha_re.search(step["uses"]), f"Step uses unpinned ref: {step['uses']}"
        if "run" in step:
            assert "${{ inputs." not in step["run"]
            assert "${{ github.event." not in step["run"]

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

    v = Violation(rule_id="GFM-M05", message="Use \\thinspace", line=3, col=4)
    payload = violation_to_dict(v)
    assert payload["docs_url"] == get_safe_subset_url("GFM-M05")
    assert "docs/safe-subset-cheatsheet.md" not in format_violation_text(v, "doc.md")
    assert get_safe_subset_url("GFM-M05") in format_violation_text(v, "doc.md", include_docs_url=True)


def test_markdown_relative_links_resolve() -> None:
    """Verify all relative Markdown links in core documentation resolve to existing files."""
    doc_files = [
        REPO_ROOT / "README.md",
        REPO_ROOT / "ROADMAP.md",
        REPO_ROOT / "docs" / "README.md",
        REPO_ROOT / "docs" / "safe-subset-cheatsheet.md",
        REPO_ROOT / "docs" / "adr" / "README.md",
        REPO_ROOT / "docs" / "retrospectives" / "README.md",
        REPO_ROOT / "actions" / "gfm-math-lint-action" / "README.md",
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
