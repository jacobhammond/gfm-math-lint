"""GFM Rendering Oracle and HTML Verification Engine."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
import webbrowser
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path


@dataclass
class VerificationIssue:
    """An issue detected during GFM HTML verification."""

    category: str
    message: str
    snippet: str
    file_path: str = ""


# Indicators that text containing '$' is broken math rather than currency
_MATH_SYNTAX_RE = re.compile(
    r"(\$\$[^\$]+\$\$|"  # display math pair $$...$$
    r"\$[^\$\n]*\\[a-zA-Z]+[^\$\n]*\$|"  # inline math containing LaTeX command
    r"\$[^\$\n]*[_^{}][^\$\n]*\$|"  # inline math containing subscript/superscript/grouping
    r"\$[^\$\n]*[=<>\\+\\-][^\$\n]*\$|"  # inline math containing operators
    r"\$[0-9.]+\$|"  # inline number math like $0.759$ or $3.6$
    r"\$[^\$\s]+\$[a-zA-Z]|"  # closing delimiter glued to unit like $0.759$dB or $15\ ^\circ$C
    r"[-/\u2013\u2014]\$[a-zA-Z0-9]|"  # hyphen/dash/slash followed by opening math delimiter
    r"\$[a-zA-Z]\$|"  # single-letter inline math ($x$, $V$)
    r"\\text\{|\\frac\{|\\sqrt\{|\\partial|\\alpha|\\beta|\\gamma|\\Delta|\\lambda|\\mu|\\pi)"  # LaTeX macro
)


class GFMHTMLValidator(HTMLParser):
    """Parses rendered GFM HTML to verify math rendering, table integrity, and syntax."""

    def __init__(self, file_path: str = "") -> None:
        super().__init__()
        self.file_path = file_path
        self.issues: list[VerificationIssue] = []

        self.in_math_renderer = False
        self.math_renderer_depth = 0
        self.pre_depth = 0
        self.code_depth = 0
        self.current_table_rows: list[int] = []
        self.current_row_cols = 0
        self.in_table = False

    @property
    def in_code_block(self) -> bool:
        return self.pre_depth > 0 or self.code_depth > 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)

        if tag == "math-renderer":
            self.in_math_renderer = True
            self.math_renderer_depth += 1

        elif self.in_math_renderer:
            # Detect HTML tag pollution inside math-renderer (e.g. <em>, <strong>, <a>, <br>)
            if tag in ("em", "strong", "a", "br", "i", "b"):
                self.issues.append(
                    VerificationIssue(
                        category="tag-pollution",
                        message=(
                            f"Markdown syntax collision: HTML tag <{tag}> was parsed inside <math-renderer>. "
                            "Subscripts or asterisks must be escaped with backslash."
                        ),
                        snippet=f"<{tag}> inside <math-renderer>",
                        file_path=self.file_path,
                    )
                )

        if tag == "pre":
            self.pre_depth += 1
        elif tag == "code":
            self.code_depth += 1

        # Check for KaTeX parse error class
        class_val = attrs_dict.get("class", "")
        if class_val and "katex-error" in class_val:
            title_val = attrs_dict.get("title", "")
            self.issues.append(
                VerificationIssue(
                    category="katex-error",
                    message=f"KaTeX parse error encountered in rendered HTML: {title_val or 'syntax error'}",
                    snippet=title_val or class_val,
                    file_path=self.file_path,
                )
            )

        if tag == "table":
            self.in_table = True
            self.current_table_rows = []

        elif tag == "tr" and self.in_table:
            self.current_row_cols = 0

        elif tag in ("td", "th") and self.in_table:
            self.current_row_cols += 1

    def handle_endtag(self, tag: str) -> None:
        if tag == "math-renderer":
            self.math_renderer_depth = max(0, self.math_renderer_depth - 1)
            if self.math_renderer_depth == 0:
                self.in_math_renderer = False

        elif tag == "pre":
            self.pre_depth = max(0, self.pre_depth - 1)
        elif tag == "code":
            self.code_depth = max(0, self.code_depth - 1)

        elif tag == "tr" and self.in_table:
            self.current_table_rows.append(self.current_row_cols)

        elif tag == "table":
            self.in_table = False
            if self.current_table_rows:
                # Check for table column count consistency
                unique_counts = set(self.current_table_rows)
                if len(unique_counts) > 1:
                    self.issues.append(
                        VerificationIssue(
                            category="table-mismatch",
                            message=(
                                f"Table column count mismatch detected across rows: {self.current_table_rows}. "
                                "Ensure table cells do not contain unescaped pipe '|' delimiters."
                            ),
                            snippet=f"Column counts: {self.current_table_rows}",
                            file_path=self.file_path,
                        )
                    )

    def handle_data(self, data: str) -> None:
        if not self.in_math_renderer and not self.in_code_block and "$" in data:
            match = _MATH_SYNTAX_RE.search(data)
            if match:
                snippet = match.group(0).strip()
                # Capture surrounding context for the snippet
                start = max(0, match.start() - 20)
                end = min(len(data), match.end() + 20)
                context_snippet = data[start:end].replace("\n", " ").strip()
                self.issues.append(
                    VerificationIssue(
                        category="unrendered-math",
                        message=(
                            f"Unrendered math expression detected in plain text outside <math-renderer>: '{snippet}'"
                        ),
                        snippet=f"...{context_snippet}...",
                        file_path=self.file_path,
                    )
                )


def render_gfm(markdown_content: str, token: str | None = None) -> str:
    """Render markdown using GitHub API.

    If an explicit token is passed, uses standard library urllib.request directly
    with the provided token. Otherwise, tries the GitHub CLI ('gh') first if available,
    and falls back to direct HTTPS call via standard library urllib.request.
    """
    if not token:
        gh_bin = shutil.which("gh")
        if gh_bin:
            try:
                payload = json.dumps({"text": markdown_content, "mode": "gfm"})
                proc = subprocess.run(
                    [gh_bin, "api", "/markdown", "--input", "-"],
                    input=payload.encode("utf-8"),
                    capture_output=True,
                    shell=False,
                    check=True,
                    timeout=30,
                )
                return proc.stdout.decode("utf-8")
            except (subprocess.SubprocessError, OSError):
                # Fall back to HTTPS request below
                pass

    # Direct GitHub REST API fallback
    url = "https://api.github.com/markdown"
    headers = {
        "User-Agent": "gfm-math-lint",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
    }

    auth_token = token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    req_data = json.dumps({"text": markdown_content, "mode": "gfm"}).encode("utf-8")
    req = urllib.request.Request(url, data=req_data, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=30) as response:  # nosec: B310
            content_bytes: bytes = response.read()
            return content_bytes.decode("utf-8")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub Markdown API error ({e.code} {e.reason}): {body}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Failed to connect to GitHub Markdown API: {e.reason}") from e


def _clean_math_entities(html_str: str) -> str:
    """Unescape double-escaped HTML entities inside math-renderer tags.

    GitHub's API /markdown serializes GFM into HTML where math formulas
    containing '<', '>', '&' get double-escaped (e.g. '>' -> '&gt;' -> '&amp;gt;').
    Unescaping '&amp;...' inside math-renderer tags restores valid HTML entities
    ('&gt;', '&lt;', '&amp;') so they are properly decoded into characters by the
    browser DOM.
    """

    def repl(m: re.Match[str]) -> str:
        open_tag = m.group(1)
        content = m.group(2)
        close_tag = m.group(3)
        content = (
            content.replace("&amp;gt;", "&gt;")
            .replace("&amp;lt;", "&lt;")
            .replace("&amp;amp;", "&amp;")
            .replace("&amp;quot;", "&quot;")
            .replace("&amp;#39;", "&#39;")
        )
        return f"{open_tag}{content}{close_tag}"

    return re.sub(r"(<math-renderer\b[^>]*>)([\s\S]*?)(</math-renderer>)", repl, html_str, flags=re.IGNORECASE)


def build_preview_html(body_html: str, title: str = "GFM Math Preview") -> str:
    """Wrap rendered GFM HTML with KaTeX client rendering and clean typography."""
    body_html = _clean_math_entities(body_html)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <link rel="stylesheet"
    href="https://cdn.jsdelivr.net/npm/katex@0.16.21/dist/katex.min.css"
    integrity="sha384-zh0CIslj+VczCZtlzBcjt5ppRcsAmDnRem7ESsYwWwg3m/OaJ2l4x7YBZl9Kxxib"
    crossorigin="anonymous">
  <script defer
    src="https://cdn.jsdelivr.net/npm/katex@0.16.21/dist/katex.min.js"
    integrity="sha384-Rma6DA2IPUwhNxmrB/7S3Tno0YY7sFu9WSYMCuulLhIqYSGZ2gKCJWIqhBWqMQfh"
    crossorigin="anonymous"></script>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans", Helvetica, Arial, sans-serif;
      line-height: 1.6;
      max-width: 980px;
      margin: 40px auto;
      padding: 0 24px;
      color: #1f2328;
      background-color: #ffffff;
    }}
    table {{
      border-collapse: collapse;
      width: 100%;
      margin: 16px 0;
      display: block;
      overflow-x: auto;
    }}
    th, td {{
      border: 1px solid #d0d7de;
      padding: 6px 13px;
    }}
    tr:nth-child(2n) {{
      background-color: #f6f8fa;
    }}
    pre {{
      background-color: #f6f8fa;
      padding: 16px;
      border-radius: 6px;
      overflow: auto;
      font-size: 85%;
    }}
    code {{
      font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
      font-size: 85%;
    }}
    math-renderer {{
      display: inline-block;
    }}
    math-renderer.js-display-math {{
      display: block;
      text-align: center;
      margin: 1.2em 0;
    }}
    .katex-error {{
      color: #cf222e;
      background-color: #ffebe9;
      border: 1px solid #ff8182;
      padding: 2px 4px;
      border-radius: 3px;
    }}
    .katex-mathml {{
      display: none !important;
    }}
  </style>
  <script>
    function decodeHTMLEntities(str) {{
      return str
        .replace(/&amp;/g, "&")
        .replace(/&lt;/g, "<")
        .replace(/&gt;/g, ">")
        .replace(/&quot;/g, '"')
        .replace(/&#39;/g, "'")
        .replace(/&apos;/g, "'");
    }}

    document.addEventListener("DOMContentLoaded", function() {{
      if (typeof katex === "undefined") return;
      document.querySelectorAll("math-renderer").forEach(function(el) {{
        var isDisplay = el.classList.contains("js-display-math");
        var text = el.textContent || "";
        if (text.startsWith("$$") && text.endsWith("$$")) {{
          text = text.slice(2, -2);
        }} else if (text.startsWith("$") && text.endsWith("$")) {{
          text = text.slice(1, -1);
        }}
        text = decodeHTMLEntities(text);
        try {{
          katex.render(text, el, {{
            displayMode: isDisplay,
            throwOnError: false,
            output: "html"
          }});
        }} catch (err) {{
          console.error("KaTeX error:", err);
        }}
      }});
    }});
  </script>
</head>
<body>
{body_html}
</body>
</html>
"""


def verify_markdown(
    content: str,
    file_path: str = "",
    token: str | None = None,
) -> tuple[str, list[VerificationIssue]]:
    """Render markdown content via GitHub API and verify the returned HTML."""
    rendered_html = render_gfm(content, token=token)
    validator = GFMHTMLValidator(file_path=file_path)
    validator.feed(rendered_html)
    return rendered_html, validator.issues


def verify_file(
    file_path: Path,
    token: str | None = None,
) -> tuple[str, list[VerificationIssue]]:
    """Read a markdown file, render via GitHub API, and verify the returned HTML."""
    with file_path.open("r", encoding="utf-8", newline="") as f:
        content = f.read()
    return verify_markdown(content, file_path=str(file_path), token=token)


def open_in_browser(html_content: str, title: str = "GFM Math Preview") -> Path:
    """Save HTML preview to a dedicated temporary directory and open in system web browser."""
    full_html = build_preview_html(html_content, title=title)
    temp_dir = Path(tempfile.mkdtemp(prefix="gfm_math_lint_"))
    temp_path = temp_dir / "preview.html"
    temp_path.write_text(full_html, encoding="utf-8")

    webbrowser.open(temp_path.resolve().as_uri())
    return temp_path
