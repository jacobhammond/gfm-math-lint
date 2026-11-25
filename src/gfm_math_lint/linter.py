"""Linter orchestrator and inline suppression engine for gfm-math-lint."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Sequence

from gfm_math_lint.config import LintConfig
from gfm_math_lint.emulator import SpanDiff, emulate_gfm_document
from gfm_math_lint.fixer import LintEdit, apply_edits, generate_unified_diff
from gfm_math_lint.rules import ALL_MARKDOWN_RULES, Rule, Violation
from gfm_math_lint.tokenizer import DocumentZone, Zone, scan_document_zones

BLOCK_DISABLE_RE = re.compile(r"<!--\s*gfm-math-lint-disable(?!\s*-next-line)(?:\s+(.*?))?\s*--!?>")
BLOCK_ENABLE_RE = re.compile(r"<!--\s*gfm-math-lint-enable(?:\s+(.*?))?\s*--!?>")
NEXT_LINE_DISABLE_RE = re.compile(r"<!--\s*gfm-math-lint-disable-next-line(?:\s+(.*?))?\s*--!?>")


@dataclass
class SuppressionManager:
    """Manages HTML comment directives for rule suppression."""

    # Map of line_number -> (all_disabled: bool, disabled_rules: set[str], enabled_exceptions: set[str])
    line_states: dict[int, tuple[bool, set[str], set[str]]] = field(default_factory=dict)

    @classmethod
    def parse_from_lines(cls, lines: Sequence[str], zones: list[DocumentZone] | None = None) -> SuppressionManager:
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


@runtime_checkable
class _TargetConfigurable(Protocol):
    target: str


@runtime_checkable
class _ExpensiveReadonlyRule(Protocol):
    is_expensive_readonly: bool


@dataclass(frozen=True)
class SpanDiffTelemetry:
    """Summary of differential math span emulation for a linted document."""

    intended_count: int = 0
    received_count: int = 0
    diffs: list[SpanDiff] = field(default_factory=list)


def violation_to_dict(v: Violation, file_path: str = "") -> dict[str, Any]:
    """Serialize a `Violation` to a JSON-compatible dictionary."""
    data: dict[str, Any] = {
        "rule_id": v.rule_id,
        "severity": v.severity,
        "line": v.line,
        "col": v.col,
        "message": v.message,
        "fixable": v.edit is not None,
    }
    if file_path:
        data["file"] = file_path
    return data


def span_diff_to_dict(d: SpanDiff) -> dict[str, Any]:
    """Serialize a `SpanDiff` to a JSON-compatible dictionary."""
    return {
        "category": d.category,
        "message": d.message,
        "intended": d.intended,
        "received": d.received,
        "line": d.line,
        "display": d.display,
    }


@dataclass
class LintResult:
    """Result of linting a file or string."""

    file_path: str
    violations: list[Violation]
    original_content: str
    fixed_content: str
    diff: str
    modified: bool = False
    fixed_violations: list[Violation] = field(default_factory=list)
    remaining_violations: list[Violation] = field(default_factory=list)
    span_diff: SpanDiffTelemetry = field(default_factory=SpanDiffTelemetry)

    def to_json_dict(self, target: str = "dual") -> dict[str, Any]:
        """Serialize this `LintResult` to a machine-readable JSON dictionary."""
        return {
            "file": self.file_path,
            "target": target,
            "modified": self.modified,
            "violations": [violation_to_dict(v) for v in self.violations],
            "fixed_violations": [violation_to_dict(v) for v in self.fixed_violations],
            "remaining_violations": [violation_to_dict(v) for v in self.remaining_violations],
            "span_diff": {
                "intended_count": self.span_diff.intended_count,
                "received_count": self.span_diff.received_count,
                "diffs": [span_diff_to_dict(d) for d in self.span_diff.diffs],
            },
        }


class Linter:
    """Core linting engine."""

    def __init__(
        self,
        config: LintConfig | None = None,
        rules: list[Rule] | None = None,
        root_dir: Path | None = None,
        enable_span_diff_fallback: bool | None = None,
    ) -> None:
        self.config = config or LintConfig()
        self.rules = rules if rules is not None else ALL_MARKDOWN_RULES
        self.root_dir = root_dir or Path.cwd()
        self.enable_span_diff_fallback = (
            (rules is None) if enable_span_diff_fallback is None else enable_span_diff_fallback
        )

    def _collect_raw_rule_violations(
        self,
        lines: Sequence[str],
        zones: list[DocumentZone],
        file_path: str,
        skip_expensive_readonly: bool = False,
    ) -> list[Violation]:
        raw_violations: list[Violation] = []
        for rule in self.rules:
            if self.config.is_rule_ignored(rule.id, file_path, self.root_dir):
                continue
            if skip_expensive_readonly and isinstance(rule, _ExpensiveReadonlyRule) and rule.is_expensive_readonly:
                continue
            if isinstance(rule, _TargetConfigurable):
                rule.target = self.config.target
            raw_violations.extend(rule.check(lines, zones, file_path))
        return raw_violations

    def _collect_violations(
        self,
        lines: Sequence[str],
        zones: list[DocumentZone],
        suppression: SuppressionManager,
        file_path: str,
        skip_expensive_readonly: bool = False,
    ) -> list[Violation]:
        """Run active rules and filter inline suppressions."""
        raw_violations = self._collect_raw_rule_violations(
            lines, zones, file_path, skip_expensive_readonly=skip_expensive_readonly
        )
        filtered = [v for v in raw_violations if not suppression.is_suppressed(v.rule_id, v.line)]
        return sorted(filtered, key=lambda v: (v.line, v.col))

    def _collect_span_diff_fallback(
        self,
        content: str,
        zones: list[DocumentZone],
        raw_rule_violations: list[Violation],
        suppression: SuppressionManager,
        file_path: str,
    ) -> tuple[SpanDiffTelemetry, list[Violation]]:
        """Run differential emulator and emit GFM-E01 for any unexplained span discrepancy."""
        emu = emulate_gfm_document(content)
        telemetry = SpanDiffTelemetry(
            intended_count=len(emu.intended_spans),
            received_count=len(emu.received_spans),
            diffs=list(emu.diffs),
        )
        if (
            not self.enable_span_diff_fallback
            or self.config.is_rule_ignored("GFM-E01", file_path, self.root_dir)
            or not emu.diffs
        ):
            return telemetry, []

        math_table_lines = {v.line for v in raw_rule_violations if v.rule_id.startswith(("GFM-M", "GFM-T"))}
        display_zone_ranges: dict[int, tuple[int, int]] = {
            z.start_line: (z.start_line, z.end_line) for z in zones if z.zone_type == Zone.DISPLAY_MATH
        }

        def _is_covered(line_no: int, is_display: bool) -> bool:
            if line_no in math_table_lines:
                return True
            if is_display and line_no in display_zone_ranges:
                start_ln, end_ln = display_zone_ranges[line_no]
                return any(start_ln <= ln <= end_ln for ln in math_table_lines)
            return False

        fallback: list[Violation] = []
        per_span_diffs = [d for d in emu.diffs if d.category in ("span-dropped", "span-mutated") and d.line > 0]
        for d in per_span_diffs:
            if _is_covered(d.line, d.display):
                continue
            if suppression.is_suppressed("GFM-E01", d.line):
                continue
            fallback.append(
                Violation(
                    rule_id="GFM-E01",
                    message=f"Unexplained GFM math span discrepancy ({d.category}): {d.message}",
                    line=d.line,
                    col=1,
                    severity="error",
                    edit=None,
                )
            )

        if (
            not per_span_diffs
            and any(d.category == "span-count-mismatch" for d in emu.diffs)
            and not math_table_lines
            and not suppression.is_suppressed("GFM-E01", 1)
        ):
            mismatch = next(d for d in emu.diffs if d.category == "span-count-mismatch")
            fallback.append(
                Violation(
                    rule_id="GFM-E01",
                    message=f"Unexplained GFM math span discrepancy ({mismatch.category}): {mismatch.message}",
                    line=1,
                    col=1,
                    severity="error",
                    edit=None,
                )
            )

        return telemetry, fallback

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

        raw_initial = self._collect_raw_rule_violations(lines, zones, file_path)
        rule_violations = sorted(
            (v for v in raw_initial if not suppression.is_suppressed(v.rule_id, v.line)),
            key=lambda v: (v.line, v.col),
        )
        initial_telemetry, initial_fallback = self._collect_span_diff_fallback(
            content, zones, raw_initial, suppression, file_path
        )
        sorted_violations = sorted([*rule_violations, *initial_fallback], key=lambda v: (v.line, v.col))

        if not fix:
            return LintResult(
                file_path=file_path,
                violations=sorted_violations,
                original_content=content,
                fixed_content=content,
                diff="",
                modified=False,
                fixed_violations=[],
                remaining_violations=sorted_violations,
                span_diff=initial_telemetry,
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
            iter_violations = self._collect_violations(
                iter_lines,
                iter_zones,
                iter_suppression,
                file_path,
                skip_expensive_readonly=True,
            )
            iter_edits: list[LintEdit] = [
                v.edit
                for v in iter_violations
                if v.edit is not None
                and not iter_suppression.is_edit_suppressed(v.rule_id, v.edit.start_line, v.edit.end_line)
            ]
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

        if current_content == content:
            post_violations = sorted_violations
            final_telemetry = initial_telemetry
        else:
            post_lines = current_content.splitlines(keepends=True)
            post_zones = scan_document_zones(post_lines)
            post_suppression = SuppressionManager.parse_from_lines(post_lines, post_zones)
            raw_post = self._collect_raw_rule_violations(post_lines, post_zones, file_path)
            post_rule_violations = sorted(
                (v for v in raw_post if not post_suppression.is_suppressed(v.rule_id, v.line)),
                key=lambda v: (v.line, v.col),
            )
            final_telemetry, post_fallback = self._collect_span_diff_fallback(
                current_content, post_zones, raw_post, post_suppression, file_path
            )
            post_violations = sorted([*post_rule_violations, *post_fallback], key=lambda v: (v.line, v.col))

        # Safe-Fix Guard (REG-22): roll back if fixing introduces a net-new unfixable violation
        initial_rule_ids = {v.rule_id for v in sorted_violations}
        if current_content != content and any(v.rule_id not in initial_rule_ids for v in post_violations):
            current_content = content
            post_violations = sorted_violations
            final_telemetry = initial_telemetry

        if current_content == content:
            fixed_violations: list[Violation] = []
            remaining_violations = sorted_violations
        elif not post_violations:
            fixed_violations = list(sorted_violations)
            remaining_violations = []
        else:
            rem_counts = Counter(v.rule_id for v in post_violations)
            kept_counts: Counter[str] = Counter()
            fixed_violations = []
            for v in reversed(sorted_violations):
                if kept_counts[v.rule_id] < rem_counts[v.rule_id]:
                    kept_counts[v.rule_id] += 1
                else:
                    fixed_violations.append(v)
            fixed_violations.reverse()
            remaining_violations = post_violations

        diff = generate_unified_diff(content, current_content, file_path)

        return LintResult(
            file_path=file_path,
            violations=sorted_violations,
            original_content=content,
            fixed_content=current_content,
            diff=diff,
            modified=(current_content != content),
            fixed_violations=fixed_violations,
            remaining_violations=remaining_violations,
            span_diff=final_telemetry,
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
