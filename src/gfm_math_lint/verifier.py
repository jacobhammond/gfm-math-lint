"""GFM Rendering Oracle and HTML Verification Engine."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import webbrowser
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


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

STANDARD_MATH_FUNCTIONS: frozenset[str] = frozenset(
    {
        "sin",
        "cos",
        "tan",
        "cot",
        "sec",
        "csc",
        "arcsin",
        "arccos",
        "arctan",
        "arccot",
        "arcsec",
        "arccsc",
        "sinh",
        "cosh",
        "tanh",
        "coth",
        "sech",
        "csch",
        "arsinh",
        "arcosh",
        "artanh",
        "log",
        "ln",
        "lg",
        "exp",
        "det",
        "dim",
        "ker",
        "hom",
        "gcd",
        "deg",
        "arg",
        "min",
        "max",
        "inf",
        "sup",
        "lim",
        "liminf",
        "limsup",
        "Pr",
        "prob",
        "probability",
    }
)

GENUINE_MATH_TAGS: frozenset[str] = frozenset(
    {
        "msub",
        "msup",
        "msubsup",
        "mfrac",
        "munder",
        "mover",
        "munderover",
        "msqrt",
        "mroot",
        "mtable",
    }
)

GENUINE_MATH_OPERATORS: frozenset[str] = frozenset(
    {
        "∫",
        "∬",
        "∭",
        "∮",
        "∑",
        "∏",
        "∐",
        "∂",
        "∇",
        "√",
    }
)

_GENUINE_MATH_LATEX_RE = re.compile(
    r"(\\(?:int|iint|iiint|oint|sum|prod|coprod|frac|cfrac|dfrac|tfrac|sqrt|partial|nabla)\b|\^)"
)

BLOCK_CONTAINERS: frozenset[str] = frozenset(
    {
        "p",
        "li",
        "td",
        "th",
        "blockquote",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "div",
        "section",
        "article",
        "aside",
        "caption",
    }
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

        # Buffered container traversal across inline tag boundaries
        self.container_stack: list[dict[str, Any]] = []
        self.root_buffer: list[str] = []

        # MathML / pseudo-code stacking detection state
        self.math_tags_seen: set[str] = set()
        self.math_tokens: list[tuple[str, str]] = []
        self.math_text_chunks: list[str] = []
        self.current_math_tag: str = ""
        self.current_math_tag_text: list[str] = []

    @property
    def in_code_block(self) -> bool:
        return self.pre_depth > 0 or self.code_depth > 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        tag_lower = tag.lower()

        if tag_lower == "math-renderer":
            self.in_math_renderer = True
            self.math_renderer_depth += 1
            if self.math_renderer_depth == 1:
                self.math_tags_seen = set()
                self.math_tokens = []
                self.math_text_chunks = []
                self.current_math_tag = ""
                self.current_math_tag_text = []

        elif self.in_math_renderer:
            self.math_tags_seen.add(tag_lower)
            self.current_math_tag = tag_lower
            self.current_math_tag_text = []

            # Detect HTML tag pollution inside math-renderer (e.g. <em>, <strong>, <a>, <br>)
            if tag_lower in ("em", "strong", "a", "br", "i", "b"):
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

        if tag_lower == "pre":
            self.pre_depth += 1
            if self.container_stack:
                self.container_stack[-1]["buffer"].append(" ")
        elif tag_lower == "code":
            self.code_depth += 1
            if self.container_stack:
                self.container_stack[-1]["buffer"].append(" ")

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

        if tag_lower == "table":
            self.in_table = True
            self.current_table_rows = []

        elif tag_lower == "tr" and self.in_table:
            self.current_row_cols = 0

        elif tag_lower in ("td", "th") and self.in_table:
            self.current_row_cols += 1

        # Container buffering across inline tags
        if tag_lower in BLOCK_CONTAINERS and not self.in_math_renderer:
            if not self.container_stack and self.root_buffer:
                self._check_buffered_text("".join(self.root_buffer))
                self.root_buffer = []
            self.container_stack.append({"tag": tag_lower, "buffer": []})

    def handle_endtag(self, tag: str) -> None:
        tag_lower = tag.lower()

        if tag_lower == "math-renderer":
            self.math_renderer_depth = max(0, self.math_renderer_depth - 1)
            if self.math_renderer_depth == 0:
                self.in_math_renderer = False
                self._check_math_renderer_pseudo_code()

        elif self.in_math_renderer:
            if tag_lower in ("mi", "mo", "mn", "mtext", "annotation"):
                txt = "".join(self.current_math_tag_text).strip()
                if txt:
                    self.math_tokens.append((tag_lower, txt))
                self.current_math_tag = ""
                self.current_math_tag_text = []

        if tag_lower == "pre":
            self.pre_depth = max(0, self.pre_depth - 1)
            if self.container_stack:
                self.container_stack[-1]["buffer"].append(" ")
        elif tag_lower == "code":
            self.code_depth = max(0, self.code_depth - 1)
            if self.container_stack:
                self.container_stack[-1]["buffer"].append(" ")

        elif tag_lower == "tr" and self.in_table:
            self.current_table_rows.append(self.current_row_cols)

        elif tag_lower == "table":
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

        # Check block container closure
        if self.container_stack and self.container_stack[-1]["tag"] == tag_lower:
            entry = self.container_stack.pop()
            self._check_buffered_text("".join(entry["buffer"]))

    def handle_data(self, data: str) -> None:
        if self.in_math_renderer:
            self.math_text_chunks.append(data)
            if self.current_math_tag:
                self.current_math_tag_text.append(data)
            return

        if self.in_code_block:
            return

        if self.container_stack:
            self.container_stack[-1]["buffer"].append(data)
        else:
            self.root_buffer.append(data)

    def feed(self, data: str) -> None:
        super().feed(data)
        if not self.container_stack and self.root_buffer:
            self._check_buffered_text("".join(self.root_buffer))
            self.root_buffer = []

    def close(self) -> None:
        while self.container_stack:
            entry = self.container_stack.pop()
            self._check_buffered_text("".join(entry["buffer"]))
        if self.root_buffer:
            self._check_buffered_text("".join(self.root_buffer))
            self.root_buffer = []
        super().close()

    def _check_buffered_text(self, text: str) -> None:
        if "$" not in text and "\\" not in text:
            return
        for match in _MATH_SYNTAX_RE.finditer(text):
            snippet = match.group(0).strip()
            start = max(0, match.start() - 20)
            end = min(len(text), match.end() + 20)
            context_snippet = text[start:end].replace("\n", " ").strip()
            self.issues.append(
                VerificationIssue(
                    category="unrendered-math",
                    message=(f"Unrendered math expression detected in plain text outside <math-renderer>: '{snippet}'"),
                    snippet=f"...{context_snippet}...",
                    file_path=self.file_path,
                )
            )

    def _check_math_renderer_pseudo_code(self) -> None:
        raw_text = "".join(self.math_text_chunks).strip()
        snippet = raw_text if raw_text else "<math-renderer>"

        # 1. Check for genuine mathematical constructs
        if any(t in GENUINE_MATH_TAGS for t in self.math_tags_seen):
            return

        for tag, txt in self.math_tokens:
            if tag == "mo" and txt in GENUINE_MATH_OPERATORS:
                return

        if _GENUINE_MATH_LATEX_RE.search(raw_text):
            return

        # 2. Check MathML tokens for pseudo-code / function composition
        has_pseudo_code = False

        if self.math_tokens:
            collapsed: list[tuple[str, str, bool]] = []
            i = 0
            while i < len(self.math_tokens):
                t_tag, t_txt = self.math_tokens[i]
                if t_tag == "mi":
                    mi_parts = [t_txt]
                    j = i + 1
                    while j < len(self.math_tokens) and self.math_tokens[j][0] == "mi":
                        mi_parts.append(self.math_tokens[j][1])
                        j += 1
                    combined = "".join(mi_parts)
                    was_consec = j - i > 1
                    collapsed.append(("mi", combined, was_consec))
                    i = j
                else:
                    if t_txt != "\u2061":
                        collapsed.append((t_tag, t_txt, False))
                    i += 1

            # Detect function calls
            func_calls: list[tuple[str, bool]] = []
            for k in range(len(collapsed) - 1):
                if collapsed[k][0] == "mi" and collapsed[k + 1][0] == "mo" and collapsed[k + 1][1] in ("(", "["):
                    func_calls.append((collapsed[k][1], collapsed[k][2]))

            if len(func_calls) >= 2:
                for name, was_consec in func_calls:
                    name_clean = name.strip()
                    if name_clean.lower() not in STANDARD_MATH_FUNCTIONS and (
                        len(name_clean) >= 2 or was_consec or "_" in name_clean
                    ):
                        has_pseudo_code = True
                        break

        # 3. If no MathML tokens or not detected via tokens, check raw formula text
        if not has_pseudo_code and raw_text:
            formula = raw_text.strip("$").strip()
            formula_clean = re.sub(r"\\text\{([^{}]+)\}", r"\1", formula)
            matches = list(re.finditer(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\(", formula_clean))
            if len(matches) >= 2:
                for m in matches:
                    name = m.group(1).strip()
                    if name.lower() not in STANDARD_MATH_FUNCTIONS and (len(name) >= 2 or "_" in name):
                        has_pseudo_code = True
                        break

        if has_pseudo_code:
            self.issues.append(
                VerificationIssue(
                    category="pseudo-code-stacking",
                    message=(
                        "Formula contains code function composition in math delimiters; "
                        "causes vertical MathML stacking in environments without KaTeX CSS."
                    ),
                    snippet=snippet,
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
    stdout: bool = False,
) -> tuple[str, list[VerificationIssue]]:
    """Render markdown content via GitHub API and verify the returned HTML."""
    rendered_html = render_gfm(content, token=token)
    if stdout:
        sys.stdout.write(rendered_html)
        if not rendered_html.endswith("\n"):
            sys.stdout.write("\n")
    validator = GFMHTMLValidator(file_path=file_path)
    validator.feed(rendered_html)
    validator.close()
    return rendered_html, validator.issues


def verify_file(
    file_path: Path,
    token: str | None = None,
    stdout: bool = False,
) -> tuple[str, list[VerificationIssue]]:
    """Read a markdown file, render via GitHub API, and verify the returned HTML."""
    with file_path.open("r", encoding="utf-8", newline="") as f:
        content = f.read()
    return verify_markdown(content, file_path=str(file_path), token=token, stdout=stdout)


def open_in_browser(html_content: str, title: str = "GFM Math Preview") -> Path:
    """Save HTML preview to a dedicated temporary directory and open in system web browser."""
    full_html = build_preview_html(html_content, title=title)
    temp_dir = Path(tempfile.mkdtemp(prefix="gfm_math_lint_"))
    temp_path = temp_dir / "preview.html"
    temp_path.write_text(full_html, encoding="utf-8")

    webbrowser.open(temp_path.resolve().as_uri())
    return temp_path
