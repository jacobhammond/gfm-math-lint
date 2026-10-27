"""HTML buffer inspection oracle for live GitHub GFM rendering."""

from __future__ import annotations

import re
from html.parser import HTMLParser


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

    # 3. Offline heuristic rendering fallback
    # Minimal standard conversion for local/offline testing without external network
    lines = markdown_content.splitlines()
    html_parts: list[str] = []
    in_code = False
    code_fence = ""

    # Pattern for backtick math: $`...`$ (immune to emphasis collisions)
    backtick_math_pattern = re.compile(r"\$`([^`]+)`\$")
    # Pattern for inline math: $...$
    inline_math_pattern = re.compile(r"(?<!\\)\$(?!\$)([^\$\n]+?)(?<!\\)\$")

    for line in lines:
        if line.startswith("```"):
            if in_code and line.startswith(code_fence):
                in_code = False
                html_parts.append("</code></pre>")
            else:
                in_code = True
                code_fence = line[:3]
                info = line[3:].strip()
                html_parts.append(f'<pre><code class="language-{info}">')
            continue

        if in_code:
            html_parts.append(line)
            continue

        stripped = line.strip()
        if stripped.startswith("$$") and stripped.endswith("$$") and len(stripped) > 2:
            html_parts.append(f"<math-renderer>{stripped}</math-renderer>")
        elif stripped == "$$":
            html_parts.append("<p>$$</p>")
        else:
            # Check for underscore emphasis collisions: e.g. $P\_...$ vs $P_...$ and $P_...$
            processed_line = line

            # Convert backtick math to math-renderer (immune to underscore collision)
            processed_line = backtick_math_pattern.sub(r"<math-renderer>$`\1`$</math-renderer>", processed_line)

            # If unescaped underscores exist across multiple inline dollar spans:
            # e.g. "$P_{primary}$ and $P_{secondary}$"
            # CommonMark treats unescaped underscores as <em> delimiters
            # If they are escaped as "\_" or inside backticks, they don't collide
            raw_dollars = inline_math_pattern.findall(processed_line)
            has_collision = False
            if len(raw_dollars) >= 2:
                # Check if multiple spans contain unescaped underscores
                sub_count = sum(1 for d in raw_dollars if re.search(r"(?<!\\)_", d))
                if sub_count >= 2:
                    has_collision = True

            if has_collision:
                # GitHub CommonMark corrupts this by injecting <em> across spans
                # Replace with simulated corrupted HTML containing <em>
                processed_line = re.sub(
                    r"(?<!\\)_([a-zA-Z0-9\\]+)(?<!\\)_",
                    r"<em>\1</em>",
                    processed_line,
                )
            else:
                processed_line = inline_math_pattern.sub(r"<math-renderer>$\1$</math-renderer>", processed_line)

            html_parts.append(f"<p>{processed_line}</p>")

    return "\n".join(html_parts)
