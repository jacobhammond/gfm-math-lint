"""Lexical Zone Tokenizer for gfm-math-lint.

Zero-dependency single-pass state machine segmenting Markdown documents
into discrete semantic zones before linting rules execute.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence


class Zone(StrEnum):
    """Semantic document zones."""

    FRONTMATTER = "frontmatter"  # YAML metadata between opening --- and ---
    FENCED_CODE = "fenced_code"  # ``` or ~~~ code blocks (tracks fence length N)
    INLINE_CODE = "inline_code"  # `...` or ``...`` inline code spans
    DISPLAY_MATH = "display_math"  # Standalone $$ ... $$ display blocks
    INLINE_MATH = "inline_math"  # Inline $...$ or $`...`$ math spans
    TABLE = "table"  # GFM table rows (| col | col |)
    COMMENT = "comment"  # HTML comments (<!-- ... -->)
    PROSE = "prose"  # Standard body paragraphs and headers


@dataclass(frozen=True)
class DocumentZone:
    """A contiguous block-level semantic zone in a document."""

    zone_type: Zone
    content: str
    start_line: int  # 1-indexed
    end_line: int  # 1-indexed
    lines: list[str] = field(default_factory=list)
    fence_char: str = ""
    fence_len: int = 0
    info: str = ""
    is_closed: bool = True
    parent_block: str | None = None
    indent_level: int = 0
    list_marker: str = ""


@dataclass(frozen=True)
class InlineSpan:
    """An inline semantic span within a line."""

    zone_type: Zone
    content: str  # Inner content without delimiters
    raw: str  # Full raw text including delimiters
    line: int  # 1-indexed
    start_col: int  # 1-indexed
    end_col: int  # 1-indexed (exclusive)
    delimiter: str = ""


# Regex to detect code fences: optional leading spaces, 3+ backticks or tildes, then optional info string
FENCE_OPEN_RE = re.compile(r"^(\s*)(`{3,}|~{3,})(.*)$")

# Regex to detect blockquote fenced code blocks
BLOCKQUOTE_FENCE_OPEN_RE = re.compile(r"^(\s{0,3}(?:>\s*)+)(`{3,}|~{3,})(.*)$")

# Regex to detect display math delimiter lines: optional whitespace/blockquote prefix, $$, optional whitespace
DISPLAY_MATH_LINE_RE = re.compile(r"^\s*(?:>\s*)*\$\$\s*$")

# Regex to detect list item opening lines
LIST_ITEM_RE = re.compile(r"^(\s*)(\*|-|\+|\d+[.)])\s+")

# Regex to detect HTML comment opening and closing (supports standard --> and HTML5 --!>)
COMMENT_OPEN_RE = re.compile(r"<!--")
COMMENT_CLOSE_RE = re.compile(r"--!?>")

TABLE_DELIM_CELL_RE = re.compile(r"^:?-+:?$")
CURRENCY_SPAN_RE = re.compile(r"\$(\d+(?:,\d{3})*(?:\.\d{1,2})?(?:[kKmMbB]|(?=[,\s\.\)\?!]|$)))")
_CURRENCY_RANGE_CAND_RE = re.compile(r"^\d+(?:,\d{3})*(?:\.\d{1,2})?[kKmMbB]?\s*[-/\u2013\u2014]\s*$")

_CODE_DELIM_CACHE: dict[int, re.Pattern[str]] = {}


def _get_code_delim_pattern(bt_count: int) -> re.Pattern[str]:
    pattern = _CODE_DELIM_CACHE.get(bt_count)
    if pattern is None:
        delim = "`" * bt_count
        pattern = re.compile(rf"(?<!`){delim}(?!`)")
        _CODE_DELIM_CACHE[bt_count] = pattern
    return pattern


def is_escaped(s: str, pos: int) -> bool:
    """Check if character at pos in s is escaped by an odd number of preceding backslashes."""
    count = 0
    p = pos - 1
    while p >= 0 and s[p] == "\\":
        count += 1
        p -= 1
    return count % 2 == 1


def is_table_delimiter_row(line: str) -> bool:
    """Determine whether a line is a GFM table delimiter row (e.g. | :--- | ---: | or :--- | ---:)."""
    s = line.strip().strip("|")
    if not s:
        return False
    cells = [c.strip() for c in s.split("|")]
    valid_cells = [c for c in cells if c]
    return bool(valid_cells and all(TABLE_DELIM_CELL_RE.match(c) for c in valid_cells))


def is_table_row(line: str) -> bool:
    """Determine whether a line is a GFM table row."""
    s = line.strip()
    if s.startswith("|") and s.endswith("|") and len(s) >= 2:
        return True
    return bool("|" in s and not s.startswith("<!--") and not s.startswith(">"))


def scan_document_zones(lines: Sequence[str]) -> list[DocumentZone]:
    """Scan document lines into top-level semantic zones with block-context metadata."""
    zones: list[DocumentZone] = []
    i = 0
    total = len(lines)
    in_list = False
    current_list_marker = ""

    # 1. Check Frontmatter at the very beginning of the document (supporting optional UTF-8 BOM)
    first_line_clean = lines[0].lstrip("\ufeff").strip() if total > 0 else ""
    if total > 0 and first_line_clean == "---":
        fm_lines = [lines[0]]
        i = 1
        fm_closed = False
        while i < total:
            fm_lines.append(lines[i])
            if lines[i].strip() == "---":
                fm_closed = True
                i += 1
                break
            i += 1
        zones.append(
            DocumentZone(
                zone_type=Zone.FRONTMATTER,
                content="".join(fm_lines),
                start_line=1,
                end_line=i,
                lines=fm_lines,
                is_closed=fm_closed,
            )
        )

    while i < total:
        line = lines[i]

        # 2a. Check Blockquote Fenced Code Blocks (> ```bash or   > ```math)
        m_bq = BLOCKQUOTE_FENCE_OPEN_RE.match(line)
        if m_bq:
            bq_prefix = m_bq.group(1)
            bq_leading_ws = len(bq_prefix) - len(bq_prefix.lstrip(" \t"))
            bq_parent = "list_item" if (in_list and bq_leading_ws > 0) else "blockquote"
            bq_marker = current_list_marker if bq_parent == "list_item" else ""

            fence = m_bq.group(2)
            info = m_bq.group(3).strip()
            fence_char = fence[0]
            fence_len = len(fence)
            start_line = i + 1
            code_lines = [line]
            i += 1
            closed = False
            while i < total:
                curr_line = lines[i]
                m_bq_line = re.match(r"^\s{0,3}(?:>\s*)+(.*)$", curr_line)
                if not m_bq_line:
                    break
                code_lines.append(curr_line)
                rest = m_bq_line.group(1)
                m_close = re.match(r"^ {0,3}(`{3,}|~{3,})\s*$", rest)
                if m_close and m_close.group(1)[0] == fence_char and len(m_close.group(1)) >= fence_len:
                    closed = True
                    i += 1
                    break
                i += 1

            zones.append(
                DocumentZone(
                    zone_type=Zone.FENCED_CODE,
                    content="".join(code_lines),
                    start_line=start_line,
                    end_line=i,
                    lines=code_lines,
                    fence_char=fence_char,
                    fence_len=fence_len,
                    info=info,
                    is_closed=closed,
                    parent_block=bq_parent,
                    indent_level=bq_leading_ws,
                    list_marker=bq_marker,
                )
            )
            continue

        # 2b. Check Standard and List-nested Fenced Code Blocks (``` or ~~~)
        m_fence = FENCE_OPEN_RE.match(line)
        if m_fence:
            fence_ws = len(m_fence.group(1))
            fence_parent = "list_item" if in_list else None
            fence_marker = current_list_marker if in_list else ""

            fence = m_fence.group(2)
            info = m_fence.group(3).strip()
            fence_char = fence[0]
            fence_len = len(fence)
            start_line = i + 1
            code_lines = [line]
            i += 1
            fence_stack = [fence_len]
            closed = False
            while i < total:
                curr_line = lines[i]
                code_lines.append(curr_line)
                # Check if this is an inner opening fence with an info string
                m_inner = FENCE_OPEN_RE.match(curr_line)
                if m_inner and m_inner.group(3).strip() != "" and m_inner.group(2)[0] == fence_char:
                    fence_stack.append(len(m_inner.group(2)))
                else:
                    # CommonMark closing fence: optional leading spaces, matching fence char, length >= current
                    m_close = re.match(r"^\s*(`{3,}|~{3,})\s*$", curr_line)
                    if m_close and m_close.group(1)[0] == fence_char:
                        close_len = len(m_close.group(1))
                        if close_len >= fence_stack[-1]:
                            fence_stack.pop()
                            if not fence_stack:
                                closed = True
                                i += 1
                                break
                i += 1

            zones.append(
                DocumentZone(
                    zone_type=Zone.FENCED_CODE,
                    content="".join(code_lines),
                    start_line=start_line,
                    end_line=i,
                    lines=code_lines,
                    fence_char=fence_char,
                    fence_len=fence_len,
                    info=info,
                    is_closed=closed,
                    parent_block=fence_parent,
                    indent_level=fence_ws,
                    list_marker=fence_marker,
                )
            )
            continue

        # 2c. Check CommonMark Indented Code Blocks (>= 4 spaces or \t after blank line)
        prev_is_blank = (i == 0) or (lines[i - 1].strip() == "")
        if (
            prev_is_blank
            and not in_list
            and (line.startswith("    ") or line.startswith("\t"))
            and line.strip() != ""
            and not DISPLAY_MATH_LINE_RE.match(line)
            and not re.match(r"^\s*(?:\*|-|\+|\d+\.)\s+", line)
            and not line.lstrip().startswith(">")
        ):
            ind_ws = len(line) - len(line.lstrip(" \t"))
            start_line = i + 1
            code_lines = [line]
            i += 1
            while i < total:
                curr = lines[i]
                if curr.startswith("    ") or curr.startswith("\t"):
                    code_lines.append(curr)
                    i += 1
                elif curr.strip() == "":
                    # Check lookahead: is there another indented line?
                    has_more = False
                    for k in range(i + 1, total):
                        if lines[k].startswith("    ") or lines[k].startswith("\t"):
                            has_more = True
                            break
                        elif lines[k].strip() != "":
                            break
                    if has_more:
                        code_lines.append(curr)
                        i += 1
                    else:
                        break
                else:
                    break

            zones.append(
                DocumentZone(
                    zone_type=Zone.FENCED_CODE,
                    content="".join(code_lines),
                    start_line=start_line,
                    end_line=i,
                    lines=code_lines,
                    fence_char="",
                    fence_len=0,
                    info="",
                    is_closed=True,
                    parent_block="list_item" if in_list else None,
                    indent_level=ind_ws,
                    list_marker=current_list_marker if in_list else "",
                )
            )
            continue

        # 3. Check Multi-line HTML Comments starting at start of line
        if line.strip().startswith("<!--") and not COMMENT_CLOSE_RE.search(line):
            start_line = i + 1
            comment_lines = [line]
            i += 1
            closed = False
            while i < total:
                curr_line = lines[i]
                comment_lines.append(curr_line)
                if COMMENT_CLOSE_RE.search(curr_line):
                    closed = True
                    i += 1
                    break
                i += 1
            zones.append(
                DocumentZone(
                    zone_type=Zone.COMMENT,
                    content="".join(comment_lines),
                    start_line=start_line,
                    end_line=i,
                    lines=comment_lines,
                    is_closed=closed,
                )
            )
            continue

        # 4. Check Standalone Display Math Blocks ($$ or > $$)
        if DISPLAY_MATH_LINE_RE.match(line):
            dm_ws = len(line) - len(line.lstrip(" \t"))
            dm_is_bq = line.lstrip(" \t").startswith(">")
            if dm_is_bq:
                dm_parent: str | None = "list_item" if (in_list and dm_ws > 0) else "blockquote"
            elif in_list:
                dm_parent = "list_item"
            else:
                dm_parent = None
            dm_marker = current_list_marker if dm_parent == "list_item" else ""

            start_line = i + 1
            math_lines = [line]
            i += 1
            closed = False
            while i < total:
                curr_line = lines[i]
                math_lines.append(curr_line)
                if DISPLAY_MATH_LINE_RE.match(curr_line):
                    closed = True
                    i += 1
                    break
                i += 1
            zones.append(
                DocumentZone(
                    zone_type=Zone.DISPLAY_MATH,
                    content="".join(math_lines),
                    start_line=start_line,
                    end_line=i,
                    lines=math_lines,
                    is_closed=closed,
                    parent_block=dm_parent,
                    indent_level=dm_ws,
                    list_marker=dm_marker,
                )
            )
            continue

        # 5. Check GFM Tables (with or without outer pipes)
        is_table_start = False
        if is_table_delimiter_row(line):
            is_table_start = True
        elif is_table_row(line):
            s_stripped = line.strip()
            if (i + 1 < total and is_table_delimiter_row(lines[i + 1])) or (
                s_stripped.startswith("|") and s_stripped.endswith("|") and len(s_stripped) >= 2
            ):
                is_table_start = True

        if is_table_start:
            tbl_ws = len(line) - len(line.lstrip(" \t"))
            tbl_parent = "list_item" if (in_list and tbl_ws > 0) else "table"
            if tbl_ws == 0:
                in_list = False
                current_list_marker = ""
            start_line = i + 1
            table_lines = [line]
            i += 1
            while i < total and is_table_row(lines[i]) and lines[i].strip() != "":
                table_lines.append(lines[i])
                i += 1
            zones.append(
                DocumentZone(
                    zone_type=Zone.TABLE,
                    content="".join(table_lines),
                    start_line=start_line,
                    end_line=i,
                    lines=table_lines,
                    parent_block=tbl_parent,
                    indent_level=tbl_ws,
                    list_marker=current_list_marker if tbl_parent == "list_item" else "",
                )
            )
            continue

        # 6. Standard Prose Line (track list & blockquote state)
        m_list = LIST_ITEM_RE.match(line)
        prose_ws = len(line) - len(line.lstrip(" \t"))
        if m_list:
            in_list = True
            current_list_marker = m_list.group(2)
            prose_parent: str | None = "list_item"
            prose_indent = len(m_list.group(1))
            prose_marker = current_list_marker
        elif line.strip() == "":
            prose_parent = None
            prose_indent = 0
            prose_marker = ""
        elif line.lstrip(" \t").startswith(">"):
            prose_parent = "list_item" if (in_list and prose_ws > 0) else "blockquote"
            prose_indent = prose_ws
            prose_marker = current_list_marker if prose_parent == "list_item" else ""
            if prose_ws == 0:
                in_list = False
                current_list_marker = ""
        elif prose_ws > 0:
            prose_parent = "list_item" if in_list else None
            prose_indent = prose_ws
            prose_marker = current_list_marker if in_list else ""
        else:
            in_list = False
            current_list_marker = ""
            prose_parent = None
            prose_indent = 0
            prose_marker = ""

        zones.append(
            DocumentZone(
                zone_type=Zone.PROSE,
                content=line,
                start_line=i + 1,
                end_line=i + 1,
                lines=[line],
                parent_block=prose_parent,
                indent_level=prose_indent,
                list_marker=prose_marker,
            )
        )
        i += 1

    return zones


def scan_inline_spans(line: str, line_no: int) -> list[InlineSpan]:
    """Scan a single line for inline semantic spans.

    Extracts inline HTML comments, code spans (`...`), backtick math ($`...`$),
    and inline math spans ($...$). Remaining text segments are marked as PROSE.
    """
    spans: list[InlineSpan] = []
    idx = 0
    line_len = len(line)

    while idx < line_len:
        # 1. HTML comments: <!-- ... --> or <!-- ... --!>
        if line.startswith("<!--", idx):
            m_close = COMMENT_CLOSE_RE.search(line, idx + 4)
            if m_close is not None:
                end_pos = m_close.end()
                raw = line[idx:end_pos]
                content = line[idx + 4 : m_close.start()].strip()
                spans.append(
                    InlineSpan(
                        zone_type=Zone.COMMENT,
                        content=content,
                        raw=raw,
                        line=line_no,
                        start_col=idx + 1,
                        end_col=end_pos + 1,
                        delimiter="<!--",
                    )
                )
                idx = end_pos
                continue

        # 2. Backtick math: $`...`$
        if line.startswith("$`", idx):
            # Find closing `$
            close_idx = line.find("`$", idx + 2)
            if close_idx != -1:
                end_pos = close_idx + 2
                raw = line[idx:end_pos]
                content = line[idx + 2 : close_idx]
                spans.append(
                    InlineSpan(
                        zone_type=Zone.INLINE_MATH,
                        content=content,
                        raw=raw,
                        line=line_no,
                        start_col=idx + 1,
                        end_col=end_pos + 1,
                        delimiter="$`",
                    )
                )
                idx = end_pos
                continue

        # 3. Inline code span: `...` or ``...``
        if line[idx] == "`":
            # Count opening backticks
            bt_count = 0
            while idx + bt_count < line_len and line[idx + bt_count] == "`":
                bt_count += 1
            delim = line[idx : idx + bt_count]

            # Look for matching delimiter of length bt_count
            pattern = _get_code_delim_pattern(bt_count)
            match = pattern.search(line, idx + bt_count)
            if match:
                end_pos = match.end()
                raw = line[idx:end_pos]
                inner_content = line[idx + bt_count : match.start()]
                spans.append(
                    InlineSpan(
                        zone_type=Zone.INLINE_CODE,
                        content=inner_content,
                        raw=raw,
                        line=line_no,
                        start_col=idx + 1,
                        end_col=end_pos + 1,
                        delimiter=delim,
                    )
                )
                idx = end_pos
                continue

        # 4. Inline display math on a single line: $$...$$
        if line.startswith("$$", idx):
            # Find closing $$
            close_idx = line.find("$$", idx + 2)
            if close_idx != -1:
                end_pos = close_idx + 2
                raw = line[idx:end_pos]
                content = line[idx + 2 : close_idx]
                spans.append(
                    InlineSpan(
                        zone_type=Zone.DISPLAY_MATH,
                        content=content,
                        raw=raw,
                        line=line_no,
                        start_col=idx + 1,
                        end_col=end_pos + 1,
                        delimiter="$$",
                    )
                )
                idx = end_pos
                continue

        # 5. Inline math: $...$
        if line[idx] == "$" and not is_escaped(line, idx):
            # Check if this could be an inline math span
            # Find next non-escaped single $ (not $$)
            close_idx = -1
            j = idx + 1
            while j < line_len:
                if line[j] == "\\" and j + 1 < line_len:
                    j += 2
                    continue
                if line[j] == "$":
                    # Check not $$
                    if (j + 1 < line_len and line[j + 1] == "$") or (j > 0 and line[j - 1] == "$"):
                        j += 1
                        continue
                    close_idx = j
                    break
                j += 1

            # Disambiguate inline math from prose currency pairs (e.g. "$10 to $20" or "$10 for $x$")
            # A candidate starting with a digit and ending with whitespace is currency in prose,
            # not a valid closed inline math formula.
            is_currency_pair = False
            if close_idx != -1:
                cand = line[idx + 1 : close_idx]
                if (cand and cand[0].isdigit() and cand.endswith(" ")) or (
                    _CURRENCY_RANGE_CAND_RE.match(cand) and close_idx + 1 < line_len and line[close_idx + 1].isdigit()
                ):
                    is_currency_pair = True

            if close_idx != -1 and not is_currency_pair:
                candidate = line[idx + 1 : close_idx]
                end_pos = close_idx + 1
                raw = line[idx:end_pos]
                spans.append(
                    InlineSpan(
                        zone_type=Zone.INLINE_MATH,
                        content=candidate,
                        raw=raw,
                        line=line_no,
                        start_col=idx + 1,
                        end_col=end_pos + 1,
                        delimiter="$",
                    )
                )
                idx = end_pos
                continue

        # 7. Accumulate prose text
        prose_start = idx
        idx += 1  # Always consume at least 1 character to guarantee forward progress
        while idx < line_len:
            ch = line[idx]
            if ch == "`":
                break
            if ch == "$" and not is_escaped(line, idx):
                break
            if line.startswith("<!--", idx):
                break
            idx += 1

        prose_text = line[prose_start:idx]
        spans.append(
            InlineSpan(
                zone_type=Zone.PROSE,
                content=prose_text,
                raw=prose_text,
                line=line_no,
                start_col=prose_start + 1,
                end_col=idx + 1,
                delimiter="",
            )
        )

    return spans
