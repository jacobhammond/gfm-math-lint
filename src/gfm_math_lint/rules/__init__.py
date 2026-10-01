"""Rule registry for gfm-math-lint."""

from __future__ import annotations

from gfm_math_lint.rules.base import Rule, Violation
from gfm_math_lint.rules.code_rules import RuleC01, RuleC02
from gfm_math_lint.rules.diagram_rules import RuleD01, RuleD02
from gfm_math_lint.rules.image_rules import RuleI01
from gfm_math_lint.rules.math_rules import (
    RuleM01,
    RuleM02,
    RuleM03,
    RuleM04,
    RuleM05,
    RuleM06,
    RuleM07,
    RuleM08,
    RuleM09,
    RuleM10,
    RuleM11,
    RuleM12,
    RuleM13,
)
from gfm_math_lint.rules.shell_rules import RuleS01
from gfm_math_lint.rules.table_rules import RuleT01

ALL_MATH_RULES: list[Rule] = [
    RuleM01(),
    RuleM02(),
    RuleM03(),
    RuleM04(),
    RuleM05(),
    RuleM06(),
    RuleM07(),
    RuleM08(),
    RuleM09(),
    RuleM10(),
    RuleM11(),
    RuleM12(),
    RuleM13(),
]

ALL_TABLE_RULES: list[Rule] = [
    RuleT01(),
]

ALL_CODE_RULES: list[Rule] = [
    RuleC01(),
    RuleC02(),
]

ALL_DIAGRAM_RULES: list[Rule] = [
    RuleD01(),
    RuleD02(),
]

ALL_IMAGE_RULES: list[Rule] = [
    RuleI01(),
]

ALL_MARKDOWN_RULES: list[Rule] = [
    *ALL_MATH_RULES,
    *ALL_TABLE_RULES,
    *ALL_CODE_RULES,
    *ALL_DIAGRAM_RULES,
    *ALL_IMAGE_RULES,
]

ALL_SHELL_RULES: list[Rule] = [
    RuleS01(),
]

RULE_MAP: dict[str, Rule] = {rule.id: rule for rule in (*ALL_MARKDOWN_RULES, *ALL_SHELL_RULES)}


def get_rule_by_id(rule_id: str) -> Rule | None:
    """Retrieve rule instance by its ID (e.g. GFM-M01)."""
    return RULE_MAP.get(rule_id.upper())


__all__ = [
    "ALL_CODE_RULES",
    "ALL_DIAGRAM_RULES",
    "ALL_IMAGE_RULES",
    "ALL_MARKDOWN_RULES",
    "ALL_MATH_RULES",
    "ALL_SHELL_RULES",
    "ALL_TABLE_RULES",
    "RULE_MAP",
    "Rule",
    "RuleC01",
    "RuleC02",
    "RuleD01",
    "RuleD02",
    "RuleI01",
    "RuleM01",
    "RuleM02",
    "RuleM03",
    "RuleM04",
    "RuleM05",
    "RuleM06",
    "RuleM07",
    "RuleM08",
    "RuleM09",
    "RuleM10",
    "RuleM11",
    "RuleM12",
    "RuleM13",
    "RuleS01",
    "RuleT01",
    "Violation",
    "get_rule_by_id",
]
