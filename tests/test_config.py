"""Unit tests for config loader and pyproject.toml parser."""

from __future__ import annotations

from pathlib import Path

from gfm_math_lint.config import LintConfig, load_config


def test_is_file_excluded() -> None:
    config = LintConfig(exclude=["docs/archive/*", "*.tmp.md"])
    root = Path("/repo")
    assert config.is_file_excluded(Path("/repo/docs/archive/old.md"), root) is True
    assert config.is_file_excluded(Path("/repo/notes.tmp.md"), root) is True
    assert config.is_file_excluded(Path("/repo/docs/active.md"), root) is False


def test_is_rule_ignored() -> None:
    config = LintConfig(
        ignore=["GFM-M10"],
        per_file_ignores={"docs/pitfalls.md": ["GFM-M03", "GFM-M05"]},
    )
    root = Path("/repo")
    # Global ignore
    assert config.is_rule_ignored("GFM-M10", Path("/repo/docs/any.md"), root) is True
    assert config.is_rule_ignored("gfm-m10", Path("/repo/docs/any.md"), root) is True

    # Per-file ignore
    assert config.is_rule_ignored("GFM-M03", Path("/repo/docs/pitfalls.md"), root) is True
    assert config.is_rule_ignored("GFM-M05", Path("/repo/docs/pitfalls.md"), root) is True
    assert config.is_rule_ignored("GFM-M01", Path("/repo/docs/pitfalls.md"), root) is False
    assert config.is_rule_ignored("GFM-M03", Path("/repo/docs/other.md"), root) is False


def test_load_config_from_toml(tmp_path: Path) -> None:
    toml_path = tmp_path / "pyproject.toml"
    toml_str = (
        "[tool.gfm-math-lint]\n"
        'exclude = ["docs/archive/*", "vendor/*"]\n'
        'ignore = ["GFM-M10"]\n'
        "\n"
        "[tool.gfm-math-lint.per-file-ignores]\n"
        '"docs/pitfalls.md" = ["GFM-M03"]\n'
    )
    toml_path.write_text(toml_str, encoding="utf-8")
    res = load_config(toml_path, is_explicit=True)
    assert "docs/archive/*" in res.exclude
    assert "vendor/*" in res.exclude
    assert res.ignore == ["GFM-M10"]
    assert "docs/pitfalls.md" in res.per_file_ignores
    assert res.per_file_ignores["docs/pitfalls.md"] == ["GFM-M03"]


def test_load_config_nonexistent(tmp_path: Path) -> None:
    # Non-explicit nonexistent file returns default config
    config = load_config(tmp_path / "nonexistent.toml", is_explicit=False)
    assert config.exclude == []
    assert config.ignore == []
