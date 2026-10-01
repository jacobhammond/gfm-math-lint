"""Unit tests for comment posting and preview wrapper."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from gfm_math_lint.comment import post_comment, preview_markdown


def test_preview_markdown_no_gh() -> None:
    with patch("shutil.which", return_value=None), pytest.raises(RuntimeError, match="GitHub CLI"):
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

    with patch("shutil.which", return_value="/usr/bin/gh"), patch("subprocess.run", return_value=mock_proc):
        res = post_comment("pr", 42, "content", repo="org/repo")
        assert res["status"] == "posted"
        assert "issuecomment-1" in res["output"]


def test_post_comment_no_gh() -> None:
    with patch("shutil.which", return_value=None), pytest.raises(RuntimeError, match="GitHub CLI"):
        post_comment("pr", 42, "content")
