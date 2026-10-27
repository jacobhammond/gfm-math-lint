"""Math expression extractor for Markdown documents."""

from __future__ import annotations

import re

from gfm_math_lint.tokenizer import Zone, scan_document_zones, scan_inline_spans

_DISPLAY_MATH_OPEN_CLOSE_RE = re.compile(r"^\s*\$\$\s*|\s*\$\$\s*$")


def extract_math_blocks(markdown_content: str) -> list[tuple[str, bool]]:
    """Extract all mathematical expressions from a Markdown document.

    Returns a list of tuples: (math_content, is_display_block).
    """
    lines = markdown_content.splitlines(keepends=True)
    if not lines:
        return []

    zones = scan_document_zones(lines)
    math_blocks: list[tuple[str, bool]] = []

    for zone in zones:
        if zone.zone_type == Zone.DISPLAY_MATH:
            # Strip outer $$ lines or markers
            inner_lines: list[str] = []
            for idx, line in enumerate(zone.lines):
                line_content = line.strip()
                if idx == 0 and line_content.startswith("$$"):
                    line_content = line_content[2:].strip()
                if (idx == len(zone.lines) - 1 or len(zone.lines) == 1) and line_content.endswith("$$"):
                    line_content = line_content[:-2].strip()
                if line_content:
                    inner_lines.append(line_content)
            display_content = "\n".join(inner_lines).strip()
            if display_content:
                math_blocks.append((display_content, True))

        elif zone.zone_type == Zone.FENCED_CODE and zone.info.strip().lower() == "math":
            # Extract fenced math code block content (excluding fence lines)
            fence_lines = zone.lines
            content_lines = fence_lines[1:-1] if len(fence_lines) >= 2 else fence_lines
            math_text = "".join(content_lines).strip()
            if math_text:
                math_blocks.append((math_text, True))

        elif zone.zone_type in (Zone.PROSE, Zone.TABLE):
            for rel_idx, line in enumerate(zone.lines):
                line_no = zone.start_line + rel_idx
                spans = scan_inline_spans(line, line_no)
                for span in spans:
                    if span.zone_type == Zone.INLINE_MATH:
                        content = span.content.strip()
                        if content:
                            math_blocks.append((content, False))

    return math_blocks
