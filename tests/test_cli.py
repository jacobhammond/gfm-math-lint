"""Comprehensive tests for the CLI."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from gfm_math_lint.cli import get_version, main

if TYPE_CHECKING:
    from pathlib import Path


def test_main_no_args(capsys: pytest.CaptureFixture[str]) -> None:
    """Test running CLI with no arguments shows help and returns 0."""
    assert main([]) == 0
    captured = capsys.readouterr()
    assert "gfm-math-lint" in captured.out


def test_show_help(capsys: pytest.CaptureFixture[str]) -> None:
    """Show help."""
    with pytest.raises(SystemExit) as exc_info:
        main(["-h"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "gfm-math-lint" in captured.out
    assert "check" in captured.out
    assert "comment" in captured.out


def test_show_version(capsys: pytest.CaptureFixture[str]) -> None:
    """Show version."""
    with pytest.raises(SystemExit) as exc_info:
        main(["-V"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert get_version() in captured.out


def test_check_clean_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Test check on a clean markdown file returns 0."""
    clean_file = tmp_path / "clean.md"
    clean_file.write_text("# Clean Title\n\nSome clean content.\n", encoding="utf-8")
    assert main(["check", str(clean_file)]) == 0
    captured = capsys.readouterr()
    assert captured.err == ""


