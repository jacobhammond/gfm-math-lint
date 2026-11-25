"""Zero-dependency emulator of GitHub CommonMark math escape, flanking, and block rules."""

from __future__ import annotations

import difflib
import html
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from gfm_math_lint.tokenizer import InlineSpan, Zone, scan_document_zones, scan_inline_spans

if TYPE_CHECKING:
    from collections.abc import Callable

ASCII_PUNCT: str = re.escape(r"""!"#$%&'()*+,-./:;<=>?@[\]^_`{|}~""")
COMMONMARK_UNESCAPE_RE: re.Pattern[str] = re.compile(r"\\([" + ASCII_PUNCT + r"])")
BLOCK_INTERRUPT_RE: re.Pattern[str] = re.compile(r"^\s{0,3}(?:[-+*]\s+|>\s*|#{1,6}(?:\s|$)|\d+[.)]\s+|=+\s*$|-+\s*$)")
_UNESCAPED_UNDERSCORE_RE: re.Pattern[str] = re.compile(r"(?<!\\)_")
_BQ_PREFIX_RE: re.Pattern[str] = re.compile(r"^\s*(?:>\s*)+")
_TEXT_MACRO_RE: re.Pattern[str] = re.compile(r"\\(?:text|mathrm|textrm|textit|textbf|texttt|textsf)\s*\{")
_TABLE_DELIM_ROW_RE: re.Pattern[str] = re.compile(r"^\|?\s*:?-+[-:| ]*\|?$")


@dataclass(frozen=True)
class MathSpan:
    """A mathematical span extracted from Markdown source or rendered HTML."""

    content: str
    display: bool
    delimiter: str
    line: int
    col: int = 1


@dataclass(frozen=True)
class SpanDiff:
    """A discrepancy between an intended math span and the rendered/emulated span."""

    category: str
    message: str
    intended: str = ""
    received: str = ""
    line: int = 0
    display: bool = False


@dataclass
class EmulationResult:
    """Result of local zero-dependency GFM document emulation."""

    intended_spans: list[MathSpan] = field(default_factory=list)
    received_spans: list[MathSpan] = field(default_factory=list)
    rendered_html: str = ""
    diffs: list[SpanDiff] = field(default_factory=list)


def emulate_github_math_escapes(tex: str, display: bool) -> str:
    """Model the exact LaTeX string GitHub hands to MathJax after CommonMark inline unescaping.

    - In inline math ($...$), all \\ + ASCII punctuation sequences are unescaped to the bare character.
    - In display math ($$...$$), all \\ + ASCII punctuation sequences are unescaped EXCEPT
      a trailing \\\\ at the end of a line.
    """
    if not display:
        return COMMONMARK_UNESCAPE_RE.sub(r"\1", tex)

    out_lines: list[str] = []
    for line in tex.split("\n"):
        body = line.rstrip()
        keep_eol_break = body.endswith("\\\\")
        core = body[:-2] if keep_eol_break else body
        unescaped = COMMONMARK_UNESCAPE_RE.sub(r"\1", core)
        out_lines.append(unescaped + ("\\\\" if keep_eol_break else ""))
    return "\n".join(out_lines)


def is_flanking_underscore(text: str, pos: int) -> bool:
    """Determine if an underscore at `pos` in `text` can participate in CommonMark §6.2 emphasis.

    Intra-word underscores ([a-zA-Z0-9]_[a-zA-Z0-9]) and space-padded underscores (` _ `)
    are neither left- nor right-flanking and cannot open or close emphasis in CommonMark.
    """
    if pos < 0 or pos >= len(text) or text[pos] != "_":
        return False
    prev_ch = text[pos - 1] if pos > 0 else " "
    next_ch = text[pos + 1] if pos + 1 < len(text) else " "
    if prev_ch.isalnum() and next_ch.isalnum():
        return False
    return not (prev_ch.isspace() and next_ch.isspace())


