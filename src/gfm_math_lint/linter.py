"""Linter orchestrator and inline suppression engine for gfm-math-lint."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from gfm_math_lint.config import LintConfig
from gfm_math_lint.fixer import LintEdit, apply_edits, generate_unified_diff
from gfm_math_lint.rules import ALL_MARKDOWN_RULES, Rule, Violation
from gfm_math_lint.tokenizer import DocumentZone, Zone, scan_document_zones

BLOCK_DISABLE_RE = re.compile(r"<!--\s*gfm-math-lint-disable(?!\s*-next-line)(?:\s+(.*?))?\s*-->")
BLOCK_ENABLE_RE = re.compile(r"<!--\s*gfm-math-lint-enable(?:\s+(.*?))?\s*-->")
NEXT_LINE_DISABLE_RE = re.compile(r"<!--\s*gfm-math-lint-disable-next-line(?:\s+(.*?))?\s*-->")


@dataclass
class SuppressionManager:
    """Manages HTML comment directives for rule suppression."""

    # Map of line_number -> (all_disabled: bool, disabled_rules: set[str], enabled_exceptions: set[str])
    line_states: dict[int, tuple[bool, set[str], set[str]]] = field(default_factory=dict)

    @classmethod
    def parse_from_lines(cls, lines: list[str], zones: list[DocumentZone] | None = None) -> SuppressionManager:
        """Parse suppression directives across lines, ignoring fenced code blocks."""
        manager = cls()

        # Identify lines inside FENCED_CODE blocks
        fenced_lines: set[int] = set()
        if zones:
            for z in zones:
                if z.zone_type == Zone.FENCED_CODE:
                    fenced_lines.update(range(z.start_line, z.end_line + 1))

        all_disabled = False
        disabled_rules: set[str] = set()
        enabled_exceptions: set[str] = set()
        next_line_suppressions: dict[int, tuple[bool, set[str]]] = {}

        for idx, line in enumerate(lines):
            line_no = idx + 1

            # Directives inside code blocks must never be executed
            if line_no not in fenced_lines:
                # Check for block disable: <!-- gfm-math-lint-disable [rules...] -->
                m_block_dis = BLOCK_DISABLE_RE.search(line)
                if m_block_dis:
                    raw_rules = (m_block_dis.group(1) or "").strip()
                    if not raw_rules:
                        all_disabled = True
                        enabled_exceptions.clear()
                    else:
                        rules = {r.strip().upper() for r in raw_rules.split(",") if r.strip()}
                        if all_disabled:
                            enabled_exceptions.difference_update(rules)
                        else:
                            disabled_rules.update(rules)

                # Check for block enable: <!-- gfm-math-lint-enable [rules...] -->
                m_block_en = BLOCK_ENABLE_RE.search(line)
                if m_block_en:
                    raw_rules = (m_block_en.group(1) or "").strip()
                    if not raw_rules:
                        all_disabled = False
                        disabled_rules.clear()
                        enabled_exceptions.clear()
                    else:
                        rules = {r.strip().upper() for r in raw_rules.split(",") if r.strip()}
                        if all_disabled:
                            enabled_exceptions.update(rules)
                        else:
                            disabled_rules.difference_update(rules)

                # Check for next-line disable: <!-- gfm-math-lint-disable-next-line [rules...] -->
                m_next = NEXT_LINE_DISABLE_RE.search(line)
                if m_next:
                    raw_rules = (m_next.group(1) or "").strip()
                    next_line_no = line_no + 1
                    if not raw_rules:
                        next_line_suppressions[next_line_no] = (True, set())
                    else:
                        rules = {r.strip().upper() for r in raw_rules.split(",") if r.strip()}
                        next_line_suppressions[next_line_no] = (False, rules)

            # Record active state for this line
            curr_all = all_disabled
            curr_dis = set(disabled_rules)
            curr_exc = set(enabled_exceptions)

            if line_no in next_line_suppressions:
                nl_all, nl_rules = next_line_suppressions[line_no]
                if nl_all:
                    curr_all = True
                    curr_exc.clear()
                else:
                    curr_dis.update(nl_rules)

            manager.line_states[line_no] = (curr_all, curr_dis, curr_exc)

        return manager

    def is_suppressed(self, rule_id: str, line_no: int) -> bool:
        """Check if rule_id is suppressed on line_no."""
        state = self.line_states.get(line_no)
        if not state:
            return False
        all_disabled, disabled_rules, enabled_exceptions = state
        rule_upper = rule_id.upper()
        if all_disabled:
            return rule_upper not in enabled_exceptions
        return rule_upper in disabled_rules

    def is_edit_suppressed(self, rule_id: str, start_line: int, end_line: int) -> bool:
        """Check if any line touched by the edit range is suppressed for rule_id."""
        return any(self.is_suppressed(rule_id, line_no) for line_no in range(start_line, end_line + 1))


@dataclass
class LintResult:
    """Result of linting a file or string."""

    file_path: str
    violations: list[Violation]
    original_content: str
    fixed_content: str
    diff: str
    modified: bool = False


class Linter:
    """Core linting engine."""

    def __init__(
        self,
        config: LintConfig | None = None,
        rules: list[Rule] | None = None,
        root_dir: Path | None = None,
    ) -> None:
        self.config = config or LintConfig()
        self.rules = rules if rules is not None else ALL_MARKDOWN_RULES
        self.root_dir = root_dir or Path.cwd()

    def lint_string(
        self,
        content: str,
        file_path: str = "stdin",
        fix: bool = False,
    ) -> LintResult:
        """Lint raw markdown string."""
        lines = content.splitlines(keepends=True)
        zones = scan_document_zones(lines)
        suppression = SuppressionManager.parse_from_lines(lines, zones)

        raw_violations: list[Violation] = []

        for rule in self.rules:
            # Check if ignored by config
            if self.config.is_rule_ignored(rule.id, file_path, self.root_dir):
                continue

            violations = rule.check(lines, zones, file_path)
            for v in violations:
                # Filter suppressed violations
                if not suppression.is_suppressed(v.rule_id, v.line):
                    raw_violations.append(v)

        # Sort violations by coordinate
        sorted_violations = sorted(raw_violations, key=lambda v: (v.line, v.col))

        if not fix:
            return LintResult(
                file_path=file_path,
                violations=sorted_violations,
                original_content=content,
                fixed_content=content,
                diff="",
                modified=False,
            )

        # Iterative fix application: resolve overlapping edits until convergence (max 5 passes)
        current_content = content
        all_edits: list[LintEdit] = [
            v.edit
            for v in sorted_violations
            if v.edit is not None and not suppression.is_edit_suppressed(v.rule_id, v.edit.start_line, v.edit.end_line)
        ]
        if all_edits:
            current_content = apply_edits(current_content, all_edits)

        converged = not bool(all_edits)
        for _ in range(4):
            if not current_content:
                converged = True
                break
            iter_lines = current_content.splitlines(keepends=True)
            iter_zones = scan_document_zones(iter_lines)
            iter_suppression = SuppressionManager.parse_from_lines(iter_lines, iter_zones)
            iter_edits: list[LintEdit] = []
            for rule in self.rules:
                if self.config.is_rule_ignored(rule.id, file_path, self.root_dir):
                    continue
                for v in rule.check(iter_lines, iter_zones, file_path):
                    if (
                        v.edit is not None
                        and not iter_suppression.is_suppressed(v.rule_id, v.line)
                        and not iter_suppression.is_edit_suppressed(v.rule_id, v.edit.start_line, v.edit.end_line)
                    ):
                        iter_edits.append(v.edit)
            if not iter_edits:
                converged = True
                break
            next_content = apply_edits(current_content, iter_edits)
            if next_content == current_content:
                converged = True
                break
            current_content = next_content

        if not converged:
            import warnings

            warnings.warn(f"Fixes did not converge within 5 passes for {file_path}", RuntimeWarning, stacklevel=2)

        diff = generate_unified_diff(content, current_content, file_path)

        return LintResult(
            file_path=file_path,
            violations=sorted_violations,
            original_content=content,
            fixed_content=current_content,
            diff=diff,
            modified=(current_content != content),
        )

    def lint_file(
        self,
        path: Path | str,
        fix: bool = False,
        in_place: bool = False,
    ) -> LintResult:
        """Lint a file on disk preserving native line endings."""
        p = Path(path)
        with p.open("r", encoding="utf-8", newline="") as f:
            content = f.read()
        result = self.lint_string(content, file_path=str(p), fix=fix)

        if fix and in_place and result.modified:
            with p.open("w", encoding="utf-8", newline="") as f:
                f.write(result.fixed_content)

        return result


def format_violation_text(violation: Violation, file_path: str) -> str:
    """Format violation as standard terminal text."""
    v = violation
    return f"{file_path}:{v.line}:{v.col}: [{v.rule_id}] ({v.severity}) {v.message}"


def _escape_workflow_data(data: str) -> str:
    """Escape data for GitHub Actions workflow command message."""
    return data.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def _escape_workflow_property(prop: str) -> str:
    """Escape property value for GitHub Actions workflow command."""
    return prop.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A").replace(":", "%3A").replace(",", "%2C")


def format_violation_github(violation: Violation, file_path: str) -> str:
    """Format violation as GitHub Actions workflow command with escaped fields."""
    file_esc = _escape_workflow_property(file_path)
    title_esc = _escape_workflow_property(violation.rule_id)
    msg_esc = _escape_workflow_data(violation.message)
    return (
        f"::{violation.severity} file={file_esc},line={violation.line},col={violation.col},title={title_esc}::{msg_esc}"
    )