def test_check_file_with_violations(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Test check on a file with violations returns 1 and reports violations."""
    bad_file = tmp_path / "bad.md"
    bad_file.write_text("```math\nx = 1\n```\n", encoding="utf-8")
    ret = main(["check", str(bad_file)])
    assert ret == 1
    captured = capsys.readouterr()
    assert "GFM-M01" in captured.out


def test_check_format_github(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Test check with --format=github prints GitHub workflow annotations."""
    bad_file = tmp_path / "bad.md"
    bad_file.write_text("```math\nx = 1\n```\n", encoding="utf-8")
    ret = main(["check", "--format=github", str(bad_file)])
    assert ret == 1
    captured = capsys.readouterr()
    assert "::error" in captured.out
    assert "title=GFM-M01" in captured.out


def test_check_diff(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Test check --diff prints unified diff without changing file."""
    bad_file = tmp_path / "bad.md"
    bad_content = "```math\nx = 1\n```\n"
    bad_file.write_text(bad_content, encoding="utf-8")
    ret = main(["check", "--diff", str(bad_file)])
    assert ret == 1
    captured = capsys.readouterr()
    assert "--- a/" in captured.out
    assert "+++ b/" in captured.out
    assert "$$" in captured.out
    # File must be untouched
    assert bad_file.read_text(encoding="utf-8") == bad_content


def test_check_fix(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Test check --fix modifies file in-place and passes on second run."""
    bad_file = tmp_path / "bad.md"
    bad_file.write_text("```math\nx = 1\n```\n", encoding="utf-8")

    # First run fixes file and returns 1
    ret1 = main(["check", "--fix", str(bad_file)])
    assert ret1 == 1

    # Verify content was updated
    fixed_content = bad_file.read_text(encoding="utf-8")
    assert "$$\nx = 1\n$$\n" in fixed_content

    # Second run is clean and returns 0
    ret2 = main(["check", str(bad_file)])
    assert ret2 == 0


def test_check_shell_with_violations(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Test check-shell flags unsafe parameter expansion."""
    script_file = tmp_path / "unsafe.sh"
    script_file.write_text('gh pr comment $PR_NO -b "$x_1$"\n', encoding="utf-8")

    ret = main(["check-shell", str(script_file)])
    assert ret == 1
    captured = capsys.readouterr()
    assert "GFM-S01" in captured.out


def test_comment_missing_args(capsys: pytest.CaptureFixture[str]) -> None:
    """Test comment subcommand errors when required args are missing."""
    ret = main(["comment"])
    assert ret == 2
    captured = capsys.readouterr()
    assert "Error" in captured.err


def test_comment_file_not_found(capsys: pytest.CaptureFixture[str]) -> None:
    """Test comment subcommand with non-existent file."""
    ret = main(["comment", "--pr", "123", "--file", "nonexistent.md"])
    assert ret == 2
    captured = capsys.readouterr()
    assert "File not found" in captured.err


def test_comment_preview_success(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test comment --preview prints rendered markdown."""
    comment_file = tmp_path / "comment.md"
    comment_file.write_text("# Heading\n", encoding="utf-8")

    monkeypatch.setattr(
        "gfm_math_lint.cli.preview_markdown",
        lambda *args, **kwargs: "<h1>Heading</h1>\n",
    )

    ret = main(["comment", "--preview", "--file", str(comment_file)])
    assert ret == 0
    captured = capsys.readouterr()
    assert "<h1>Heading</h1>" in captured.out


def test_comment_post_success(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test comment --pr posts comment."""
    comment_file = tmp_path / "comment.md"
    comment_file.write_text("PR body\n", encoding="utf-8")

    monkeypatch.setattr(
        "gfm_math_lint.cli.post_comment",
        lambda **kwargs: {"status": "posted", "output": "ok"},
    )

    ret = main(["comment", "--pr", "123", "--file", str(comment_file)])
    assert ret == 0
    captured = capsys.readouterr()
    assert "Successfully posted pr comment on #123" in captured.out


def test_comment_both_pr_and_issue(capsys: pytest.CaptureFixture[str]) -> None:
    """Test comment with both --pr and --issue returns error."""
    ret = main(["comment", "--pr", "1", "--issue", "2"])
    assert ret == 2
    captured = capsys.readouterr()
    assert "Cannot specify both --pr and --issue" in captured.err


def test_collect_markdown_files_nonexistent(capsys: pytest.CaptureFixture[str]) -> None:
    """Test collect_markdown_files exits 2 on nonexistent path."""
    ret = main(["check", "this_path_does_not_exist_xyz.md"])
    assert ret == 2
    captured = capsys.readouterr()
    assert "Error: Path does not exist" in captured.err


def test_fix_subcommand(tmp_path: Path) -> None:
    """Test 'fix' subcommand modifies file in-place."""
    bad_file = tmp_path / "bad.md"
    bad_file.write_text("```math\nx = 1\n```\n", encoding="utf-8")

    ret = main(["fix", str(bad_file)])
    assert ret == 1
    assert "$$\nx = 1\n$$\n" in bad_file.read_text(encoding="utf-8")


def test_check_with_explicit_config(tmp_path: Path) -> None:
    """Test 'check' subcommand respects explicit --config."""
    cfg_file = tmp_path / "custom.toml"
    cfg_file.write_text('[tool.gfm-math-lint]\nignore = ["GFM-M01"]\n', encoding="utf-8")

    bad_file = tmp_path / "bad.md"
    bad_file.write_text("```math\nx = 1\n```\n", encoding="utf-8")

    # With ignore in config, it should pass with 0
    ret = main(["check", "--config", str(cfg_file), str(bad_file)])
    assert ret == 0


def test_cli_verify_stdin(capsys: pytest.CaptureFixture[str]) -> None:
    """Test 'verify -' reads piped markdown from stdin."""
    from unittest.mock import patch

    clean_html = '<p><math-renderer class="js-inline-math">$x = y$</math-renderer></p>'
    with (
        patch("sys.stdin.read", return_value="$x = y$\n"),
        patch("gfm_math_lint.verifier.render_gfm", return_value=clean_html),
    ):
        ret = main(["verify", "-"])
        assert ret == 0
        captured = capsys.readouterr()
        assert "Auditing <stdin>" in captured.out


def test_cli_verify_stdout_flag(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Test 'verify --stdout' prints rendered HTML directly to stdout and diagnostics to stderr."""
    from unittest.mock import patch

    doc = tmp_path / "doc.md"
    doc.write_text("$x = y$\n", encoding="utf-8")
    clean_html = '<p><math-renderer class="js-inline-math">$x = y$</math-renderer></p>'

    with patch("gfm_math_lint.verifier.render_gfm", return_value=clean_html):
        ret = main(["verify", "--stdout", str(doc)])
        assert ret == 0
        captured = capsys.readouterr()
        assert captured.out.strip() == clean_html.strip()
        assert "Auditing 1 file(s)" in captured.err


def test_cli_verify_raw_flag(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Test 'verify --raw' (alias for --stdout) prints rendered HTML directly to stdout."""
    from unittest.mock import patch

    doc = tmp_path / "doc.md"
    doc.write_text("$x = y$\n", encoding="utf-8")
    clean_html = '<p><math-renderer class="js-inline-math">$x = y$</math-renderer></p>'

    with patch("gfm_math_lint.verifier.render_gfm", return_value=clean_html):
        ret = main(["verify", "--raw", str(doc)])
        assert ret == 0
        captured = capsys.readouterr()
        assert captured.out.strip() == clean_html.strip()
        assert "Auditing 1 file(s)" in captured.err


def test_cli_comment_create_issue(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from unittest.mock import patch

    doc = tmp_path / "issue.md"
    doc.write_text("Issue content with $x_1$\n", encoding="utf-8")

    with patch(
        "gfm_math_lint.cli.create_issue",
        return_value={"status": "created", "url": "https://github.com/org/repo/issues/42"},
    ):
        ret = main(["comment", "--create-issue", "--title", "Test Issue", "--file", str(doc)])
        assert ret == 0
        captured = capsys.readouterr()
        assert "Successfully created issue: https://github.com/org/repo/issues/42" in captured.out


def test_cli_post_alias_create_pr(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from unittest.mock import patch

    doc = tmp_path / "pr.md"
    doc.write_text("PR content\n", encoding="utf-8")

    with patch(
        "gfm_math_lint.cli.create_pr",
        return_value={"status": "created", "url": "https://github.com/org/repo/pull/43"},
    ):
        ret = main(["post", "--create-pr", "--title", "Test PR", "--file", str(doc), "--base", "main"])
        assert ret == 0
        captured = capsys.readouterr()
        assert "Successfully created pull request: https://github.com/org/repo/pull/43" in captured.out


def test_cli_comment_missing_action(capsys: pytest.CaptureFixture[str]) -> None:
    ret = main(["comment", "--title", "No action"])
    assert ret == 2
    captured = capsys.readouterr()
    assert "Either --pr, --issue, --create-issue, --create-pr, or --preview must be specified" in captured.err


def test_cli_comment_missing_title(capsys: pytest.CaptureFixture[str]) -> None:
    ret = main(["comment", "--create-issue"])
    assert ret == 2
    captured = capsys.readouterr()
    assert "--title is required when using --create-issue" in captured.err


def test_cli_comment_conflicting_modes(capsys: pytest.CaptureFixture[str]) -> None:
    ret = main(["comment", "--create-issue", "--create-pr", "--title", "Both"])
    assert ret == 2
    captured = capsys.readouterr()
    assert "Conflicting target action modes" in captured.err