def find_colliding_math_underscores(
    spans: list[InlineSpan],
    macro_ranges_fn: Callable[[str], list[tuple[int, int]]] | None = None,
) -> list[tuple[InlineSpan, int]]:
    """Identify unescaped underscores in dollar math spans that risk CommonMark emphasis collision.

    Ignores underscores inside inline code spans, HTML comments, backtick math ($`...`$),
    and text-mode LaTeX macros (handled separately by GFM-M03/GFM-M14).
    """
    candidates: list[tuple[InlineSpan, int, bool]] = []
    prose_underscore_count = 0
    has_any_flanking = False

    for span in spans:
        if span.zone_type in (Zone.INLINE_CODE, Zone.COMMENT):
            continue

        if span.zone_type == Zone.PROSE:
            for m in _UNESCAPED_UNDERSCORE_RE.finditer(span.content):
                prose_underscore_count += 1
                if is_flanking_underscore(span.content, m.start()):
                    has_any_flanking = True
            continue

        if span.zone_type in (Zone.INLINE_MATH, Zone.DISPLAY_MATH) and span.delimiter in ("$", "$$"):
            macro_ranges = macro_ranges_fn(span.content) if macro_ranges_fn is not None else []
            for m in _UNESCAPED_UNDERSCORE_RE.finditer(span.content):
                u_pos = m.start()
                if any(start <= u_pos < end for start, end in macro_ranges):
                    continue
                flanking = is_flanking_underscore(span.content, u_pos)
                if flanking:
                    has_any_flanking = True
                candidates.append((span, u_pos, flanking))

    if len(candidates) + prose_underscore_count < 2:
        return []

    if not has_any_flanking:
        return []

    return [(span, u_pos) for span, u_pos, _ in candidates]


def has_block_interrupt(inner_lines: list[str]) -> bool:
    """Return True if any line inside display math triggers a CommonMark block interruption."""
    return any(BLOCK_INTERRUPT_RE.match(line) for line in inner_lines)


def _find_text_macro_ranges(text: str) -> list[tuple[int, int]]:
    """Find (start, end) ranges of text-mode LaTeX macro arguments in `text`."""
    ranges: list[tuple[int, int]] = []
    n = len(text)
    for m in _TEXT_MACRO_RE.finditer(text):
        brace_start = m.end() - 1
        depth = 1
        j = brace_start + 1
        while j < n and depth > 0:
            if text[j] == "\\":
                j += 2
                continue
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
            j += 1
        if depth == 0:
            ranges.append((m.start(), j))
    return ranges


def _is_valid_display_pad(line: str, is_blockquote: bool) -> bool:
    """Check whether a boundary line provides valid blank-line padding for display math."""
    if is_blockquote:
        return _BQ_PREFIX_RE.sub("", line).strip() == ""
    return line.strip() == ""


def _strip_display_math_zone(lines: list[str], parent_block: str | None) -> list[str]:
    """Extract inner lines from a multi-line $$...$$ zone, stripping blockquote prefixes."""
    inner = lines[1:-1] if len(lines) >= 2 else lines[1:]
    is_bq = parent_block == "blockquote"
    return [_BQ_PREFIX_RE.sub("", ln) if (is_bq or ln.lstrip().startswith(">")) else ln for ln in inner]


