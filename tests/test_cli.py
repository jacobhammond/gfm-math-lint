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
    """Test check --fix modifies file in-place, prints summary, and returns 0 when clean."""
    bad_file = tmp_path / "bad.md"
    bad_file.write_text("```math\nx = 1\n```\n", encoding="utf-8")

    # First run fixes all violations and exits 0
    ret1 = main(["check", "--fix", str(bad_file)])
    assert ret1 == 0
    captured = capsys.readouterr()
    assert "Fixed 1 violation(s)" in captured.out
    assert "GFM-M01" not in captured.out

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


def test_fix_subcommand(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Test 'fix' subcommand modifies file in-place, is idempotent (REG-21), and exits 0."""
    bad_file = tmp_path / "bad.md"
    bad_file.write_text("```math\nx = 1\n```\n", encoding="utf-8")

    ret = main(["fix", str(bad_file)])
    assert ret == 0
    captured = capsys.readouterr()
    assert "Fixed 1 violation(s)" in captured.out
    fixed_once = bad_file.read_text(encoding="utf-8")
    assert "$$\nx = 1\n$$\n" in fixed_once

    # REG-21: second fix run is a clean no-op and exits 0
    ret2 = main(["fix", str(bad_file)])
    assert ret2 == 0
    captured2 = capsys.readouterr()
    assert captured2.out == ""
    assert bad_file.read_text(encoding="utf-8") == fixed_once


def test_fix_subcommand_exits_nonzero_when_unfixable_remains(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Test 'fix' subcommand exits 1 and prints only remaining unfixable violations."""
    doc = tmp_path / "unfixable.md"
    doc.write_text("```math\nx = 1\n```\n\n```mermaid\ngraph TD\n    Node A --> Node B\n```\n", encoding="utf-8")

    ret = main(["fix", str(doc)])
    assert ret == 1
    captured = capsys.readouterr()
    assert "Fixed 1 violation(s)" in captured.out
    assert "GFM-D01" in captured.out
    assert "GFM-M01" not in captured.out


def test_check_target_flag(tmp_path: Path) -> None:
    """Test 'check --target' accepts valid rendering engine profiles."""
    clean_file = tmp_path / "clean.md"
    clean_file.write_text("# Clean\n\n$x = 1$\n", encoding="utf-8")
    assert main(["check", "--target", "vscode", str(clean_file)]) == 0
    assert main(["fix", "--target", "github", str(clean_file)]) == 0


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
    """Test 'verify - --remote' reads piped markdown from stdin."""
    from unittest.mock import patch

    clean_html = '<p><math-renderer class="js-inline-math">$x = y$</math-renderer></p>'
    with (
        patch("sys.stdin.read", return_value="$x = y$\n"),
        patch("gfm_math_lint.verifier.render_gfm", return_value=clean_html),
    ):
        ret = main(["verify", "--remote", "-"])
        assert ret == 0
        captured = capsys.readouterr()
        assert "Auditing <stdin> against api.github.com" in captured.out


def test_cli_verify_local_default_and_preview_dir(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Test 'verify' defaults to local offline emulator and supports --preview-dir."""
    from unittest.mock import patch

    doc = tmp_path / "doc.md"
    doc.write_text("# Doc\n\n$a_1 + b_2$\n\n```mermaid\ngraph TD\n    A --> B\n```\n", encoding="utf-8")
    preview_dir = tmp_path / "previews"
    fake_png = preview_dir / "doc_mermaid_01.png"

    with (
        patch("gfm_math_lint.verifier.render_gfm", side_effect=AssertionError("Must stay offline")),
        patch("gfm_math_lint.verifier.render_mermaid_previews", return_value=[fake_png]) as mock_preview,
    ):
        ret = main(["verify", "--preview-dir", str(preview_dir), str(doc)])
        assert ret == 0
        assert mock_preview.called
        out = capsys.readouterr().out
        assert "locally (offline emulator)" in out
        assert "Recognized 1/1 math spans" in out
        assert "Rendered 1 Mermaid preview(s)" in out


def test_cli_verify_preview_dir_unique_stems_across_subdirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify --preview-dir uses relative-path stems so subdirs do not overwrite each other."""
    from unittest.mock import patch

    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    (tmp_path / "a" / "README.md").write_text("```mermaid\ngraph TD\n    A --> B\n```\n", encoding="utf-8")
    (tmp_path / "b" / "README.md").write_text("```mermaid\ngraph LR\n    C --> D\n```\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    stems: list[str] = []

    def _fake_render(content: str, out_dir: Path, stem: str = "diagram") -> list[Path]:
        stems.append(stem)
        return [out_dir / f"{stem}_mermaid_01.png"]

    with patch("gfm_math_lint.verifier.render_mermaid_previews", side_effect=_fake_render):
        ret = main(["verify", "--no-katex", "--preview-dir", str(tmp_path / "out"), "."])
        assert ret == 0
        assert sorted(stems) == ["a__README", "b__README"]


def test_cli_verify_strict_katex_and_no_katex_flags(tmp_path: Path) -> None:
    from unittest.mock import patch

    from gfm_math_lint.latex import KaTeXDiagnostic

    doc = tmp_path / "doc.md"
    doc.write_text(r"$\text{µm}$" + "\n", encoding="utf-8")
    fake_diag = KaTeXDiagnostic(
        math_content=r"\text{µm}",
        display_mode=False,
        error_message="",
        warnings=["unknownSymbol: Unrecognized 'µ'"],
    )

    with patch("gfm_math_lint.verifier.run_local_katex_verification", return_value=[fake_diag]) as mock_katex:
        assert main(["verify", str(doc)]) == 0
        assert main(["verify", "--strict-katex", str(doc)]) == 1
        assert mock_katex.call_count == 2
        assert main(["verify", "--no-katex", "--strict-katex", str(doc)]) == 0
        assert mock_katex.call_count == 2


def test_cli_verify_preview_dir_missing_mmdc(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from unittest.mock import patch

    doc = tmp_path / "doc.md"
    doc.write_text("```mermaid\ngraph TD\n    A --> B\n```\n", encoding="utf-8")
    with patch("gfm_math_lint.rules.diagram_rules.find_mmdc_binary", return_value=None):
        ret = main(["verify", "--preview-dir", str(tmp_path / "out"), str(doc)])
        assert ret == 2
        assert "requires 'mmdc'" in capsys.readouterr().err


def test_cli_verify_stdout_flag(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Test 'verify --remote --stdout' prints rendered HTML directly to stdout and diagnostics to stderr."""
    from unittest.mock import patch

    doc = tmp_path / "doc.md"
    doc.write_text("$x = y$\n", encoding="utf-8")
    clean_html = '<p><math-renderer class="js-inline-math">$x = y$</math-renderer></p>'

    with patch("gfm_math_lint.verifier.render_gfm", return_value=clean_html):
        ret = main(["verify", "--remote", "--stdout", str(doc)])
        assert ret == 0
        captured = capsys.readouterr()
        assert captured.out.strip() == clean_html.strip()
        assert "Auditing 1 file(s)" in captured.err


def test_cli_verify_raw_flag(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Test 'verify --remote --raw' (alias for --stdout) prints rendered HTML directly to stdout."""
    from unittest.mock import patch

    doc = tmp_path / "doc.md"
    doc.write_text("$x = y$\n", encoding="utf-8")
    clean_html = '<p><math-renderer class="js-inline-math">$x = y$</math-renderer></p>'

    with patch("gfm_math_lint.verifier.render_gfm", return_value=clean_html):
        ret = main(["verify", "--remote", "--raw", str(doc)])
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


def test_cli_check_fix_shell_verify_json_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    import json

    md = tmp_path / "doc.md"
    md.write_text("```math\nx = 1\n```\n", encoding="utf-8")

    # check --format json
    ret_check = main(["check", "--format", "json", str(md)])
    assert ret_check == 1
    check_data = json.loads(capsys.readouterr().out)
    assert check_data["command"] == "check"
    assert check_data["target"] == "dual"
    assert check_data["summary"]["total_violations"] == 1
    assert check_data["files"][0]["violations"][0]["rule_id"] == "GFM-M01"

    # fix --format json
    ret_fix = main(["fix", "--format", "json", str(md)])
    assert ret_fix == 0
    fix_data = json.loads(capsys.readouterr().out)
    assert fix_data["command"] == "fix"
    assert fix_data["summary"]["fixed_violations"] == 1
    assert fix_data["summary"]["remaining_violations"] == 0
    assert fix_data["files"][0]["modified"] is True
    assert fix_data["files"][0]["span_diff"]["intended_count"] == 1

    # verify --format json (local)
    ret_verify = main(["verify", "--no-katex", "--format", "json", str(md)])
    assert ret_verify == 0
    verify_data = json.loads(capsys.readouterr().out)
    assert verify_data["command"] == "verify"
    assert verify_data["mode"] == "local"
    assert verify_data["summary"]["intended_math_spans"] == 1
    assert verify_data["summary"]["received_math_spans"] == 1

    # check-shell --format json
    sh = tmp_path / "run.sh"
    sh.write_text('gh pr comment 1 -b "$x_1$"\n', encoding="utf-8")
    ret_shell = main(["check-shell", "--format", "json", str(sh)])
    assert ret_shell == 1
    shell_data = json.loads(capsys.readouterr().out)
    assert shell_data["command"] == "check-shell"
    assert shell_data["summary"]["total_violations"] == 1
    assert shell_data["files"][0]["violations"][0]["rule_id"] == "GFM-S01"
