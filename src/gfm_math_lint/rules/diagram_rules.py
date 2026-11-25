"""GFM Mermaid diagram and fence symmetry rules (GFM-D01 through GFM-D06)."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

from gfm_math_lint.fixer import LintEdit
from gfm_math_lint.rules.base import Rule, Violation
from gfm_math_lint.tokenizer import DocumentZone, Zone, is_escaped, scan_document_zones

if TYPE_CHECKING:
    from collections.abc import Sequence

MERMAID_SUBGRAPH_ARROW_RE = re.compile(r"^subgraph\s+.*?(?:--!?>|---|==>|-\.->)")
MERMAID_LINK_RE = re.compile(
    r"(?:\s+--\s+[^-]+?\s+--!?>|\s+-\.\s+[^\.]+?\s+\.->|\s+==\s+[^=]+?\s+==>|--!?>\|[^|]+\||--!?>|---|==>|-\.->)"
)

CODE_TAG_RE = re.compile(r"<code>.*?</code>", re.IGNORECASE)
LITERAL_NEWLINE_RE = re.compile(r"\\+n")
LATEX_N_CMD_RE = re.compile(
    r"^\\(?:nu|neq|nabla|neg|notin|nmid|newline|ni|natural|nless|ngtr|nleq|ngeq|"
    r"nsubset|nsupset|napprox|nsim|ncong|nparallel|nshortmid|nvdash|nvDash|nVDash|"
    r"nleftarrow|nrightarrow|nleftrightarrow|nLeftarrow|nRightarrow|nLeftrightarrow)\b"
)

MERMAID_PIPE_EDGE_INTERNAL_PIPE_RE = re.compile(r'(?:--!?>|---|==>|-\.->)\|"[^"\n]*\|[^"\n]*"\|')
MERMAID_SPECIAL_LABEL_CHARS_RE = re.compile(r"[(){}|]")

MERMAID_LATEX_MACRO_RE = re.compile(
    r"\\(?:Delta|alpha|beta|gamma|omega|mu|pi|sigma|theta|lambda|frac|sqrt|text|mathrm)\b"
)


def _strip_blockquote_prefix(line: str) -> str:
    """Strip leading whitespace and blockquote '>' markers from a line."""
    return re.sub(r"^\s*(?:>\s*)*", "", line)


def _iter_mermaid_inner_lines(zones: list[DocumentZone]) -> list[tuple[int, str]]:
    """Collect (1-indexed line_no, raw_line) pairs for inner lines of Mermaid code blocks."""
    result: list[tuple[int, str]] = []
    for zone in zones:
        if zone.zone_type != Zone.FENCED_CODE or zone.info.strip().lower() != "mermaid":
            continue
        inner_lines = zone.lines[1:-1] if zone.is_closed and len(zone.lines) >= 2 else zone.lines[1:]
        for rel_idx, line in enumerate(inner_lines):
            if _strip_blockquote_prefix(line).startswith("%%"):
                continue
            result.append((zone.start_line + 1 + rel_idx, line))
    return result


def _find_mermaid_label_spans(line: str) -> list[tuple[int, int, str]]:
    """Return (inner_start, inner_end, kind) spans for [...], (...), {...}, and "..." labels on a line."""
    spans: list[tuple[int, int, str]] = []
    n = len(line)
    i = 0
    matching_close = {"[": "]", "(": ")", "{": "}"}

    while i < n:
        ch = line[i]
        if ch == '"':
            start = i + 1
            j = start
            while j < n:
                if line[j] == "\\" and j + 1 < n:
                    j += 2
                    continue
                if line[j] == '"':
                    spans.append((start, j, '"'))
                    i = j + 1
                    break
                j += 1
            else:
                i += 1
            continue

        if ch in matching_close:
            open_ch = ch
            close_ch = matching_close[open_ch]
            start = i + 1
            depth = 1
            in_quotes = False
            j = start
            while j < n and depth > 0:
                c = line[j]
                if in_quotes:
                    if c == "\\" and j + 1 < n:
                        j += 2
                        continue
                    if c == '"':
                        in_quotes = False
                else:
                    if c == '"':
                        in_quotes = True
                    elif c == open_ch:
                        depth += 1
                    elif c == close_ch:
                        depth -= 1
                        if depth == 0:
                            spans.append((start, j, open_ch))
                            i = j + 1
                            break
                j += 1
            else:
                i += 1
            continue

        i += 1

    return spans


def _has_wrapping_delims(text: str, open_ch: str, close_ch: str) -> bool:
    """Return True if text starts with open_ch and ends with its matching close_ch."""
    if len(text) < 2 or text[0] != open_ch or text[-1] != close_ch:
        return False
    depth = 0
    for idx, ch in enumerate(text):
        if ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return idx == len(text) - 1
    return False


def _is_double_quoted(text: str) -> bool:
    """Return True if text (stripped) is a single double-quoted string."""
    s = text.strip()
    if len(s) < 2 or s[0] != '"' or s[-1] != '"':
        return False
    i = 1
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s):
            i += 2
            continue
        if s[i] == '"':
            return i == len(s) - 1
        i += 1
    return False


def _find_mermaid_math_spans(line: str) -> list[tuple[int, int]]:
    """Find $...$ and $$...$$ math spans in a Mermaid line while ignoring currency values."""
    spans: list[tuple[int, int]] = []
    n = len(line)
    i = 0
    while i < n:
        if line[i] == "$" and not is_escaped(line, i):
            is_double = i + 1 < n and line[i + 1] == "$"
            delim_len = 2 if is_double else 1
            j = i + delim_len
            close_idx = -1
            while j < n:
                if line[j] == "\\" and j + 1 < n:
                    j += 2
                    continue
                if line[j] == '"' or line.startswith(("-->", "--!>", "---", "==>", "-.->"), j):
                    break
                if is_double:
                    if line.startswith("$$", j):
                        close_idx = j
                        break
                elif line[j] == "$":
                    if (j + 1 < n and line[j + 1] == "$") or (j > 0 and line[j - 1] == "$"):
                        j += 1
                        continue
                    close_idx = j
                    break
                j += 1

            if close_idx != -1:
                candidate = line[i + delim_len : close_idx]
                is_currency_pair = bool(candidate and candidate[0].isdigit() and candidate.endswith(" "))
                if candidate and not is_currency_pair:
                    spans.append((i, close_idx + delim_len))
                    i = close_idx + delim_len
                    continue
        i += 1
    return spans


class RuleD01(Rule):
    """GFM-D01: Explicit Subgraph & Node Label Identifier Enforcement."""

    id: str = "GFM-D01"
    name: str = "mermaid-identifier"
    description: str = "Enforce alphanumeric IDs for Mermaid subgraphs and multi-word node labels"
    severity: str = "warning"

    def check(self, lines: Sequence[str], zones: list[DocumentZone], file_path: str = "") -> list[Violation]:
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

    def check(self, lines: Sequence[str], zones: list[DocumentZone], file_path: str = "") -> list[Violation]:
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


class RuleD03(Rule):
    """GFM-D03: Literal Newline Escape Sequence in Mermaid Labels."""

    id: str = "GFM-D03"
    name: str = "mermaid-newline-linebreak"
    description: str = "Replace literal \\n escape sequences in Mermaid labels with <br> line breaks"
    severity: str = "error"

    def check(self, lines: Sequence[str], zones: list[DocumentZone], file_path: str = "") -> list[Violation]:
        violations: list[Violation] = []

        for line_no, line in _iter_mermaid_inner_lines(zones):
            code_spans = [(m.start(), m.end()) for m in CODE_TAG_RE.finditer(line)]
            math_spans = _find_mermaid_math_spans(line)
            label_spans = _find_mermaid_label_spans(line)
            seen_offsets: set[int] = set()

            for start, end, kind in label_spans:
                inner = line[start:end]
                for m in LITERAL_NEWLINE_RE.finditer(line, start, end):
                    pos = m.start()
                    if pos in seen_offsets:
                        continue
                    # Preserve trapezoid/parallelogram opening '[\' when label begins with 'n' (e.g. A[\name\])
                    if kind == "[" and pos == start and inner.endswith(("\\", "/")):
                        continue
                    if any(cs <= pos < ce for cs, ce in code_spans):
                        continue
                    if any(ms <= pos < me for ms, me in math_spans) and LATEX_N_CMD_RE.match(line[pos:]):
                        continue

                    seen_offsets.add(pos)
                    col_start = pos + 1
                    col_end = m.end() + 1
                    edit = LintEdit(
                        rule_id=self.id,
                        start_line=line_no,
                        start_col=col_start,
                        end_line=line_no,
                        end_col=col_end,
                        replacement="<br>",
                    )
                    violations.append(
                        Violation(
                            rule_id=self.id,
                            message=(
                                f"Literal '{m.group(0)}' sequence in Mermaid label renders as raw text in GFM. "
                                "Use '<br>' for line breaks."
                            ),
                            line=line_no,
                            col=col_start,
                            severity=self.severity,
                            edit=edit,
                        )
                    )

        return violations


class RuleD04(Rule):
    """GFM-D04: Unescaped Special Characters in Mermaid Labels and Pipe Edge Labels."""

    id: str = "GFM-D04"
    name: str = "mermaid-label-special-chars"
    description: str = "Disallow unquoted special characters in Mermaid node labels and internal pipes in edge labels"
    severity: str = "error"

    def check(self, lines: Sequence[str], zones: list[DocumentZone], file_path: str = "") -> list[Violation]:
        violations: list[Violation] = []

        for line_no, line in _iter_mermaid_inner_lines(zones):
            # Check 1 (REG-18): Pipe-delimited edge labels containing an internal pipe
            for m in MERMAID_PIPE_EDGE_INTERNAL_PIPE_RE.finditer(line):
                col_start = m.start() + 1
                violations.append(
                    Violation(
                        rule_id=self.id,
                        message=(
                            "Mermaid pipe-delimited edge label contains an internal '|' that breaks parsing. "
                            "Use '-- \"...\" -->' syntax or remove the internal pipe."
                        ),
                        line=line_no,
                        col=col_start,
                        severity=self.severity,
                        edit=None,
                    )
                )

            # Check 2: Unquoted [...] node/subgraph labels containing (, ), {, }, or |
            for start, end, kind in _find_mermaid_label_spans(line):
                if kind != "[":
                    continue

                prefix = _strip_blockquote_prefix(line[: start - 1]).rstrip()
                if not prefix or not (prefix[-1].isalnum() or prefix[-1] in "_-"):
                    continue

                inner = line[start:end]
                if _has_wrapping_delims(inner, "(", ")") or _has_wrapping_delims(inner, "[", "]"):
                    start += 1
                    end -= 1
                    inner = line[start:end]

                if _is_double_quoted(inner):
                    continue
                if not MERMAID_SPECIAL_LABEL_CHARS_RE.search(inner):
                    continue

                stripped_inner = inner.strip()
                escaped_inner = stripped_inner.replace('"', "#quot;")
                edit = LintEdit(
                    rule_id=self.id,
                    start_line=line_no,
                    start_col=start + 1,
                    end_line=line_no,
                    end_col=end + 1,
                    replacement=f'"{escaped_inner}"',
                )
                violations.append(
                    Violation(
                        rule_id=self.id,
                        message=(
                            "Unquoted Mermaid node label contains special characters ('(', ')', '{', '}', '|'). "
                            f"Wrap the label in double quotes: '\"{escaped_inner}\"'."
                        ),
                        line=line_no,
                        col=start,
                        severity=self.severity,
                        edit=edit,
                    )
                )

        return violations


class RuleD05(Rule):
    """GFM-D05: LaTeX/KaTeX Math Inside Mermaid Diagrams."""

    id: str = "GFM-D05"
    name: str = "math-in-mermaid"
    description: str = "Warn against LaTeX/KaTeX math inside Mermaid diagrams"
    severity: str = "warning"

    def check(self, lines: Sequence[str], zones: list[DocumentZone], file_path: str = "") -> list[Violation]:
        violations: list[Violation] = []

        for line_no, line in _iter_mermaid_inner_lines(zones):
            math_spans = _find_mermaid_math_spans(line)
            for ms, _me in math_spans:
                violations.append(
                    Violation(
                        rule_id=self.id,
                        message=(
                            "Mermaid diagrams do not render LaTeX/KaTeX '$...$' math. "
                            "Use Unicode characters (e.g., Δ, α, β, μ) instead."
                        ),
                        line=line_no,
                        col=ms + 1,
                        severity=self.severity,
                        edit=None,
                    )
                )

            for m in MERMAID_LATEX_MACRO_RE.finditer(line):
                pos = m.start()
                if any(ms <= pos < me for ms, me in math_spans):
                    continue
                violations.append(
                    Violation(
                        rule_id=self.id,
                        message=(
                            f"Mermaid diagram contains LaTeX macro '{m.group(0)}' which will render literally. "
                            "Use Unicode characters (e.g., Δ, α, β, μ) instead."
                        ),
                        line=line_no,
                        col=pos + 1,
                        severity=self.severity,
                        edit=None,
                    )
                )

        return violations


_BROWSER_ENV_ERROR_MARKERS: tuple[str, ...] = (
    "could not find chrome",
    "failed to launch the browser",
    "no usable sandbox",
    "error while loading shared libraries",
    "cannot open shared object file",
    "browser was not found",
)


def find_mmdc_binary() -> str | None:
    """Return the path to `mmdc` (@mermaid-js/mermaid-cli) on PATH, or None."""
    return shutil.which("mmdc")


def find_headless_chrome_binary() -> str | None:
    """Locate an existing headless Chrome/Chromium executable without downloading one."""
    for env_var in ("BROWSER_PATH", "CHROME_PATH", "PUPPETEER_EXECUTABLE_PATH"):
        val = os.environ.get(env_var, "").strip()
        if val and Path(val).is_file():
            return val
    for candidate in ("chrome-headless-shell", "chromium", "chromium-browser", "google-chrome"):
        found = shutil.which(candidate)
        if found:
            return found
    return None


def build_puppeteer_config(executable_path: str | None = None) -> dict[str, Any]:
    """Build a desktop-quiet Puppeteer config using headless shell mode."""
    cfg: dict[str, Any] = {
        "headless": "shell",
        "args": ["--no-sandbox", "--disable-setuid-sandbox", "--disable-gpu"],
    }
    exe = executable_path if executable_path is not None else find_headless_chrome_binary()
    if exe:
        cfg["executablePath"] = exe
    return cfg


def _get_mmdc_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PUPPETEER_SKIP_DOWNLOAD"] = "1"
    env["PUPPETEER_SKIP_CHROMIUM_DOWNLOAD"] = "1"
    return env


def _extract_mermaid_blocks(zones: list[DocumentZone]) -> list[tuple[int, str]]:
    """Return `(start_line, diagram_source)` for closed Mermaid fenced code blocks."""
    blocks: list[tuple[int, str]] = []
    for zone in zones:
        if zone.zone_type != Zone.FENCED_CODE or zone.info.strip().lower() != "mermaid" or not zone.is_closed:
            continue
        inner_lines = zone.lines[1:-1] if len(zone.lines) >= 2 else []
        cleaned = [
            _strip_blockquote_prefix(ln) if (zone.parent_block == "blockquote" or ln.lstrip().startswith(">")) else ln
            for ln in inner_lines
        ]
        src = "".join(cleaned).strip()
        if src:
            blocks.append((zone.start_line, src))
    return blocks


def _is_browser_env_error(output: str) -> bool:
    low = output.lower()
    return any(marker in low for marker in _BROWSER_ENV_ERROR_MARKERS)


class RuleD06(Rule):
    """GFM-D06: Opportunistic Mermaid Syntax Validation via `mmdc`."""

    id: str = "GFM-D06"
    name: str = "mermaid-parse"
    description: str = "Opportunistically validate Mermaid diagram syntax using mmdc when installed"
    severity: str = "error"

    def check(self, lines: Sequence[str], zones: list[DocumentZone], file_path: str = "") -> list[Violation]:
        blocks = _extract_mermaid_blocks(zones)
        if not blocks:
            return []

        mmdc_bin = find_mmdc_binary()
        if not mmdc_bin:
            return []

        violations: list[Violation] = []
        cfg = build_puppeteer_config()
        env = _get_mmdc_env()

        with tempfile.TemporaryDirectory(prefix="gfm_mermaid_") as tmp_dir:
            tmp_path = Path(tmp_dir)
            cfg_path = tmp_path / "puppeteer-config.json"
            cfg_path.write_text(json.dumps(cfg), encoding="utf-8")

            for idx, (start_line, src) in enumerate(blocks):
                in_mmd = tmp_path / f"diagram_{idx}.mmd"
                out_svg = tmp_path / f"diagram_{idx}.svg"
                in_mmd.write_text(src + "\n", encoding="utf-8")

                try:
                    proc = subprocess.run(
                        [mmdc_bin, "-i", str(in_mmd), "-o", str(out_svg), "-p", str(cfg_path)],
                        capture_output=True,
                        shell=False,
                        check=False,
                        timeout=30,
                        env=env,
                    )
                except (subprocess.SubprocessError, OSError):
                    return violations

                if proc.returncode != 0:
                    combined = (
                        proc.stderr.decode("utf-8", errors="replace")
                        + "\n"
                        + proc.stdout.decode("utf-8", errors="replace")
                    ).strip()
                    if _is_browser_env_error(combined):
                        continue
                    first_line = next((ln.strip() for ln in combined.splitlines() if ln.strip()), "Syntax error")
                    violations.append(
                        Violation(
                            rule_id=self.id,
                            message=f"Mermaid syntax error (mmdc): {first_line[:200]}",
                            line=start_line,
                            col=1,
                            severity=self.severity,
                            edit=None,
                        )
                    )

        return violations


def render_mermaid_previews(markdown_content: str, output_dir: Path, stem: str = "diagram") -> list[Path]:
    """Render all Mermaid blocks in `markdown_content` to high-DPI PNGs in `output_dir`."""
    lines = markdown_content.splitlines(keepends=True)
    if not lines:
        return []
    zones = scan_document_zones(lines)
    blocks = _extract_mermaid_blocks(zones)
    if not blocks:
        return []

    mmdc_bin = find_mmdc_binary()
    if not mmdc_bin:
        raise RuntimeError("Mermaid preview rendering requires 'mmdc' (@mermaid-js/mermaid-cli) on PATH.")

    output_dir.mkdir(parents=True, exist_ok=True)
    cfg = build_puppeteer_config()
    env = _get_mmdc_env()
    written: list[Path] = []

    with tempfile.TemporaryDirectory(prefix="gfm_mermaid_preview_") as tmp_dir:
        tmp_path = Path(tmp_dir)
        cfg_path = tmp_path / "puppeteer-config.json"
        cfg_path.write_text(json.dumps(cfg), encoding="utf-8")

        for idx, (_start_line, src) in enumerate(blocks, start=1):
            in_mmd = tmp_path / f"diagram_{idx:02d}.mmd"
            out_png = output_dir / f"{stem}_mermaid_{idx:02d}.png"
            in_mmd.write_text(src + "\n", encoding="utf-8")

            try:
                proc = subprocess.run(
                    [
                        mmdc_bin,
                        "-i",
                        str(in_mmd),
                        "-o",
                        str(out_png),
                        "-s",
                        "2",
                        "-b",
                        "white",
                        "-p",
                        str(cfg_path),
                    ],
                    capture_output=True,
                    shell=False,
                    check=False,
                    timeout=30,
                    env=env,
                )
            except (subprocess.SubprocessError, OSError) as e:
                raise RuntimeError(f"Failed to invoke mmdc for Mermaid preview: {e}") from e

            if proc.returncode != 0:
                err_txt = proc.stderr.decode("utf-8", errors="replace").strip()
                raise RuntimeError(f"mmdc failed rendering Mermaid diagram #{idx}: {err_txt or 'unknown error'}")
            written.append(out_png)

    return written
