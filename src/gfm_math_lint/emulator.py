"""Zero-dependency emulator of GitHub CommonMark math escape, flanking, and block rules."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from gfm_math_lint.tokenizer import InlineSpan, Zone

if TYPE_CHECKING:
    from collections.abc import Callable

ASCII_PUNCT: str = re.escape(r"""!"#$%&'()*+,-./:;<=>?@[\]^_`{|}~""")
COMMONMARK_UNESCAPE_RE: re.Pattern[str] = re.compile(r"\\([" + ASCII_PUNCT + r"])")
BLOCK_INTERRUPT_RE: re.Pattern[str] = re.compile(r"^\s{0,3}(?:[-+*]\s+|>\s*|#{1,6}(?:\s|$)|\d+[.)]\s+|=+\s*$|-+\s*$)")
_UNESCAPED_UNDERSCORE_RE: re.Pattern[str] = re.compile(r"(?<!\\)_")


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