def extract_intended_math_spans(markdown_content: str) -> list[MathSpan]:
    """Extract all math spans the author intended in `markdown_content`."""
    lines = markdown_content.splitlines(keepends=True)
    if not lines:
        return []

    zones = scan_document_zones(lines)
    spans_out: list[MathSpan] = []

    for zone in zones:
        if zone.zone_type == Zone.DISPLAY_MATH:
            if zone.is_closed and len(zone.lines) >= 2:
                stripped_inner = _strip_display_math_zone(zone.lines, zone.parent_block)
                display_content = "".join(stripped_inner).strip()
            else:
                inner_lines: list[str] = []
                for idx, line in enumerate(zone.lines):
                    line_content = _BQ_PREFIX_RE.sub("", line).rstrip("\r\n")
                    if idx == 0 and line_content.lstrip().startswith("$$"):
                        line_content = line_content.lstrip()[2:]
                    if (idx == len(zone.lines) - 1 or len(zone.lines) == 1) and line_content.rstrip().endswith("$$"):
                        line_content = line_content.rstrip()[:-2]
                    if line_content.strip():
                        inner_lines.append(line_content)
                display_content = "\n".join(inner_lines).strip()
            if display_content:
                spans_out.append(
                    MathSpan(
                        content=display_content,
                        display=True,
                        delimiter="$$",
                        line=zone.start_line,
                        col=1,
                    )
                )

        elif zone.zone_type == Zone.FENCED_CODE and zone.info.strip().lower() == "math":
            content_lines = zone.lines[1:-1] if zone.is_closed and len(zone.lines) >= 2 else zone.lines[1:]
            cleaned_lines = [
                _BQ_PREFIX_RE.sub("", ln) if (zone.parent_block == "blockquote" or ln.lstrip().startswith(">")) else ln
                for ln in content_lines
            ]
            math_text = "".join(cleaned_lines).strip()
            if math_text:
                spans_out.append(
                    MathSpan(
                        content=math_text,
                        display=True,
                        delimiter="```math",
                        line=zone.start_line,
                        col=1,
                    )
                )

        elif zone.zone_type in (Zone.PROSE, Zone.TABLE):
            for rel_idx, line in enumerate(zone.lines):
                line_no = zone.start_line + rel_idx
                inline_spans = scan_inline_spans(line, line_no)
                for sp in inline_spans:
                    if sp.zone_type in (Zone.INLINE_MATH, Zone.DISPLAY_MATH):
                        content = sp.content.strip()
                        if content:
                            spans_out.append(
                                MathSpan(
                                    content=content,
                                    display=(sp.zone_type == Zone.DISPLAY_MATH),
                                    delimiter=sp.delimiter,
                                    line=line_no,
                                    col=sp.start_col,
                                )
                            )

    return spans_out


def _html_escape_math(text: str) -> str:
    """Escape HTML special characters inside simulated <math-renderer> elements."""
    return html.escape(text, quote=False)


def _norm_math(text: str) -> str:
    return text.replace("\r\n", "\n").strip()


def _has_escaped_underscore_in_text_macro(tex: str) -> bool:
    return any(r"\_" in tex[start:end] for start, end in _find_text_macro_ranges(tex))


def _spans_equivalent(intended: MathSpan, received: MathSpan, allow_underscore_unescape: bool) -> bool:
    exp = _norm_math(intended.content)
    got = _norm_math(received.content)
    if exp == got:
        return True
    return (
        allow_underscore_unescape and exp.replace(r"\_", "_") == got and not _has_escaped_underscore_in_text_macro(exp)
    )


def _canonical_span_key(span: MathSpan, allow_underscore_unescape: bool) -> str:
    norm = _norm_math(span.content)
    if allow_underscore_unescape and not _has_escaped_underscore_in_text_macro(norm):
        return norm.replace(r"\_", "_")
    return norm


def compare_math_spans(
    intended: list[MathSpan],
    received: list[MathSpan],
    allow_underscore_unescape: bool = True,
) -> list[SpanDiff]:
    """Compare intended math spans against rendered/emulated spans in order."""
    diffs: list[SpanDiff] = []

    if len(intended) != len(received):
        diffs.append(
            SpanDiff(
                category="span-count-mismatch",
                message=(
                    f"Recognized {len(received)}/{len(intended)} math spans "
                    f"(expected {len(intended)}, received {len(received)})."
                ),
            )
        )

    exp_keys = [_canonical_span_key(s, allow_underscore_unescape) for s in intended]
    got_keys = [_norm_math(s.content) for s in received]
    matcher = difflib.SequenceMatcher(None, exp_keys, got_keys, autojunk=False)

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        if tag == "delete":
            for exp in intended[i1:i2]:
                diffs.append(
                    SpanDiff(
                        category="span-dropped",
                        message=f"Math span at line {exp.line} was not recognized as math by GFM.",
                        intended=_norm_math(exp.content),
                        received="",
                        line=exp.line,
                        display=exp.display,
                    )
                )
        elif tag == "replace":
            n_pair = min(i2 - i1, j2 - j1)
            for exp, got in zip(intended[i1 : i1 + n_pair], received[j1 : j1 + n_pair], strict=True):
                diffs.append(
                    SpanDiff(
                        category="span-mutated",
                        message=f"Math span at line {exp.line} mutated during CommonMark processing.",
                        intended=_norm_math(exp.content),
                        received=_norm_math(got.content),
                        line=exp.line,
                        display=exp.display,
                    )
                )
            for exp in intended[i1 + n_pair : i2]:
                diffs.append(
                    SpanDiff(
                        category="span-dropped",
                        message=f"Math span at line {exp.line} was not recognized as math by GFM.",
                        intended=_norm_math(exp.content),
                        received="",
                        line=exp.line,
                        display=exp.display,
                    )
                )

    return diffs


