"""HTML buffer inspection oracle for live GitHub GFM rendering."""

from __future__ import annotations

import re
from html.parser import HTMLParser

from gfm_math_lint.emulator import find_colliding_math_underscores, has_block_interrupt
from gfm_math_lint.rules.math_rules import TEXT_MACROS, find_macro_calls, is_valid_display_math_pad
from gfm_math_lint.tokenizer import Zone, scan_document_zones, scan_inline_spans


class BufferedGFMVerifier(HTMLParser):
    """Inspects rendered GFM HTML with cross-tag text buffering to prevent slice blindness."""

    def __init__(self, file_path: str = "") -> None:
        super().__init__()
        self.file_path = file_path
        self.block_buffer: list[str] = []
        self.in_block = False
        self.in_code = False
        self.in_math_renderer = False
        self.anomalies: list[str] = []

        # Table validation
        self.in_table = False
        self.current_table_rows: list[int] = []
        self.current_row_cols = 0

        # Mermaid inspection
        self.in_mermaid = False
        self.mermaid_buffer: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)

        if tag in ("p", "li", "td", "th", "blockquote"):
            self.in_block = True
            self.block_buffer.clear()

        elif tag in ("pre", "code"):
            self.in_code = True
            class_val = attrs_dict.get("class", "") or ""
            if "mermaid" in class_val or "language-mermaid" in class_val:
                self.in_mermaid = True
                self.mermaid_buffer.clear()

        elif tag == "math-renderer":
            self.in_math_renderer = True

        elif self.in_math_renderer:
            # Tag pollution: <em>, <strong>, <br> inside math renderer
            if tag in ("em", "strong", "br", "i", "b", "a"):
                self.anomalies.append(f"Markdown syntax collision: HTML tag <{tag}> was parsed inside <math-renderer>.")

        if tag == "table":
            self.in_table = True
            self.current_table_rows = []
        elif tag == "tr" and self.in_table:
            self.current_row_cols = 0
        elif tag in ("td", "th") and self.in_table:
            self.current_row_cols += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in ("p", "li", "td", "th", "blockquote"):
            self._evaluate_block("".join(self.block_buffer))
            self.in_block = False
            self.block_buffer.clear()

        elif tag in ("pre", "code"):
            if self.in_mermaid:
                self._evaluate_mermaid("".join(self.mermaid_buffer))
                self.in_mermaid = False
                self.mermaid_buffer.clear()
            self.in_code = False

        elif tag == "math-renderer":
            self.in_math_renderer = False

        elif tag == "tr" and self.in_table:
            self.current_table_rows.append(self.current_row_cols)

        elif tag == "table":
            self.in_table = False
            if self.current_table_rows:
                unique_counts = set(self.current_table_rows)
                if len(unique_counts) > 1:
                    self.anomalies.append(
                        f"Table column count mismatch across rows: {self.current_table_rows}. "
                        "Unescaped pipes in math or prose broke table structure."
                    )

    def handle_data(self, data: str) -> None:
        if self.in_mermaid:
            self.mermaid_buffer.append(data)
        elif self.in_block and not self.in_code and not self.in_math_renderer:
            self.block_buffer.append(data)

    def _evaluate_block(self, text: str) -> None:
        # Check 1: Literal unrendered display math delimiter in plain prose
        if "$$" in text:
            snippet = text.strip()[:60]
            self.anomalies.append(f"Unrendered '$$' delimiter found in block: '{snippet}...'")

        # Check 2: Raw LaTeX command leaked outside math-renderer
        m = re.search(r"\\[a-zA-Z]{3,}\{", text)
        if m:
            snippet = text.strip()[:60]
            self.anomalies.append(f"Leaked LaTeX command outside math-renderer: '{snippet}...'")

    def _evaluate_mermaid(self, text: str) -> None:
        # Check for literal newline string (\n or \\n) in node labels
        # e.g. A[Label\nText] or B("Line\nBreak")
        if re.search(r"(\[|\(|\{|\(\()([^\n\]\)\}]+)\\n([^\n\]\)\}]+)(\]|\)|\}|\)\))", text):
            self.anomalies.append("Literal '\\n' sequence found in Mermaid node label instead of <br>.")


