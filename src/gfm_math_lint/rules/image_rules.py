"""GFM Image format enforcement rules (GFM-I01)."""

from __future__ import annotations

import os
import re

from gfm_math_lint.rules.base import Rule, Violation
from gfm_math_lint.tokenizer import DocumentZone, Zone, scan_inline_spans

SUPPORTED_CONVERT_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
IMAGE_LINK_RE = re.compile(r"!\[(.*?)\]\(([^)]+)\)")


class RuleI01(Rule):
    """GFM-I01: Non-AVIF Image Format Rule."""

    id: str = "GFM-I01"
    name: str = "image-avif-format"
    description: str = "Enforce .avif format for markdown images and figures"
    severity: str = "warning"

    def check(self, lines: list[str], zones: list[DocumentZone], file_path: str = "") -> list[Violation]:
        violations: list[Violation] = []

        for zone in zones:
            if zone.zone_type in (Zone.PROSE, Zone.TABLE):
                for line_idx, line in enumerate(zone.lines):
                    line_no = zone.start_line + line_idx
                    spans = scan_inline_spans(line, line_no)
                    code_spans = [
                        (s.start_col, s.end_col) for s in spans if s.zone_type in (Zone.INLINE_CODE, Zone.COMMENT)
                    ]

                    # Match markdown image links: ![alt](path/to/img.ext)
                    for m in IMAGE_LINK_RE.finditer(line):
                        col_start = m.start() + 1
                        col_end = m.end() + 1

                        # Skip matches inside inline code spans
                        if any(c_start <= col_start and col_end <= c_end for c_start, c_end in code_spans):
                            continue

                        raw_target = m.group(2).strip()
                        parts = raw_target.split(maxsplit=1)
                        if not parts:
                            continue
                        img_path_str = parts[0]

                        # Ignore web links
                        if img_path_str.startswith(("http://", "https://", "//")):
                            continue

                        # Extract extension
                        ext = os.path.splitext(img_path_str)[1].lower()
                        if ext in SUPPORTED_CONVERT_EXTS:
                            base_no_ext = os.path.splitext(img_path_str)[0]
                            avif_path_str = f"{base_no_ext}.avif"

                            violations.append(
                                Violation(
                                    rule_id=self.id,
                                    message=(
                                        f"Non-AVIF image '{img_path_str}' detected. "
                                        f"Convert to AVIF format ({avif_path_str}) for optimal performance."
                                    ),
                                    line=line_no,
                                    col=col_start,
                                    severity=self.severity,
                                    edit=None,
                                )
                            )

        return violations
