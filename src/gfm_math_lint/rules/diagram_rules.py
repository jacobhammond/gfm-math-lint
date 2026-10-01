"""GFM Mermaid diagram and fence symmetry rules (GFM-D01, GFM-D02)."""

from __future__ import annotations

import re

from gfm_math_lint.rules.base import Rule, Violation
from gfm_math_lint.tokenizer import DocumentZone, Zone

MERMAID_SUBGRAPH_ARROW_RE = re.compile(r"^subgraph\s+.*?(?:-->|---|==>|-\.->)")
MERMAID_LINK_RE = re.compile(
    r"(?:\s+--\s+[^-]+?\s+-->|\s+-\.\s+[^\.]+?\s+\.->|\s+==\s+[^=]+?\s+==>|-->\|[^|]+\||-->|---|==>|-\.->)"
)


class RuleD01(Rule):
    """GFM-D01: Explicit Subgraph & Node Label Identifier Enforcement."""

    id: str = "GFM-D01"
    name: str = "mermaid-identifier"
    description: str = "Enforce alphanumeric IDs for Mermaid subgraphs and multi-word node labels"
    severity: str = "warning"

    def check(self, lines: list[str], zones: list[DocumentZone], file_path: str = "") -> list[Violation]:
        violations: list[Violation] = []

        for zone in zones:
            if zone.zone_type == Zone.FENCED_CODE and zone.info.strip().lower() == "mermaid":
                for line_idx, line in enumerate(zone.lines):
                    line_no = zone.start_line + line_idx
                    stripped = line.strip()

                    # Check for subgraph declaration containing arrows/links (invalid Mermaid syntax)
                    if MERMAID_SUBGRAPH_ARROW_RE.match(stripped):
                        violations.append(
                            Violation(
                                rule_id=self.id,
                                message=(
                                    "Mermaid subgraph declaration contains link arrows. "
                                    "Use 'subgraph ID [\"Label\"]' without arrows."
                                ),
                                line=line_no,
                                col=1,
                                severity=self.severity,
                            )
                        )
                        continue

                    # Check for node identifier with spaces without brackets before a link:
                    # e.g. "Node Alpha --> Node Beta" vs "A -- yes --> B"
                    m_link = MERMAID_LINK_RE.search(stripped)
                    if m_link and not stripped.startswith("subgraph"):
                        left_side = stripped[: m_link.start()].strip()
                        # If left side has spaces and doesn't end with a bracket/paren/quote
                        if " " in left_side and not left_side.endswith(("]", ")", "}", '"', "'")):
                            violations.append(
                                Violation(
                                    rule_id=self.id,
                                    message=(
                                        f"Mermaid node identifier '{left_side}' contains spaces without "
                                        "explicit label. Use an alphanumeric ID with a quoted label like "
                                        "'ID[\"Label Text\"]'."
                                    ),
                                    line=line_no,
                                    col=1,
                                    severity=self.severity,
                                )
                            )

        return violations


class RuleD02(Rule):
    """GFM-D02: Code Block Fence Boundary Symmetry."""

    id: str = "GFM-D02"
    name: str = "fence-boundary-symmetry"
    description: str = "Enforce symmetric opening and closing code block fences"
    severity: str = "error"

    def check(self, lines: list[str], zones: list[DocumentZone], file_path: str = "") -> list[Violation]:
        violations: list[Violation] = []

        for zone in zones:
            if zone.zone_type == Zone.FENCED_CODE and not zone.is_closed:
                violations.append(
                    Violation(
                        rule_id=self.id,
                        message=(
                            f"Unclosed code fence block opened with '{zone.fence_char * zone.fence_len}'. "
                            "Ensure every code fence has a matching closing fence."
                        ),
                        line=zone.start_line,
                        col=1,
                        severity=self.severity,
                    )
                )

        return violations
