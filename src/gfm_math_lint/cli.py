"""Command line interface for gfm-math-lint."""

from __future__ import annotations

import argparse
import os
import sys
from importlib import metadata
from pathlib import Path

from gfm_math_lint.comment import create_issue, create_pr, post_comment, preview_markdown
from gfm_math_lint.config import load_config
from gfm_math_lint.linter import (
    Linter,
    _escape_workflow_data,
    _escape_workflow_property,
    format_violation_github,
    format_violation_text,
)
from gfm_math_lint.rules.shell_rules import RuleS01
from gfm_math_lint.verifier import build_preview_html, open_in_browser, verify_file, verify_markdown


def get_version() -> str:
    """Get package version."""
    try:
        return metadata.version("gfm-math-lint")
    except metadata.PackageNotFoundError:
        return "0.1.1"


def get_parser() -> argparse.ArgumentParser:
    """Return the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="gfm-math-lint",
        description="Linter and auto-fixer for GitHub-Flavored Markdown math, tables, code fences, and Mermaid",
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"%(prog)s {get_version()}",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # check subcommand
    check_parser = subparsers.add_parser("check", help="Check markdown files for GFM math & rule violations")
    check_parser.add_argument("paths", nargs="*", default=["."], help="Files or directories to check")
    check_parser.add_argument("--fix", action="store_true", help="Automatically fix detected violations")
    check_parser.add_argument("--diff", action="store_true", help="Print unified diff of suggested fixes")
    check_parser.add_argument("--config", help="Path to pyproject.toml configuration file")
    check_parser.add_argument(
        "--format",
        choices=["text", "github"],
        default="text",
        help="Output format (default: text)",
    )

    # fix subcommand (shortcut for check --fix)
    fix_parser = subparsers.add_parser("fix", help="Automatically fix detected violations in-place")
    fix_parser.add_argument("paths", nargs="*", default=["."], help="Files or directories to fix")
    fix_parser.add_argument("--config", help="Path to pyproject.toml configuration file")
    fix_parser.add_argument(
        "--format",
        choices=["text", "github"],
        default="text",
        help="Output format (default: text)",
    )

    # check-shell subcommand
    shell_parser = subparsers.add_parser(
        "check-shell",
        help="Scan shell scripts and workflows for unsafe math expansion",
    )
    shell_parser.add_argument("paths", nargs="*", default=["."], help="Files or directories to check")
    shell_parser.add_argument(
        "--format",
        choices=["text", "github"],
        default="text",
        help="Output format (default: text)",
    )

    # comment subcommand
    comment_parser = subparsers.add_parser(
        "comment",
        aliases=["post"],
        help="Safely post GFM comments, issues, and PRs to GitHub via gh CLI",
    )
    comment_parser.add_argument("--pr", type=int, help="Pull request number to comment on")
    comment_parser.add_argument("--issue", type=int, help="Issue number to comment on")
    comment_parser.add_argument("--create-issue", action="store_true", help="Create a new GitHub issue")
    comment_parser.add_argument("--create-pr", action="store_true", help="Create a new GitHub pull request")
    comment_parser.add_argument("--title", help="Title for newly created issue or pull request")
    comment_parser.add_argument("--label", action="append", dest="labels", help="Label to apply (can be repeated)")
    comment_parser.add_argument(
        "--assignee", action="append", dest="assignees", help="Assignee to assign (can be repeated)"
    )
    comment_parser.add_argument("--milestone", help="Milestone title or number")
    comment_parser.add_argument("--base", help="Target base branch for pull request")
    comment_parser.add_argument("--head", help="Source head branch for pull request")
    comment_parser.add_argument("--file", help="File containing markdown comment")
    comment_parser.add_argument("--repo", help="Target GitHub repository (owner/repo)")
    comment_parser.add_argument("--token", help="GitHub Personal Access Token for API requests")
    comment_parser.add_argument("--preview", action="store_true", help="Preview rendered HTML via GitHub API")

    # verify subcommand
    verify_parser = subparsers.add_parser(
        "verify",
        help="Verify rendered GFM HTML using GitHub Markdown API oracle",
    )
    verify_parser.add_argument("paths", nargs="*", default=["."], help="Files or directories to verify")
    verify_parser.add_argument("--config", help="Path to pyproject.toml configuration file")
    verify_parser.add_argument("--token", help="GitHub Personal Access Token for API requests")
    verify_parser.add_argument("--html", help="Path to write rendered HTML preview document")
    verify_parser.add_argument("--browser", action="store_true", help="Open rendered preview in web browser")
    verify_parser.add_argument(
        "--stdout",
        "--raw",
        action="store_true",
        dest="stdout",
        help="Print API-rendered HTML directly to standard output",
    )
    verify_parser.add_argument(
        "--format",
        choices=["text", "github"],
        default="text",
        help="Output format (default: text)",
    )

    return parser


DEFAULT_EXCLUDE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    ".tox",
    ".nox",
    "build",
    "dist",
    "__pycache__",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    "site-packages",
}


def collect_markdown_files(paths: list[str], root_dir: Path) -> tuple[list[Path], list[str]]:
    """Collect all markdown files under specified paths, pruning common build and virtualenv trees."""
    found: list[Path] = []
    missing: list[str] = []

    for p_str in paths:
        p = Path(p_str)
        if not p.exists():
            missing.append(p_str)
            continue
        if p.is_file():
            found.append(p)
        elif p.is_dir():
            for root, dirs, files in os.walk(p):
                dirs[:] = [d for d in dirs if d not in DEFAULT_EXCLUDE_DIRS and not d.startswith(".")]
                for f in sorted(files):
                    if f.endswith((".md", ".markdown")):
                        found.append(Path(root) / f)

    # Deduplicate while preserving order
    seen: set[Path] = set()
    result: list[Path] = []
    for file_item in found:
        resolved = file_item.resolve()
        if resolved not in seen:
            seen.add(resolved)
            result.append(file_item)
    return result, missing


def collect_shell_files(paths: list[str]) -> tuple[list[Path], list[str]]:
    """Collect shell scripts and CI workflow files under specified paths."""
    found: list[Path] = []
    missing: list[str] = []

    for p_str in paths:
        p = Path(p_str)
        if not p.exists():
            missing.append(p_str)
            continue
        if p.is_file():
            found.append(p)
        elif p.is_dir():
            for root, dirs, files in os.walk(p):
                dirs[:] = [d for d in dirs if d not in DEFAULT_EXCLUDE_DIRS and not d.startswith(".")]
                for f in sorted(files):
                    if f.endswith((".sh", ".yml", ".yaml")):
                        found.append(Path(root) / f)

    seen: set[Path] = set()
    result: list[Path] = []
    for file_item in found:
        resolved = file_item.resolve()
        if resolved not in seen:
            seen.add(resolved)
            result.append(file_item)
    return result, missing


def cmd_check(args: argparse.Namespace) -> int:
    """Execute 'check' subcommand."""
    root_dir = Path.cwd()
    config_path = Path(args.config) if getattr(args, "config", None) else None
    try:
        config = load_config(config_path, is_explicit=bool(getattr(args, "config", None)))
    except (FileNotFoundError, ValueError) as e:
        sys.stderr.write(f"Configuration error: {e}\n")
        return 2

    linter = Linter(config=config, root_dir=root_dir)

    md_files, missing = collect_markdown_files(args.paths, root_dir)
    if missing:
        for m in missing:
            sys.stderr.write(f"Error: Path does not exist: {m}\n")
        return 2

    total_violations = 0
    total_modified = 0

    format_fn = format_violation_github if args.format == "github" else format_violation_text

    for file_path in md_files:
        if config.is_file_excluded(file_path, root_dir):
            continue

        try:
            res = linter.lint_file(file_path, fix=args.fix or args.diff, in_place=args.fix)
        except (OSError, UnicodeDecodeError) as e:
            sys.stderr.write(f"Error reading {file_path}: {e}\n")
            total_violations += 1
            continue
        except Exception as e:
            sys.stderr.write(f"Internal error processing {file_path}: {e}\n")
            return 2

        if args.diff and res.diff:
            sys.stdout.write(res.diff)

        for v in res.violations:
            sys.stdout.write(format_fn(v, str(file_path)) + "\n")

        total_violations += len(res.violations)
        if res.modified:
            total_modified += 1

    if total_violations > 0 or total_modified > 0:
        return 1
    return 0


def cmd_check_shell(args: argparse.Namespace) -> int:
    """Execute 'check-shell' subcommand."""
    shell_files, missing = collect_shell_files(args.paths)
    if missing:
        for m in missing:
            sys.stderr.write(f"Error: Path does not exist: {m}\n")
        return 2

    rule = RuleS01()
    total_violations = 0

    format_fn = format_violation_github if args.format == "github" else format_violation_text

    for file_path in shell_files:
        try:
            with file_path.open("r", encoding="utf-8", newline="") as f:
                content = f.read()
        except (OSError, UnicodeDecodeError) as e:
            sys.stderr.write(f"Error reading {file_path}: {e}\n")
            total_violations += 1
            continue
        except Exception as e:
            sys.stderr.write(f"Internal error processing {file_path}: {e}\n")
            return 2

        lines = content.splitlines(keepends=True)
        violations = rule.check(lines, [], str(file_path))

        for v in violations:
            sys.stdout.write(format_fn(v, str(file_path)) + "\n")

        total_violations += len(violations)

    if total_violations > 0:
        return 1
    return 0


def cmd_comment(args: argparse.Namespace) -> int:
    """Execute 'comment' / 'post' subcommand."""
    if args.pr is not None and args.issue is not None:
        sys.stderr.write("Error: Cannot specify both --pr and --issue.\n")
        return 2

    action_modes = [
        bool(args.pr is not None),
        bool(args.issue is not None),
        bool(getattr(args, "create_issue", False)),
        bool(getattr(args, "create_pr", False)),
        bool(getattr(args, "preview", False)),
    ]

    if sum(action_modes) == 0:
        sys.stderr.write("Error: Either --pr, --issue, --create-issue, --create-pr, or --preview must be specified.\n")
        return 2

    if sum(action_modes) > 1 and not (args.preview and (args.pr is not None or args.issue is not None)):
        sys.stderr.write("Error: Conflicting target action modes specified.\n")
        return 2

    if (getattr(args, "create_issue", False) or getattr(args, "create_pr", False)) and not getattr(args, "title", None):
        action_name = "--create-issue" if getattr(args, "create_issue", False) else "--create-pr"
        sys.stderr.write(f"Error: --title is required when using {action_name}.\n")
        return 2

    # Read content
    if getattr(args, "file", None):
        p = Path(args.file)
        if not p.is_file():
            sys.stderr.write(f"Error: File not found: {args.file}\n")
            return 2
        try:
            with p.open("r", encoding="utf-8", newline="") as f:
                content = f.read()
        except (OSError, UnicodeDecodeError) as e:
            sys.stderr.write(f"Error reading {args.file}: {e}\n")
            return 2
    else:
        # Read from stdin
        content = sys.stdin.read()

    try:
        if args.preview:
            rendered = preview_markdown(content, token=getattr(args, "token", None))
            sys.stdout.write(rendered + ("\n" if not rendered.endswith("\n") else ""))
            return 0

        if getattr(args, "create_issue", False):
            result = create_issue(
                title=args.title,
                content=content,
                repo=args.repo,
                labels=getattr(args, "labels", None),
                assignees=getattr(args, "assignees", None),
                milestone=getattr(args, "milestone", None),
                token=getattr(args, "token", None),
            )
            url = result.get("url", "")
            sys.stdout.write(f"Successfully created issue: {url}\n" if url else "Successfully created issue.\n")
            return 0

        if getattr(args, "create_pr", False):
            result = create_pr(
                title=args.title,
                content=content,
                repo=args.repo,
                base=getattr(args, "base", None),
                head=getattr(args, "head", None),
                labels=getattr(args, "labels", None),
                assignees=getattr(args, "assignees", None),
                milestone=getattr(args, "milestone", None),
                token=getattr(args, "token", None),
            )
            url = result.get("url", "")
            msg = f"Successfully created pull request: {url}\n" if url else "Successfully created pull request.\n"
            sys.stdout.write(msg)
            return 0

        target_type = "pr" if args.pr is not None else "issue"
        target_id = args.pr if args.pr is not None else (args.issue or 0)
        result = post_comment(
            target_type=target_type,
            target_id=target_id,
            content=content,
            repo=args.repo,
            preview=args.preview,
        )
        sys.stdout.write(f"Successfully posted {target_type} comment on #{target_id}.\n")
        return 0
    except Exception as e:
        sys.stderr.write(f"Error: {e}\n")
        return 2


def cmd_verify(args: argparse.Namespace) -> int:
    """Execute 'verify' subcommand."""
    is_stdout = getattr(args, "stdout", False)
    diag_stream = sys.stderr if is_stdout else sys.stdout

    if "-" in args.paths:
        if len(args.paths) > 1:
            sys.stderr.write("Error: Cannot combine stdin ('-') with file paths.\n")
            return 2

        try:
            content = sys.stdin.read()
        except (OSError, UnicodeDecodeError) as e:
            sys.stderr.write(f"Error reading stdin: {e}\n")
            return 2

        diag_stream.write("Auditing <stdin> against api.github.com...\n")

        try:
            rendered_html, issues = verify_markdown(
                content,
                file_path="<stdin>",
                token=args.token,
                stdout=is_stdout,
            )
        except Exception as e:
            sys.stderr.write(f"Error verifying <stdin>: {e}\n")
            return 2

        for issue in issues:
            if args.format == "github":
                file_esc = _escape_workflow_property("<stdin>")
                cat_esc = _escape_workflow_property(issue.category)
                msg_esc = _escape_workflow_data(f"{issue.message} ({issue.snippet})")
                diag_stream.write(f"::error file={file_esc},title={cat_esc}::{msg_esc}\n")
            else:
                diag_stream.write(f"<stdin>: [{issue.category}] {issue.message}\n  Snippet: {issue.snippet}\n")

        if args.html:
            out_path = Path(args.html)
            full_html = build_preview_html(rendered_html, title="GFM Math Verification")
            out_path.write_text(full_html, encoding="utf-8")
            diag_stream.write(f"Wrote rendered HTML preview to {out_path}\n")

        if args.browser:
            opened_path = open_in_browser(rendered_html, title="GFM Math Verification")
            diag_stream.write(f"Opened preview in browser ({opened_path})\n")

        if len(issues) > 0:
            sys.stderr.write(f"Verification failed: {len(issues)} rendering anomaly(ies) detected.\n")
            return 1

        diag_stream.write("All files verified cleanly! 0 rendering anomalies detected.\n")
        return 0

    root_dir = Path.cwd()
    config_path = Path(args.config) if getattr(args, "config", None) else None
    try:
        config = load_config(config_path, is_explicit=bool(getattr(args, "config", None)))
    except (FileNotFoundError, ValueError) as e:
        sys.stderr.write(f"Configuration error: {e}\n")
        return 2

    md_files, missing = collect_markdown_files(args.paths, root_dir)
    if missing:
        for m in missing:
            sys.stderr.write(f"Error: Path does not exist: {m}\n")
        return 2

    filtered_files = [f for f in md_files if not config.is_file_excluded(f, root_dir)]
    if not filtered_files:
        sys.stderr.write("No markdown files found to verify.\n")
        return 0

    diag_stream.write(f"Auditing {len(filtered_files)} file(s) against api.github.com...\n")

    total_issues = 0
    all_html_chunks: list[str] = []

    for file_path in filtered_files:
        try:
            rendered_html, issues = verify_file(file_path, token=args.token, stdout=is_stdout)
        except Exception as e:
            sys.stderr.write(f"Error verifying {file_path}: {e}\n")
            return 2

        all_html_chunks.append(rendered_html)

        for issue in issues:
            if args.format == "github":
                file_esc = _escape_workflow_property(str(file_path))
                cat_esc = _escape_workflow_property(issue.category)
                msg_esc = _escape_workflow_data(f"{issue.message} ({issue.snippet})")
                diag_stream.write(f"::error file={file_esc},title={cat_esc}::{msg_esc}\n")
            else:
                diag_stream.write(f"{file_path}: [{issue.category}] {issue.message}\n  Snippet: {issue.snippet}\n")

        total_issues += len(issues)

    combined_html = "\n<hr>\n".join(all_html_chunks)

    if args.html:
        out_path = Path(args.html)
        full_html = build_preview_html(combined_html, title="GFM Math Verification")
        out_path.write_text(full_html, encoding="utf-8")
        diag_stream.write(f"Wrote rendered HTML preview to {out_path}\n")

    if args.browser:
        opened_path = open_in_browser(combined_html, title="GFM Math Verification")
        diag_stream.write(f"Opened preview in browser ({opened_path})\n")

    if total_issues > 0:
        sys.stderr.write(f"Verification failed: {total_issues} rendering anomaly(ies) detected.\n")
        return 1

    diag_stream.write("All files verified cleanly! 0 rendering anomalies detected.\n")
    return 0


def cmd_fix(args: argparse.Namespace) -> int:
    """Execute 'fix' subcommand (shortcut for check --fix)."""
    args.fix = True
    args.diff = False
    return cmd_check(args)


def main(argv: list[str] | None = None) -> int:
    """Run gfm-math-lint CLI."""
    parser = get_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "check":
        return cmd_check(args)
    elif args.command == "fix":
        return cmd_fix(args)
    elif args.command == "check-shell":
        return cmd_check_shell(args)
    elif args.command in ("comment", "post"):
        return cmd_comment(args)
    elif args.command == "verify":
        return cmd_verify(args)

    return 0


if __name__ == "__main__":
    sys.exit(main())
