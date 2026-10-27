"""Unit tests for comment, issue, PR creation, and preview wrapper."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from gfm_math_lint.comment import create_issue, create_pr, post_comment, preview_markdown


def test_preview_markdown_no_gh_rest_fallback() -> None:
    # When gh is missing, preview_markdown should fall back to urllib.request
    mock_resp = MagicMock()
    mock_resp.read.return_value = b"<p>rendered fallback</p>"
    mock_resp.__enter__.return_value = mock_resp

    with (
        patch("shutil.which", return_value=None),
        patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen,
    ):
        out = preview_markdown("test content")
        assert out == "<p>rendered fallback</p>"
        assert mock_urlopen.called


def test_preview_markdown_no_gh_network_error() -> None:
    import urllib.error

    with (
        patch("shutil.which", return_value=None),
        patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Network down")),
        pytest.raises(RuntimeError, match="Failed to connect to GitHub Markdown API"),
    ):
        preview_markdown("test")


def test_preview_markdown_success() -> None:
    mock_proc = MagicMock()
    mock_proc.stdout = b"<p>rendered</p>"
    mock_proc.returncode = 0

    with patch("shutil.which", return_value="/usr/bin/gh"), patch("subprocess.run", return_value=mock_proc):
        out = preview_markdown("test")
        assert out == "<p>rendered</p>"


def test_post_comment_preview_mode() -> None:
    with patch("gfm_math_lint.comment.preview_markdown", return_value="<p>preview</p>"):
        res = post_comment("pr", 42, "content", preview=True)
        assert res["status"] == "preview"
        assert res["rendered_html"] == "<p>preview</p>"


def test_post_comment_success() -> None:
    mock_proc = MagicMock()
    mock_proc.stdout = b"https://github.com/org/repo/pull/42#issuecomment-1"
    mock_proc.returncode = 0

    with patch("shutil.which", return_value="/usr/bin/gh"), patch("subprocess.run", return_value=mock_proc) as mock_run:
        res = post_comment("pr", 42, "content", repo="org/repo")
        assert res["status"] == "posted"
        assert "issuecomment-1" in res["output"]
        assert mock_run.called
        cmd = mock_run.call_args[0][0]
        assert cmd == ["/usr/bin/gh", "pr", "comment", "42", "--body-file", "-", "--repo", "org/repo"]


def test_post_comment_no_gh() -> None:
    with patch("shutil.which", return_value=None), pytest.raises(RuntimeError, match="GitHub CLI"):
        post_comment("pr", 42, "content")


def test_create_issue_success_gh() -> None:
    mock_proc = MagicMock()
    mock_proc.stdout = b"https://github.com/org/repo/issues/100\n"
    mock_proc.returncode = 0

    with patch("shutil.which", return_value="/usr/bin/gh"), patch("subprocess.run", return_value=mock_proc) as mock_run:
        res = create_issue(
            title="Bug Report",
            content="Description with $x_1$",
            repo="org/repo",
            labels=["bug", "math"],
            assignees=["user1"],
            milestone="v0.1.2",
        )
        assert res["status"] == "created"
        assert res["url"] == "https://github.com/org/repo/issues/100"
        cmd = mock_run.call_args[0][0]
        assert cmd == [
            "/usr/bin/gh",
            "issue",
            "create",
            "--title",
            "Bug Report",
            "--body-file",
            "-",
            "--repo",
            "org/repo",
            "--label",
            "bug",
            "--label",
            "math",
            "--assignee",
            "user1",
            "--milestone",
            "v0.1.2",
        ]


def test_create_issue_rest_fallback() -> None:
    mock_resp = MagicMock()
    mock_resp.read.return_value = b'{"html_url": "https://github.com/org/repo/issues/101"}'
    mock_resp.__enter__.return_value = mock_resp

    with (
        patch("shutil.which", return_value=None),
        patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen,
    ):
        res = create_issue(
            title="REST Bug",
            content="Content",
            repo="org/repo",
            labels=["bug"],
            milestone="1",
            token="ghp_test123",
        )
        assert res["status"] == "created"
        assert res["url"] == "https://github.com/org/repo/issues/101"
        assert mock_urlopen.called


def test_create_issue_no_gh_no_token() -> None:
    with (
        patch("shutil.which", return_value=None),
        patch.dict("os.environ", {}, clear=True),
        pytest.raises(RuntimeError, match="GitHub CLI"),
    ):
        create_issue("Title", "Body")


def test_create_pr_success_gh() -> None:
    mock_proc = MagicMock()
    mock_proc.stdout = b"https://github.com/org/repo/pull/200\n"
    mock_proc.returncode = 0

    with patch("shutil.which", return_value="/usr/bin/gh"), patch("subprocess.run", return_value=mock_proc) as mock_run:
        res = create_pr(
            title="Feature PR",
            content="PR Body with math",
            repo="org/repo",
            base="main",
            head="feature-branch",
            labels=["enhancement"],
        )
        assert res["status"] == "created"
        assert res["url"] == "https://github.com/org/repo/pull/200"
        cmd = mock_run.call_args[0][0]
        assert cmd == [
            "/usr/bin/gh",
            "pr",
            "create",
            "--title",
            "Feature PR",
            "--body-file",
            "-",
            "--repo",
            "org/repo",
            "--base",
            "main",
            "--head",
            "feature-branch",
            "--label",
            "enhancement",
        ]


def test_create_pr_rest_fallback() -> None:
    mock_resp = MagicMock()
    mock_resp.read.return_value = b'{"html_url": "https://github.com/org/repo/pull/201"}'
    mock_resp.__enter__.return_value = mock_resp

    with (
        patch("shutil.which", return_value=None),
        patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen,
    ):
        res = create_pr(
            title="REST PR",
            content="Content",
            repo="org/repo",
            base="main",
            head="feat",
            token="ghp_test123",
        )
        assert res["status"] == "created"
        assert res["url"] == "https://github.com/org/repo/pull/201"
        assert mock_urlopen.called


def test_create_pr_no_gh_no_token() -> None:
    with (
        patch("shutil.which", return_value=None),
        patch.dict("os.environ", {}, clear=True),
        pytest.raises(RuntimeError, match="GitHub CLI"),
    ):
        create_pr("Title", "Body")
