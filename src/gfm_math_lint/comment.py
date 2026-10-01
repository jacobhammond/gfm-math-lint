"""Safe GitHub PR and issue comment posting wrapper."""

from __future__ import annotations

import json
import shutil
import subprocess
from typing import Any


def preview_markdown(content: str) -> str:
    """Render markdown via GitHub API (gh api /markdown) without shell evaluation."""
    gh_bin = shutil.which("gh")
    if not gh_bin:
        raise RuntimeError("GitHub CLI ('gh') is not installed or not found in PATH.")

    payload = json.dumps({"text": content, "mode": "gfm"})
    try:
        result = subprocess.run(
            [gh_bin, "api", "/markdown", "--input", "-"],
            input=payload.encode("utf-8"),
            capture_output=True,
            shell=False,
            check=True,
            timeout=20,
        )
        return result.stdout.decode("utf-8")
    except subprocess.CalledProcessError as e:
        err = e.stderr.decode("utf-8", errors="replace") if e.stderr else str(e)
        raise RuntimeError(f"GitHub CLI error: {err}") from e


def post_comment(
    target_type: str,
    target_id: int,
    content: str,
    repo: str | None = None,
    preview: bool = False,
) -> dict[str, Any]:
    """Safely post PR or issue comment bypassing shell parameter expansion."""
    gh_bin = shutil.which("gh")
    if not gh_bin:
        raise RuntimeError("GitHub CLI ('gh') is not installed or not found in PATH.")

    if preview:
        rendered = preview_markdown(content)
        return {"status": "preview", "rendered_html": rendered}

    cmd = [gh_bin, target_type, "comment", str(target_id), "--body-file", "-"]
    if repo:
        cmd.extend(["--repo", repo])

    try:
        proc = subprocess.run(
            cmd,
            input=content.encode("utf-8"),
            capture_output=True,
            shell=False,
            check=True,
            timeout=30,
        )
        return {
            "status": "posted",
            "output": proc.stdout.decode("utf-8"),
        }
    except subprocess.CalledProcessError as e:
        err = e.stderr.decode("utf-8", errors="replace") if e.stderr else str(e)
        raise RuntimeError(f"GitHub CLI error: {err}") from e