def verify_rendered_gfm(html_content: str, file_path: str = "") -> list[str]:
    """Parse rendered GFM HTML and return all detected anomalies."""
    verifier = BufferedGFMVerifier(file_path=file_path)
    verifier.feed(html_content)
    verifier.close()
    return verifier.anomalies


def render_gfm_offline_or_online(
    markdown_content: str,
    token: str | None = None,
    offline: bool = False,
) -> str:
    """Render markdown using cmarkgfm if available, GitHub API if online, or local heuristic fallback."""
    # 1. Accelerated sub-millisecond local compiler if cmarkgfm is installed
    try:
        import cmarkgfm  # type: ignore[import-not-found]

        return str(cmarkgfm.github_flavored_markdown_to_html(markdown_content))
    except ImportError:
        pass

    # 2. Live GitHub API if not forced offline
    if not offline:
        try:
            from gfm_math_lint.verifier import render_gfm

            return render_gfm(markdown_content, token=token)
        except Exception:
            pass

    # 3. Offline heuristic rendering fallback powered by Block-Context Tokenizer & Emulator
    lines = markdown_content.splitlines(keepends=True)
    zones = scan_document_zones(lines)
    html_parts: list[str] = []

    def _render_inline_line(line_text: str, line_no: int) -> str:
        spans = scan_inline_spans(line_text.rstrip("\r\n"), line_no)
        colliding = find_colliding_math_underscores(
            spans,
            macro_ranges_fn=lambda txt: [(s, e) for _, _, _, s, e in find_macro_calls(txt, TEXT_MACROS)],
        )
        has_underscore_collision = bool(colliding)
        parts: list[str] = []
        raw_line = line_text.rstrip("\r\n")

        for span in spans:
            if span.zone_type == Zone.INLINE_CODE:
                parts.append(f"<code>{span.content}</code>")
            elif span.zone_type == Zone.COMMENT:
                parts.append(span.raw)
            elif (span.zone_type == Zone.INLINE_MATH and span.delimiter == "$`") or (
                span.zone_type == Zone.DISPLAY_MATH and span.delimiter == "$$"
            ):
                parts.append(f"<math-renderer>{span.raw}</math-renderer>")
            elif span.zone_type == Zone.INLINE_MATH and span.delimiter == "$":
                open_idx = span.start_col - 1
                close_idx = span.end_col - 1
                bad_open = open_idx > 0 and (
                    raw_line[open_idx - 1] in ("-", "\u2013", "\u2014", "/") or raw_line[open_idx - 1].isalnum()
                )
                bad_close = close_idx < len(raw_line) and raw_line[close_idx].isalnum()
                if bad_open or bad_close:
                    parts.append(span.raw)
                elif has_underscore_collision and re.search(r"(?<!\\)_", span.content):
                    corrupted = re.sub(r"(?<!\\)_([a-zA-Z0-9\\{}]+)(?<!\\)_", r"<em>\1</em>", span.raw)
                    if "<em>" not in corrupted:
                        corrupted = re.sub(r"(?<!\\)_", "<em>_</em>", span.raw, count=1)
                    parts.append(f"<math-renderer>{corrupted}</math-renderer>")
                else:
                    parts.append(f"<math-renderer>{span.raw}</math-renderer>")
            else:
                parts.append(span.raw)

        rendered = "".join(parts)
        if has_underscore_collision and "<em>" not in rendered:
            rendered = re.sub(r"(?<!\\)_([^_\n]+?)(?<!\\)_", r"<em>\1</em>", rendered)
        return rendered

    for idx, zone in enumerate(zones):
        if zone.zone_type in (Zone.FRONTMATTER, Zone.COMMENT):
            continue

        if zone.zone_type == Zone.FENCED_CODE:
            info = zone.info.strip()
            inner_lines = zone.lines[1:-1] if zone.is_closed and len(zone.lines) >= 2 else zone.lines[1:]
            if info.lower() == "math":
                stripped_math_lines = [
                    re.sub(r"^\s*(?:>\s*)+", "", ln)
                    if (zone.parent_block == "blockquote" or ln.lstrip().startswith(">"))
                    else ln
                    for ln in inner_lines
                ]
                inner_text = "".join(stripped_math_lines).strip()
                html_parts.append(f'<math-renderer class="js-display-math">$${inner_text}$$</math-renderer>')
            else:
                inner_text = "".join(inner_lines).strip()
                html_parts.append(f'<pre><code class="language-{info}">\n{inner_text}\n</code></pre>')
            continue

        if zone.zone_type == Zone.DISPLAY_MATH:
            inner_lines = zone.lines[1:-1] if zone.is_closed and len(zone.lines) >= 2 else zone.lines[1:]
            stripped_inner = [
                re.sub(r"^\s*(?:>\s*)+", "", ln)
                if (zone.parent_block == "blockquote" or ln.lstrip().startswith(">"))
                else ln
                for ln in inner_lines
            ]
            has_internal_blank = any(ln.strip() == "" for ln in stripped_inner)

            is_bq = zone.parent_block == "blockquote"
            prev_valid = (
                idx == 0 or not zones[idx - 1].lines or is_valid_display_math_pad(zones[idx - 1].lines[-1], is_bq)
            )
            next_valid = (
                idx + 1 >= len(zones)
                or not zones[idx + 1].lines
                or is_valid_display_math_pad(zones[idx + 1].lines[0], is_bq)
            )
            pad_above_ok = prev_valid
            pad_below_ok = next_valid

            valid_display = (
                zone.is_closed
                and zone.indent_level == 0
                and not has_internal_blank
                and not has_block_interrupt(stripped_inner)
                and pad_above_ok
                and pad_below_ok
            )
            if valid_display:
                inner_tex = "".join(stripped_inner).strip()
                html_parts.append(f'<math-renderer class="js-display-math">$${inner_tex}$$</math-renderer>')
            else:
                html_parts.append(f"<p>{zone.content.strip()}</p>")
            continue

        if zone.zone_type == Zone.TABLE:
            html_parts.append("<table>")
            for r_idx, row in enumerate(zone.lines):
                stripped_row = row.strip()
                if re.match(r"^\|?\s*:?-+[-:| ]*\|?$", stripped_row):
                    continue
                inner_row = stripped_row[1:] if stripped_row.startswith("|") else stripped_row
                if inner_row.endswith("|") and not inner_row.endswith("\\|"):
                    inner_row = inner_row[:-1]
                cells = re.split(r"(?<!\\)\|", inner_row)
                html_parts.append("<tr>")
                for cell in cells:
                    rendered_cell = _render_inline_line(cell.strip(), zone.start_line + r_idx)
                    html_parts.append(f"<td>{rendered_cell}</td>")
                html_parts.append("</tr>")
            html_parts.append("</table>")
            continue

        if zone.zone_type == Zone.PROSE:
            raw_prose = zone.content.rstrip("\r\n")
            if not raw_prose.strip():
                continue
            if raw_prose.lstrip().startswith("#"):
                html_parts.append(f"<h1>{_render_inline_line(raw_prose, zone.start_line)}</h1>")
            elif zone.indent_level > 0 and re.match(r"^\s*\$\$.*\$\$\s*$", raw_prose):
                html_parts.append(f"<p>{raw_prose.strip()}</p>")
            else:
                html_parts.append(f"<p>{_render_inline_line(raw_prose, zone.start_line)}</p>")

    return "\n".join(html_parts)
