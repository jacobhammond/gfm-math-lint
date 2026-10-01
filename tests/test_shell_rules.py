"""Unit tests for GFM shell argument rules (GFM-S01)."""

from __future__ import annotations

from gfm_math_lint.rules.shell_rules import RuleS01


def test_rule_s01_unsafe_gh_pr_comment_expansion() -> None:
    rule = RuleS01()
    script = '#!/usr/bin/env bash\ngh pr comment $PR_NO --body "Calculated: $x_1$ ± $sigma$"\n'
    lines = script.splitlines(keepends=True)
    violations = rule.check(lines, [])
    assert len(violations) == 1
    assert violations[0].rule_id == "GFM-S01"
    assert "parameter expansion" in violations[0].message


def test_rule_s01_unsafe_gh_command_substitution() -> None:
    rule = RuleS01()
    script = '#!/usr/bin/env bash\ngh issue comment 42 -b "Result: $(date)"\n'
    lines = script.splitlines(keepends=True)
    violations = rule.check(lines, [])
    assert len(violations) == 1
    assert violations[0].rule_id == "GFM-S01"


def test_rule_s01_safe_heredoc_not_flagged() -> None:
    rule = RuleS01()
    safe_script = "#!/usr/bin/env bash\ngh pr comment $PR_NO --body-file - << 'EOF'\nCalculated: $x_1$ ± $sigma$\nEOF\n"
    lines = safe_script.splitlines(keepends=True)
    assert len(rule.check(lines, [])) == 0
