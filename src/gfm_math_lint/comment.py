"""Safe GitHub PR and issue comment, creation, and preview wrapper."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import urllib.error
import urllib.request
from typing import Any


def preview_markdown(content: str, token: str | None = None) -> str:
    """Render markdown via GitHub API (gh api /markdown with urllib.request fallback)."""
    from gfm_math_lint.verifier import render_gfm

    return render_gfm(content, token=token)


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


def create_issue(
    title: str,
    content: str,
    repo: str | None = None,
    labels: list[str] | None = None,
    assignees: list[str] | None = None,
    milestone: str | None = None,
    token: str | None = None,
) -> dict[str, Any]:
    """Safely create a GitHub issue bypassing shell parameter expansion."""
    gh_bin = shutil.which("gh")
    if gh_bin:
        cmd = [gh_bin, "issue", "create", "--title", title, "--body-file", "-"]
        if repo:
            cmd.extend(["--repo", repo])
        if labels:
            for lbl in labels:
                cmd.extend(["--label", lbl])
        if assignees:
            for a in assignees:
                cmd.extend(["--assignee", a])
        if milestone:
            cmd.extend(["--milestone", str(milestone)])

        try:
            proc = subprocess.run(
                cmd,
                input=content.encode("utf-8"),
                capture_output=True,
                shell=False,
                check=True,
                timeout=30,
            )
            out_url = proc.stdout.decode("utf-8").strip()
            return {
                "status": "created",
                "url": out_url,
                "output": proc.stdout.decode("utf-8"),
            }
        except subprocess.CalledProcessError as e:
            err = e.stderr.decode("utf-8", errors="replace") if e.stderr else str(e)
            raise RuntimeError(f"GitHub CLI error: {err}") from e

    # Fallback to direct REST API if token and repo are available
    auth_token = token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if auth_token and repo:
        url = f"https://api.github.com/repos/{repo}/issues"
        headers = {
            "User-Agent": "gfm-math-lint",
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json",
        }
        payload_dict: dict[str, Any] = {"title": title, "body": content}
        if labels:
            payload_dict["labels"] = labels
        if assignees:
            payload_dict["assignees"] = assignees
        if milestone and str(milestone).isdigit():
            payload_dict["milestone"] = int(milestone)
        req_data = json.dumps(payload_dict).encode("utf-8")
        req = urllib.request.Request(url, data=req_data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:  # nosec: B310
                resp_data = json.loads(resp.read().decode("utf-8"))
                issue_url = resp_data.get("html_url", "")
                return {"status": "created", "url": issue_url, "output": issue_url}
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"GitHub REST API error ({e.code} {e.reason}): {body}") from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"Failed to connect to GitHub REST API: {e.reason}") from e

    raise RuntimeError("GitHub CLI ('gh') is not installed or not found in PATH.")


def create_pr(
    title: str,
    content: str,
    repo: str | None = None,
    base: str | None = None,
    head: str | None = None,
    labels: list[str] | None = None,
    assignees: list[str] | None = None,
    milestone: str | None = None,
    token: str | None = None,
) -> dict[str, Any]:
    """Safely create a GitHub pull request bypassing shell parameter expansion."""
    gh_bin = shutil.which("gh")
    if gh_bin:
        cmd = [gh_bin, "pr", "create", "--title", title, "--body-file", "-"]
        if repo:
            cmd.extend(["--repo", repo])
        if base:
            cmd.extend(["--base", base])
        if head:
            cmd.extend(["--head", head])
        if labels:
            for lbl in labels:
                cmd.extend(["--label", lbl])
        if assignees:
            for a in assignees:
                cmd.extend(["--assignee", a])
        if milestone:
            cmd.extend(["--milestone", str(milestone)])

        try:
            proc = subprocess.run(
                cmd,
                input=content.encode("utf-8"),
                capture_output=True,
                shell=False,
                check=True,
                timeout=30,
            )
            out_url = proc.stdout.decode("utf-8").strip()
            return {
                "status": "created",
                "url": out_url,
                "output": proc.stdout.decode("utf-8"),
            }
        except subprocess.CalledProcessError as e:
            err = e.stderr.decode("utf-8", errors="replace") if e.stderr else str(e)
            raise RuntimeError(f"GitHub CLI error: {err}") from e

    # Fallback to direct REST API if token and repo are available
    auth_token = token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if auth_token and repo:
        url = f"https://api.github.com/repos/{repo}/pulls"
        headers = {
            "User-Agent": "gfm-math-lint",
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json",
        }
        payload_dict: dict[str, Any] = {
            "title": title,
            "body": content,
            "base": base or "main",
            "head": head or "",
        }
        req_data = json.dumps(payload_dict).encode("utf-8")
        req = urllib.request.Request(url, data=req_data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:  # nosec: B310
                resp_data = json.loads(resp.read().decode("utf-8"))
                pr_url = resp_data.get("html_url", "")
                return {"status": "created", "url": pr_url, "output": pr_url}
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"GitHub REST API error ({e.code} {e.reason}): {body}") from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"Failed to connect to GitHub REST API: {e.reason}") from e

    raise RuntimeError("GitHub CLI ('gh') is not installed or not found in PATH.")
