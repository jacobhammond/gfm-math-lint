"""Rule registry for gfm-math-lint."""

from __future__ import annotations

from typing import TYPE_CHECKING

from gfm_math_lint.rules.base import Rule, Violation

if TYPE_CHECKING:
    from collections.abc import Sequence

    from gfm_math_lint.tokenizer import DocumentZone
from gfm_math_lint.rules.code_rules import RuleC01, RuleC02, RuleC03
from gfm_math_lint.rules.diagram_rules import RuleD01, RuleD02, RuleD03, RuleD04, RuleD05, RuleD06
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
    RuleM14,
    RuleM15,
    RuleM16,
    RuleM17,
    RuleM18,
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
    RuleM14(),
    RuleM15(),
    RuleM16(),
    RuleM17(),
    RuleM18(),
]

ALL_TABLE_RULES: list[Rule] = [
    RuleT01(),
]

ALL_CODE_RULES: list[Rule] = [
    RuleC01(),
    RuleC02(),
    RuleC03(),
]

ALL_DIAGRAM_RULES: list[Rule] = [
    RuleD01(),
    RuleD02(),
    RuleD03(),
    RuleD04(),
    RuleD05(),
    RuleD06(),
]

ALL_MARKDOWN_RULES: list[Rule] = [
    *ALL_MATH_RULES,
    *ALL_TABLE_RULES,
    *ALL_CODE_RULES,
    *ALL_DIAGRAM_RULES,
]

ALL_SHELL_RULES: list[Rule] = [
    RuleS01(),
]


class RuleE01(Rule):
    """GFM-E01: Unexplained GFM math span discrepancy detected by the differential emulator."""

    id: str = "GFM-E01"
    name: str = "unexplained-span-diff"
    description: str = "Fallback diagnostic for unexplained GFM math span discrepancies detected by emulator"
    severity: str = "error"

    def check(self, lines: Sequence[str], zones: list[DocumentZone], file_path: str = "") -> list[Violation]:
        """Evaluated directly by Linter's differential span-diff fallback."""
        return []


RULE_MAP: dict[str, Rule] = {
    **{rule.id: rule for rule in (*ALL_MARKDOWN_RULES, *ALL_SHELL_RULES)},
    "GFM-E01": RuleE01(),
}


def get_rule_by_id(rule_id: str) -> Rule | None:
    """Retrieve rule instance by its ID (e.g. GFM-M01)."""
    return RULE_MAP.get(rule_id.upper())


__all__ = [
    "ALL_CODE_RULES",
    "ALL_DIAGRAM_RULES",
    "ALL_MARKDOWN_RULES",
    "ALL_MATH_RULES",
    "ALL_SHELL_RULES",
    "ALL_TABLE_RULES",
    "RULE_MAP",
    "Rule",
    "RuleC01",
    "RuleC02",
    "RuleC03",
    "RuleD01",
    "RuleD02",
    "RuleD03",
    "RuleD04",
    "RuleD05",
    "RuleD06",
    "RuleE01",
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
    "RuleM14",
    "RuleM15",
    "RuleM16",
    "RuleM17",
    "RuleM18",
    "RuleS01",
    "RuleT01",
    "Violation",
    "get_rule_by_id",
]