def emulate_gfm_document(markdown_content: str) -> EmulationResult:
    """Emulate GitHub's CommonMark + MathJax preprocessing locally with zero dependencies."""
    intended_spans = extract_intended_math_spans(markdown_content)
    received_spans: list[MathSpan] = []
    html_parts: list[str] = []

    lines = markdown_content.splitlines(keepends=True)
    if not lines:
        return EmulationResult(intended_spans=[], received_spans=[], rendered_html="", diffs=[])

    zones = scan_document_zones(lines)

    def _render_inline_line(
        line_text: str,
        line_no: int,
        indent_level: int = 0,
        parent_block: str | None = None,
    ) -> str:
        raw_line = line_text.rstrip("\r\n")
        spans = scan_inline_spans(raw_line, line_no)
        colliding = find_colliding_math_underscores(spans, macro_ranges_fn=_find_text_macro_ranges)
        colliding_keys = {(sp.start_col, u_pos) for sp, u_pos in colliding}
        parts: list[str] = []

        for span in spans:
            if span.zone_type == Zone.INLINE_CODE:
                parts.append(f"<code>{html.escape(span.content, quote=False)}</code>")
            elif span.zone_type == Zone.COMMENT:
                parts.append(span.raw)
            elif span.zone_type == Zone.INLINE_MATH and span.delimiter == "$`":
                inner = span.content.strip()
                if inner:
                    received_spans.append(
                        MathSpan(content=inner, display=False, delimiter="$`", line=line_no, col=span.start_col)
                    )
                parts.append(f'<math-renderer class="js-inline-math">${_html_escape_math(inner)}$</math-renderer>')
            elif span.zone_type == Zone.DISPLAY_MATH and span.delimiter == "$$":
                if indent_level > 0 or parent_block == "list_item":
                    parts.append(html.escape(span.raw, quote=False))
                else:
                    unescaped = emulate_github_math_escapes(span.content.strip(), display=True)
                    if unescaped:
                        received_spans.append(
                            MathSpan(content=unescaped, display=True, delimiter="$$", line=line_no, col=span.start_col)
                        )
                    parts.append(
                        f'<math-renderer class="js-display-math">$${_html_escape_math(unescaped)}$$</math-renderer>'
                    )
            elif span.zone_type == Zone.INLINE_MATH and span.delimiter == "$":
                open_idx = span.start_col - 1
                close_idx = span.end_col - 1
                bad_open = open_idx > 0 and (
                    raw_line[open_idx - 1] in ("-", "\u2013", "\u2014", "/") or raw_line[open_idx - 1].isalnum()
                )
                bad_close = close_idx < len(raw_line) and raw_line[close_idx].isalnum()
                if bad_open or bad_close:
                    parts.append(html.escape(span.raw, quote=False))
                    continue

                unescaped = emulate_github_math_escapes(span.content, display=False).strip()
                has_collision = any(sp_col == span.start_col for sp_col, _ in colliding_keys)
                if unescaped:
                    received_spans.append(
                        MathSpan(content=unescaped, display=False, delimiter="$", line=line_no, col=span.start_col)
                    )
                if has_collision and _UNESCAPED_UNDERSCORE_RE.search(span.content):
                    corrupted = re.sub(
                        r"(?<!\\)_([a-zA-Z0-9\\{}]+)(?<!\\)_",
                        r"<em>\1</em>",
                        _html_escape_math(unescaped),
                    )
                    if "<em>" not in corrupted:
                        corrupted = re.sub(r"(?<!\\)_", "<em>_</em>", _html_escape_math(unescaped), count=1)
                    parts.append(f'<math-renderer class="js-inline-math">${corrupted}$</math-renderer>')
                else:
                    parts.append(
                        f'<math-renderer class="js-inline-math">${_html_escape_math(unescaped)}$</math-renderer>'
                    )
            else:
                parts.append(html.escape(span.raw, quote=False))

        return "".join(parts)

    for idx, zone in enumerate(zones):
        if zone.zone_type in (Zone.FRONTMATTER, Zone.COMMENT):
            continue

        if zone.zone_type == Zone.FENCED_CODE:
            info = zone.info.strip()
            inner_lines = zone.lines[1:-1] if zone.is_closed and len(zone.lines) >= 2 else zone.lines[1:]
            if info.lower() == "math":
                stripped_math_lines = [
                    _BQ_PREFIX_RE.sub("", ln)
                    if (zone.parent_block == "blockquote" or ln.lstrip().startswith(">"))
                    else ln
                    for ln in inner_lines
                ]
                inner_text = "".join(stripped_math_lines).strip()
                if inner_text:
                    received_spans.append(
                        MathSpan(content=inner_text, display=True, delimiter="```math", line=zone.start_line, col=1)
                    )
                html_parts.append(
                    f'<math-renderer class="js-display-math">$${_html_escape_math(inner_text)}$$</math-renderer>'
                )
            else:
                inner_text = "".join(inner_lines).strip()
                lang_attr = f' class="language-{html.escape(info, quote=True)}"' if info else ""
                html_parts.append(f"<pre><code{lang_attr}>\n{html.escape(inner_text, quote=False)}\n</code></pre>")
            continue

        if zone.zone_type == Zone.DISPLAY_MATH:
            stripped_inner = _strip_display_math_zone(zone.lines, zone.parent_block)
            has_internal_blank = any(ln.strip() == "" for ln in stripped_inner)
            is_bq = zone.parent_block == "blockquote"
            prev_valid = idx == 0 or not zones[idx - 1].lines or _is_valid_display_pad(zones[idx - 1].lines[-1], is_bq)
            next_valid = (
                idx + 1 >= len(zones)
                or not zones[idx + 1].lines
                or _is_valid_display_pad(zones[idx + 1].lines[0], is_bq)
            )

            valid_display = (
                zone.is_closed
                and zone.indent_level == 0
                and not has_internal_blank
                and not has_block_interrupt(stripped_inner)
                and prev_valid
                and next_valid
            )
            if valid_display:
                raw_tex = "".join(stripped_inner).strip()
                unescaped_tex = emulate_github_math_escapes(raw_tex, display=True)
                if unescaped_tex:
                    received_spans.append(
                        MathSpan(content=unescaped_tex, display=True, delimiter="$$", line=zone.start_line, col=1)
                    )
                html_parts.append(
                    f'<math-renderer class="js-display-math">$${_html_escape_math(unescaped_tex)}$$</math-renderer>'
                )
            else:
                html_parts.append(f"<p>{html.escape(zone.content.strip(), quote=False)}</p>")
            continue

        if zone.zone_type == Zone.TABLE:
            html_parts.append("<table>")
            for r_idx, row in enumerate(zone.lines):
                stripped_row = row.strip()
                if _TABLE_DELIM_ROW_RE.match(stripped_row):
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
            m_heading = re.match(r"^\s{0,3}(#{1,6})\s+(.*)$", raw_prose)
            if m_heading:
                level = len(m_heading.group(1))
                rendered_body = _render_inline_line(
                    m_heading.group(2),
                    zone.start_line,
                    indent_level=zone.indent_level,
                    parent_block=zone.parent_block,
                )
                html_parts.append(f"<h{level}>{rendered_body}</h{level}>")
            elif raw_prose.lstrip().startswith(">"):
                bq_body = re.sub(r"^\s*(?:>\s?)+", "", raw_prose)
                rendered_body = _render_inline_line(
                    bq_body,
                    zone.start_line,
                    indent_level=zone.indent_level,
                    parent_block=zone.parent_block,
                )
                html_parts.append(f"<blockquote><p>{rendered_body}</p></blockquote>")
            else:
                rendered_line = _render_inline_line(
                    raw_prose,
                    zone.start_line,
                    indent_level=zone.indent_level,
                    parent_block=zone.parent_block,
                )
                html_parts.append(f"<p>{rendered_line}</p>")

    rendered_html = "\n".join(html_parts)
    diffs = compare_math_spans(intended_spans, received_spans)
    return EmulationResult(
        intended_spans=intended_spans,
        received_spans=received_spans,
        rendered_html=rendered_html,
        diffs=diffs,
    )
