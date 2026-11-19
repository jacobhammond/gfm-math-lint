"""GFM MathJax and KaTeX parsing rules (GFM-M01 through GFM-M18)."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from collections.abc import Sequence

from gfm_math_lint.emulator import BLOCK_INTERRUPT_RE, find_colliding_math_underscores, has_block_interrupt
from gfm_math_lint.fixer import LintEdit
from gfm_math_lint.rules.base import Rule, Violation
from gfm_math_lint.tokenizer import (
    DISPLAY_MATH_LINE_RE,
    DocumentZone,
    Zone,
    is_escaped,
    scan_inline_spans,
)
from gfm_math_lint.verifier import STANDARD_MATH_FUNCTIONS

# Helper for parsing LaTeX macros with balanced braces
TEXT_MACROS = ("text", "mathrm", "mathbf", "operatorname")

INLINE_DISPLAY_MATH_RE = re.compile(r"^(\s*)\$\$(.+?)\$\$(\s*)$")
TEXT_UNDERSCORE_RE = re.compile(r"(?:\\\\_|\\_|_)")

BACKSLASH_PUNCT_PATTERNS = [
    (re.compile(r"\\left\\\{"), "\\left\\lbrace", "Replace \\left\\{ with \\left\\lbrace"),
    (re.compile(r"\\right\\\}"), "\\right\\rbrace", "Replace \\right\\} with \\right\\rbrace"),
    (re.compile(r"(?<!\\)(?<!\\left)\\\{"), "\\lbrace", "Replace \\{ with \\lbrace"),
    (re.compile(r"(?<!\\)(?<!\\right)\\\}"), "\\rbrace", "Replace \\} with \\rbrace"),
    (re.compile(r"(?<!\\)\\,"), "\\thinspace", "Replace \\, with \\thinspace"),
    (re.compile(r"(?<!\\)\\:"), "\\medspace", "Replace \\: with \\medspace"),
    (re.compile(r"(?<!\\)\\;"), "\\thickspace", "Replace \\; with \\thickspace"),
    (re.compile(r"(?<!\\)\\!"), "\\negthinspace", "Replace \\! with \\negthinspace"),
    (re.compile(r"\\left\\\|"), "\\left\\lVert", "Replace \\left\\| with \\left\\lVert"),
    (re.compile(r"\\right\\\|"), "\\right\\rVert", "Replace \\right\\| with \\right\\rVert"),
    (re.compile(r"(?<!\\)(?<!\\left)(?<!\\right)\\\|"), "\\Vert", "Replace \\| with \\Vert"),
]

RELATIONAL_LT_RE = re.compile(r"<([a-zA-Z])")
HTML_TAG_AT_START_RE = re.compile(
    r"^<(?:br|em|strong|i|b|u|a|sub|sup|p|span|div|code|pre|math-renderer)\b[^>]*>",
    re.IGNORECASE,
)

ASTERISK_EMPHASIS_PATTERNS = [
    (re.compile(r"\^\{\*\}"), "^{\\ast}", "Convert ^{*} to ^{\\ast}"),
    (re.compile(r"\^\*"), "^{\\ast}", "Convert ^* to ^{\\ast}"),
    (re.compile(r"_\{\*\}"), "_{\\ast}", "Convert _{*} to _{\\ast}"),
    (re.compile(r"_\*"), "_{\\ast}", "Convert _* to _{\\ast}"),
]

OPERATORNAME_RE = re.compile(r"\\operatorname\*?(?=\s*\{|\s+[a-zA-Z])")

ALIGN_ENV_PATTERNS = [
    (re.compile(r"\\begin\{align\*?\}"), "\\begin{aligned}", "Replace \\begin{align} with \\begin{aligned}"),
    (re.compile(r"\\end\{align\*?\}"), "\\end{aligned}", "Replace \\end{align} with \\end{aligned}"),
]

CURRENCY_PATTERN = re.compile(r"(?<!\\)\$(\d+(?:,\d{3})*(?:\.\d{1,2})?(?:[kKmMbB]|(?=[,\s\.\)\?!]|$)))(?!\$)")

DISPLAY_LATEX_OPEN_RE = re.compile(r"^\s*\\\[\s*$")
DISPLAY_LATEX_CLOSE_RE = re.compile(r"^\s*\\\]\s*$")
INLINE_DISPLAY_LATEX_RE = re.compile(r"^(\s*)\\\[(.+?)\\\](\s*)$")
INLINE_PAREN_MATH_RE = re.compile(r"(?<!\\)\\\((.+?)(?<!\\)\\\)")


def find_macro_calls(text: str, macro_names: tuple[str, ...]) -> list[tuple[int, int, str, int, int]]:
    """Find occurrences of \\macro{...} with balanced braces.

    Returns list of tuples: (macro_start, macro_end, inner_text, inner_start, inner_end)
    """
    results: list[tuple[int, int, str, int, int]] = []
    i = 0
    length = len(text)

    while i < length:
        if text[i] == "\\":
            for name in macro_names:
                prefix = f"\\{name}"
                if text.startswith(prefix, i):
                    after_prefix = i + len(prefix)
                    # Next char might be optional * (like \operatorname*) then {
                    k = after_prefix
                    if k < length and text[k] == "*":
                        k += 1
                    # Skip whitespace before {
                    while k < length and text[k].isspace():
                        k += 1
                    if k < length and text[k] == "{":
                        # Match balanced braces
                        depth = 1
                        j = k + 1
                        inner_start = j
                        while j < length and depth > 0:
                            if text[j] == "\\":
                                j += 2  # Skip escaped char
                                continue
                            if text[j] == "{":
                                depth += 1
                            elif text[j] == "}":
                                depth -= 1
                            j += 1
                        if depth == 0:
                            inner_end = j - 1
                            macro_end = j
                            results.append((i, macro_end, text[inner_start:inner_end], inner_start, inner_end))
                            i = macro_end - 1
                            break
        i += 1
    return results


class RuleM01(Rule):
    """GFM-M01: Math Code Fence Conversion."""

    id: str = "GFM-M01"
    name: str = "math-fence-conversion"
    description: str = "Convert standalone ```math code fences to $$ ... $$ block math"
    severity: str = "error"

    def check(self, lines: Sequence[str], zones: list[DocumentZone], file_path: str = "") -> list[Violation]:
        violations: list[Violation] = []
        for zone in zones:
            if zone.zone_type == Zone.FENCED_CODE and zone.info.strip().lower() == "math":
                # Preserve ```math fences nested inside lists, blockquotes, or indented blocks (REG-03)
                if (
                    zone.parent_block in ("list_item", "blockquote")
                    or zone.indent_level > 0
                    or (zone.lines and zone.lines[0].startswith((" ", "\t", ">")))
                ):
                    continue

                start_line = zone.start_line
                end_line = zone.end_line
                # Extract inner lines
                inner_lines = zone.lines[1:-1] if zone.is_closed and len(zone.lines) >= 2 else zone.lines[1:]
                # Guard against creating a block-interrupted $$ block (REG-22)
                if has_block_interrupt(inner_lines):
                    continue

                inner_content = "".join(inner_lines)
                if not inner_content.endswith("\n"):
                    inner_content += "\n"

                # Check if blank line padding is needed above or below
                pad_above = ""
                if start_line > 1:
                    line_above = lines[start_line - 2].strip()
                    if line_above != "" and line_above != "---":
                        pad_above = "\n"

                pad_below = ""
                if end_line < len(lines):
                    line_below = lines[end_line].strip()
                    if line_below != "" and line_below != "---":
                        pad_below = "\n"

                replacement = f"{pad_above}$$\n{inner_content}$$\n{pad_below}"

                last_line_len = len(zone.lines[-1]) if zone.lines else 0
                edit = LintEdit(
                    rule_id=self.id,
                    start_line=start_line,
                    start_col=1,
                    end_line=end_line,
                    end_col=last_line_len + 1,
                    replacement=replacement,
                )
                violations.append(
                    Violation(
                        rule_id=self.id,
                        message="Math code fence (```math) should be converted to standalone display math ($$ ... $$).",
                        line=start_line,
                        col=1,
                        severity=self.severity,
                        edit=edit,
                    )
                )
        return violations


def is_valid_display_math_pad(line_text: str, is_blockquote: bool = False) -> bool:
    """Return True if an adjacent line satisfies display-math blank padding requirements."""
    stripped = line_text.strip()
    if stripped in ("", "---"):
        return True
    return bool(is_blockquote and re.match(r"^(?:>\s*)+$", stripped))


class RuleM02(Rule):
    """GFM-M02: Block Math Boundary Isolation & Padding."""

    id: str = "GFM-M02"
    name: str = "display-math-isolation"
    description: str = (
        "Enforce column-0 display math $$ isolation on own lines with blank line padding and no internal blank lines"
    )
    severity: str = "error"

    def check(self, lines: Sequence[str], zones: list[DocumentZone], file_path: str = "") -> list[Violation]:
        violations: list[Violation] = []

        # 1. Check PROSE zones for inline display math ($$...$$) on a single line (including indented list items)
        for zone in zones:
            if zone.zone_type == Zone.PROSE:
                for line_idx, line in enumerate(zone.lines):
                    curr_line_no = zone.start_line + line_idx
                    m = INLINE_DISPLAY_MATH_RE.match(line)
                    if m:
                        leading_ws, inner, _trailing_ws = m.groups()
                        pad_above = ""
                        if curr_line_no > 1 and lines[curr_line_no - 2].strip() not in ("", "---"):
                            pad_above = "\n"

                        pad_below = ""
                        if curr_line_no < len(lines) and lines[curr_line_no].strip() not in ("", "---"):
                            pad_below = "\n"

                        inner_clean = inner.strip()
                        replacement = f"{pad_above}$$\n{inner_clean}\n$$\n{pad_below}"

                        edit = LintEdit(
                            rule_id=self.id,
                            start_line=curr_line_no,
                            start_col=1,
                            end_line=curr_line_no,
                            end_col=len(line) + 1,
                            replacement=replacement,
                        )
                        msg = (
                            "Indented display math ($$) inside list/container breaks on GitHub; "
                            "break out to column 0 with blank line padding."
                            if leading_ws
                            else "Display math ($$) must sit on isolated lines with blank line padding."
                        )
                        violations.append(
                            Violation(
                                rule_id=self.id,
                                message=msg,
                                line=curr_line_no,
                                col=len(leading_ws) + 1,
                                severity=self.severity,
                                edit=edit,
                            )
                        )

        # 2. Check DISPLAY_MATH zones for indentation, blank line padding, and internal blank lines
        for zone in zones:
            if zone.zone_type != Zone.DISPLAY_MATH:
                continue

            if not zone.is_closed:
                violations.append(
                    Violation(
                        rule_id=self.id,
                        message="Unclosed display math block ($$).",
                        line=zone.start_line,
                        col=1,
                        severity=self.severity,
                    )
                )
                continue

            is_indented = zone.indent_level > 0 or (bool(zone.lines) and zone.lines[0].startswith((" ", "\t")))
            is_top_level_bq = zone.parent_block == "blockquote" and not is_indented
            strip_bq = zone.parent_block == "blockquote" or (
                bool(zone.lines) and zone.lines[0].lstrip(" \t").startswith(">")
            )

            if is_indented:
                violations.append(
                    Violation(
                        rule_id=self.id,
                        message=(
                            "Indented display math block ($$) fails to render on GitHub. "
                            "Break out to column 0 with blank line padding."
                        ),
                        line=zone.start_line,
                        col=zone.indent_level + 1,
                        severity=self.severity,
                    )
                )

            has_internal_blanks = False
            cleaned_inner_lines: list[str] = []
            if len(zone.lines) > 2:
                for inner_idx, inner_line in enumerate(zone.lines[1:-1]):
                    actual_line_no = zone.start_line + 1 + inner_idx
                    normalized_inner = re.sub(r"^\s*(?:>\s*)+", "", inner_line) if strip_bq else inner_line
                    if normalized_inner.strip() == "":
                        has_internal_blanks = True
                        violations.append(
                            Violation(
                                rule_id=self.id,
                                message="Internal blank lines within display math blocks are disallowed.",
                                line=actual_line_no,
                                col=1,
                                severity=self.severity,
                            )
                        )
                    else:
                        if is_indented:
                            stripped_line = re.sub(r"^\s*(?:>\s*)*", "", inner_line)
                            cleaned_inner_lines.append(stripped_line)
                        else:
                            cleaned_inner_lines.append(inner_line)
            else:
                cleaned_inner_lines = zone.lines[1:-1] if len(zone.lines) > 1 else []

            # Check padding above/below (blockquote > $$ requires > separator lines against adjacent quote text)
            need_pad_above = False
            need_pad_below = False
            if zone.start_line > 1 and not is_valid_display_math_pad(lines[zone.start_line - 2], is_top_level_bq):
                need_pad_above = True

            if zone.end_line < len(lines) and not is_valid_display_math_pad(lines[zone.end_line], is_top_level_bq):
                need_pad_below = True

            if need_pad_above or need_pad_below:
                msg_parts = []
                if need_pad_above:
                    msg_parts.append("above")
                if need_pad_below:
                    msg_parts.append("below")
                violations.append(
                    Violation(
                        rule_id=self.id,
                        message=f"Display math block must be padded with a blank line {' and '.join(msg_parts)}.",
                        line=zone.start_line,
                        col=1,
                        severity=self.severity,
                    )
                )

            # Synthesize ONE unified edit if indented, has internal blanks, or missing padding
            if is_indented or has_internal_blanks or need_pad_above or need_pad_below:
                pad_above = ""
                if need_pad_above:
                    pad_above = (
                        ">\n" if (is_top_level_bq and lines[zone.start_line - 2].lstrip().startswith(">")) else "\n"
                    )
                pad_below = ""
                if need_pad_below:
                    pad_below = ">\n" if (is_top_level_bq and lines[zone.end_line].lstrip().startswith(">")) else "\n"
                opening = "$$\n" if is_indented else zone.lines[0]
                if not opening.endswith("\n"):
                    opening += "\n"
                closing = "$$\n" if is_indented else (zone.lines[-1] if len(zone.lines) > 1 else "$$\n")
                if not closing.endswith("\n"):
                    closing += "\n"
                replacement = f"{pad_above}{opening}{''.join(cleaned_inner_lines)}{closing}{pad_below}"
                last_line_len = len(zone.lines[-1]) if zone.lines else 0
                edit = LintEdit(
                    rule_id=self.id,
                    start_line=zone.start_line,
                    start_col=1,
                    end_line=zone.end_line,
                    end_col=last_line_len + 1,
                    replacement=replacement,
                )
                for idx_v, v in enumerate(violations):
                    if v.rule_id == self.id and zone.start_line <= v.line <= zone.end_line and v.edit is None:
                        violations[idx_v] = Violation(
                            rule_id=v.rule_id,
                            message=v.message,
                            line=v.line,
                            col=v.col,
                            severity=v.severity,
                            edit=edit,
                        )
                        break

        return violations


class RuleM03(Rule):
    """GFM-M03: Text Mode Underscore Hazard."""

    id: str = "GFM-M03"
    name: str = "text-mode-underscore-escape"
    description: str = "Avoid underscores inside text mode macros (\\text{ave_shift}) which break KaTeX or CommonMark"
    severity: str = "error"

    def check(self, lines: Sequence[str], zones: list[DocumentZone], file_path: str = "") -> list[Violation]:
        violations: list[Violation] = []

        def _emit_for_text(text: str, line_no: int, base_col: int, is_standalone_span: bool) -> None:
            macro_calls = find_macro_calls(text, TEXT_MACROS)
            for _, _, inner_text, inner_start, _ in macro_calls:
                for m in TEXT_UNDERSCORE_RE.finditer(inner_text):
                    col_start = base_col + inner_start + m.start()
                    col_end = base_col + inner_start + m.end()
                    # If standalone $\text{snake_case}$, let GFM-M14 convert to inline code backticks
                    edit = (
                        None
                        if is_standalone_span
                        else LintEdit(
                            rule_id=self.id,
                            start_line=line_no,
                            start_col=col_start,
                            end_line=line_no,
                            end_col=col_end,
                            replacement="-",
                        )
                    )
                    violations.append(
                        Violation(
                            rule_id=self.id,
                            message=(
                                "Underscore inside text-mode LaTeX macro causes CommonMark collision "
                                "or KaTeX parse errors. Use hyphens or inline code backticks."
                            ),
                            line=line_no,
                            col=col_start,
                            severity=self.severity,
                            edit=edit,
                        )
                    )

        # Check DISPLAY_MATH zones
        for zone in zones:
            if zone.zone_type == Zone.DISPLAY_MATH:
                if not zone.is_closed:
                    continue
                for line_idx, line in enumerate(zone.lines):
                    line_no = zone.start_line + line_idx
                    if not DISPLAY_MATH_LINE_RE.match(line):
                        _emit_for_text(line, line_no, base_col=1, is_standalone_span=False)

        # Check INLINE_MATH ($...$, $`...`$) and single-line $$...$$ in PROSE and TABLE zones
        for zone in zones:
            if zone.zone_type in (Zone.PROSE, Zone.TABLE):
                for line_idx, line in enumerate(zone.lines):
                    line_no = zone.start_line + line_idx
                    spans = scan_inline_spans(line, line_no)
                    for span in spans:
                        if span.zone_type in (Zone.INLINE_MATH, Zone.DISPLAY_MATH) and span.delimiter in (
                            "$",
                            "$`",
                            "$$",
                        ):
                            is_standalone = bool(
                                span.zone_type == Zone.INLINE_MATH
                                and re.fullmatch(
                                    r"\s*\\(?:text|mathrm|mathbf)\{[a-zA-Z0-9_\\-]+\}\s*",
                                    span.content,
                                )
                            )
                            _emit_for_text(
                                span.content,
                                line_no,
                                base_col=span.start_col + len(span.delimiter),
                                is_standalone_span=is_standalone,
                            )
        return violations


class RuleM04(Rule):
    """GFM-M04: Inline Math Whitespace Stripping."""

    id: str = "GFM-M04"
    name: str = "inline-math-whitespace"
    description: str = "Strip leading and trailing inner whitespace from inline math delimiters ($x$)"
    severity: str = "error"

    def check(self, lines: Sequence[str], zones: list[DocumentZone], file_path: str = "") -> list[Violation]:
        violations: list[Violation] = []
        for zone in zones:
            if zone.zone_type in (Zone.PROSE, Zone.TABLE):
                for line_idx, line in enumerate(zone.lines):
                    line_no = zone.start_line + line_idx
                    spans = scan_inline_spans(line, line_no)
                    for span in spans:
                        if span.zone_type == Zone.INLINE_MATH and span.delimiter == "$":
                            content = span.content
                            stripped = content.strip()
                            if stripped and (content.startswith(" ") or content.endswith(" ")):
                                replacement = f"${stripped}$"
                                edit = LintEdit(
                                    rule_id=self.id,
                                    start_line=line_no,
                                    start_col=span.start_col,
                                    end_line=line_no,
                                    end_col=span.end_col,
                                    replacement=replacement,
                                )
                                violations.append(
                                    Violation(
                                        rule_id=self.id,
                                        message="Inline math delimiters must tightly hug content without whitespace.",
                                        line=line_no,
                                        col=span.start_col,
                                        severity=self.severity,
                                        edit=edit,
                                    )
                                )
        return violations


class RuleM05(Rule):
    """GFM-M05: Backslash-Punctuation Escape Conversion (\\{ -> \\lbrace, \\, -> \\thinspace)."""

    id: str = "GFM-M05"
    name: str = "backslash-punctuation-escape"
    description: str = "Convert CommonMark-stripped backslash-punctuation escapes in math to letter-named macros"
    severity: str = "error"

    def check(self, lines: Sequence[str], zones: list[DocumentZone], file_path: str = "") -> list[Violation]:
        violations: list[Violation] = []

        def check_text(text: str, line_no: int, base_col: int, in_table: bool = False) -> None:
            for pattern, repl, desc in BACKSLASH_PUNCT_PATTERNS:
                if in_table and "\\|" in pattern.pattern:
                    continue
                for m in pattern.finditer(text):
                    # Ensure preceding backslash count is even (don't match trailing part of \\,)
                    if is_escaped(text, m.start()):
                        continue
                    final_repl = repl
                    after_idx = m.end()
                    if (
                        repl in ("\\thinspace", "\\medspace", "\\thickspace", "\\negthinspace", "\\Vert")
                        and after_idx < len(text)
                        and text[after_idx].isalpha()
                    ):
                        final_repl = repl + " "
                    col_start = base_col + m.start()
                    col_end = base_col + m.end()
                    edit = LintEdit(
                        rule_id=self.id,
                        start_line=line_no,
                        start_col=col_start,
                        end_line=line_no,
                        end_col=col_end,
                        replacement=final_repl,
                    )
                    violations.append(
                        Violation(
                            rule_id=self.id,
                            message=f"{desc} to prevent CommonMark backslash stripping.",
                            line=line_no,
                            col=col_start,
                            severity=self.severity,
                            edit=edit,
                        )
                    )

        # 1. DISPLAY_MATH
        for zone in zones:
            if zone.zone_type == Zone.DISPLAY_MATH:
                if not zone.is_closed:
                    continue
                for line_idx, line in enumerate(zone.lines):
                    line_no = zone.start_line + line_idx
                    if not DISPLAY_MATH_LINE_RE.match(line):
                        check_text(line, line_no, base_col=1)

        # 2. INLINE_MATH ($) and single-line DISPLAY_MATH ($$) in PROSE/TABLE (skip $`...`$ backtick math)
        for zone in zones:
            if zone.zone_type in (Zone.PROSE, Zone.TABLE):
                in_table = zone.zone_type == Zone.TABLE
                for line_idx, line in enumerate(zone.lines):
                    line_no = zone.start_line + line_idx
                    spans = scan_inline_spans(line, line_no)
                    for span in spans:
                        if span.zone_type in (Zone.INLINE_MATH, Zone.DISPLAY_MATH) and span.delimiter in ("$", "$$"):
                            check_text(
                                span.content,
                                line_no,
                                base_col=span.start_col + len(span.delimiter),
                                in_table=in_table,
                            )

        return violations


class RuleM06(Rule):
    """GFM-M06: HTML Relational Operator Tag Collision (<i -> \\lt i)."""

    id: str = "GFM-M06"
    name: str = "relational-operator-collision"
    description: str = "Replace < before letters with \\lt to prevent HTML tag collisions"
    severity: str = "error"

    def check(self, lines: Sequence[str], zones: list[DocumentZone], file_path: str = "") -> list[Violation]:
        violations: list[Violation] = []

        def check_text(text: str, line_no: int, base_col: int) -> None:
            for m in RELATIONAL_LT_RE.finditer(text):
                if HTML_TAG_AT_START_RE.match(text[m.start() :]):
                    continue
                letter = m.group(1)
                col_start = base_col + m.start()
                col_end = base_col + m.end()
                edit = LintEdit(
                    rule_id=self.id,
                    start_line=line_no,
                    start_col=col_start,
                    end_line=line_no,
                    end_col=col_end,
                    replacement=f"\\lt {letter}",
                )
                violations.append(
                    Violation(
                        rule_id=self.id,
                        message=f"Replace '<{letter}' with '\\lt {letter}' to prevent HTML tag collisions.",
                        line=line_no,
                        col=col_start,
                        severity=self.severity,
                        edit=edit,
                    )
                )

        for zone in zones:
            if zone.zone_type == Zone.DISPLAY_MATH:
                if not zone.is_closed:
                    continue
                for line_idx, line in enumerate(zone.lines):
                    line_no = zone.start_line + line_idx
                    if not DISPLAY_MATH_LINE_RE.match(line):
                        check_text(line, line_no, base_col=1)
            elif zone.zone_type in (Zone.PROSE, Zone.TABLE):
                for line_idx, line in enumerate(zone.lines):
                    line_no = zone.start_line + line_idx
                    spans = scan_inline_spans(line, line_no)
                    for span in spans:
                        if span.zone_type in (Zone.INLINE_MATH, Zone.DISPLAY_MATH):
                            check_text(span.content, line_no, base_col=span.start_col + len(span.delimiter))

        return violations


class RuleM07(Rule):
    """GFM-M07: Asterisk Emphasis Collision (y^*[n] -> y^{\\ast}[n])."""

    id: str = "GFM-M07"
    name: str = "asterisk-emphasis-collision"
    description: str = "Replace superscripts/subscripts containing raw * with \\ast"
    severity: str = "error"

    def check(self, lines: Sequence[str], zones: list[DocumentZone], file_path: str = "") -> list[Violation]:
        violations: list[Violation] = []

        def check_text(text: str, line_no: int, base_col: int) -> None:
            for pattern, repl, desc in ASTERISK_EMPHASIS_PATTERNS:
                for m in pattern.finditer(text):
                    col_start = base_col + m.start()
                    col_end = base_col + m.end()
                    edit = LintEdit(
                        rule_id=self.id,
                        start_line=line_no,
                        start_col=col_start,
                        end_line=line_no,
                        end_col=col_end,
                        replacement=repl,
                    )
                    violations.append(
                        Violation(
                            rule_id=self.id,
                            message=f"{desc} to prevent Markdown emphasis collisions.",
                            line=line_no,
                            col=col_start,
                            severity=self.severity,
                            edit=edit,
                        )
                    )

        for zone in zones:
            if zone.zone_type == Zone.DISPLAY_MATH:
                if not zone.is_closed:
                    continue
                for line_idx, line in enumerate(zone.lines):
                    line_no = zone.start_line + line_idx
                    if not DISPLAY_MATH_LINE_RE.match(line):
                        check_text(line, line_no, base_col=1)
            elif zone.zone_type in (Zone.PROSE, Zone.TABLE):
                for line_idx, line in enumerate(zone.lines):
                    line_no = zone.start_line + line_idx
                    spans = scan_inline_spans(line, line_no)
                    for span in spans:
                        if span.zone_type in (Zone.INLINE_MATH, Zone.DISPLAY_MATH):
                            check_text(span.content, line_no, base_col=span.start_col + len(span.delimiter))

        return violations


class RuleM08(Rule):
    """GFM-M08: Disallowed Macro Conversion (\\operatorname -> \\text)."""

    id: str = "GFM-M08"
    name: str = "disallowed-macro"
    description: str = "Replace restricted \\operatorname macros with \\text or \\mathop"
    severity: str = "error"

    def check(self, lines: Sequence[str], zones: list[DocumentZone], file_path: str = "") -> list[Violation]:
        violations: list[Violation] = []

        def check_text(text: str, line_no: int, base_col: int) -> None:
            # Match \operatorname or \operatorname* optionally with {arg}
            for m in re.finditer(r"(\\operatorname\*?)(?:\s*\{([^{}]+)\}|(?=\s+[a-zA-Z]))", text):
                op_macro = m.group(1)
                inner_arg = m.group(2)
                col_start = base_col + m.start()
                col_end = base_col + m.end()

                if op_macro.endswith("*"):
                    replacement = f"\\mathop{{\\mathrm{{{inner_arg}}}}}\\limits" if inner_arg else "\\mathop{\\mathrm"
                else:
                    replacement = f"\\mathop{{\\mathrm{{{inner_arg}}}}}" if inner_arg else "\\mathop{\\mathrm"

                edit = LintEdit(
                    rule_id=self.id,
                    start_line=line_no,
                    start_col=col_start,
                    end_line=line_no,
                    end_col=col_end,
                    replacement=replacement,
                )
                violations.append(
                    Violation(
                        rule_id=self.id,
                        message="Replace restricted \\operatorname with \\text or \\mathop in GitHub KaTeX.",
                        line=line_no,
                        col=col_start,
                        severity=self.severity,
                        edit=edit,
                    )
                )

        for zone in zones:
            if zone.zone_type == Zone.DISPLAY_MATH:
                if not zone.is_closed:
                    continue
                for line_idx, line in enumerate(zone.lines):
                    line_no = zone.start_line + line_idx
                    if not DISPLAY_MATH_LINE_RE.match(line):
                        check_text(line, line_no, base_col=1)
            elif zone.zone_type in (Zone.PROSE, Zone.TABLE):
                for line_idx, line in enumerate(zone.lines):
                    line_no = zone.start_line + line_idx
                    spans = scan_inline_spans(line, line_no)
                    for span in spans:
                        if span.zone_type in (Zone.INLINE_MATH, Zone.DISPLAY_MATH):
                            check_text(span.content, line_no, base_col=span.start_col + len(span.delimiter))

        return violations


class RuleM09(Rule):
    """GFM-M09: Top-Level align Environment Disallowance (\\begin{align} -> \\begin{aligned})."""

    id: str = "GFM-M09"
    name: str = "align-environment"
    description: str = "Replace unsupported top-level align environments with aligned"
    severity: str = "error"

    def check(self, lines: Sequence[str], zones: list[DocumentZone], file_path: str = "") -> list[Violation]:
        violations: list[Violation] = []

        for zone in zones:
            if zone.zone_type == Zone.DISPLAY_MATH:
                if not zone.is_closed:
                    continue
                for line_idx, line in enumerate(zone.lines):
                    line_no = zone.start_line + line_idx
                    for pattern, repl, desc in ALIGN_ENV_PATTERNS:
                        for m in pattern.finditer(line):
                            col_start = m.start() + 1
                            col_end = m.end() + 1
                            edit = LintEdit(
                                rule_id=self.id,
                                start_line=line_no,
                                start_col=col_start,
                                end_line=line_no,
                                end_col=col_end,
                                replacement=repl,
                            )
                            violations.append(
                                Violation(
                                    rule_id=self.id,
                                    message=f"{desc} in KaTeX display math.",
                                    line=line_no,
                                    col=col_start,
                                    severity=self.severity,
                                    edit=edit,
                                )
                            )

        return violations


class RuleM10(Rule):
    """GFM-M10: Unescaped Currency Dollar Sign Hijacking."""

    id: str = "GFM-M10"
    name: str = "currency-dollar-sign"
    description: str = "Escape currency dollar signs on lines with multiple dollars or inline math (\\$10)"
    severity: str = "warning"

    def check(self, lines: Sequence[str], zones: list[DocumentZone], file_path: str = "") -> list[Violation]:
        violations: list[Violation] = []

        for zone in zones:
            if zone.zone_type == Zone.PROSE:
                for line_idx, line in enumerate(zone.lines):
                    line_no = zone.start_line + line_idx
                    spans = scan_inline_spans(line, line_no)
                    matches: list[tuple[int, int]] = []
                    has_math_span = False
                    for span in spans:
                        if span.zone_type in (Zone.INLINE_MATH, Zone.DISPLAY_MATH):
                            has_math_span = True
                        elif span.zone_type == Zone.PROSE:
                            for m in CURRENCY_PATTERN.finditer(span.content):
                                col_start = span.start_col + m.start()
                                col_end = col_start + 1
                                matches.append((col_start, col_end))

                    # Trigger if 2 or more currency symbols, OR if a currency symbol coexists with math on the same line
                    if len(matches) >= 2 or (len(matches) >= 1 and has_math_span):
                        for col_start, col_end in matches:
                            edit = LintEdit(
                                rule_id=self.id,
                                start_line=line_no,
                                start_col=col_start,
                                end_line=line_no,
                                end_col=col_end,
                                replacement="\\$",
                            )
                            violations.append(
                                Violation(
                                    rule_id=self.id,
                                    message=(
                                        "Unescaped currency dollar sign triggers or interferes with LaTeX math. "
                                        "Escape as \\$."
                                    ),
                                    line=line_no,
                                    col=col_start,
                                    severity=self.severity,
                                    edit=edit,
                                )
                            )
        return violations


class RuleM11(Rule):
    """GFM-M11: LaTeX Standard Delimiters Conversion (\\[ -> $$, \\( -> $)."""

    id: str = "GFM-M11"
    name: str = "latex-delimiters-conversion"
    description: str = (
        "Convert LaTeX standard display math delimiters (\\[ ... \\]) to $$ and inline delimiters (\\( ... \\)) to $"
    )
    severity: str = "error"

    def check(self, lines: Sequence[str], zones: list[DocumentZone], file_path: str = "") -> list[Violation]:
        violations: list[Violation] = []

        # 1. Check for inline \( ... \) in PROSE zones
        for zone in zones:
            if zone.zone_type == Zone.PROSE:
                for line_idx, line in enumerate(zone.lines):
                    line_no = zone.start_line + line_idx
                    spans = scan_inline_spans(line, line_no)
                    for span in spans:
                        if span.zone_type == Zone.PROSE:
                            for m in INLINE_PAREN_MATH_RE.finditer(span.content):
                                if is_escaped(span.content, m.start()):
                                    continue
                                inner_content = m.group(1).strip()
                                col_start = span.start_col + m.start()
                                col_end = span.start_col + m.end()
                                replacement = f"${inner_content}$"
                                edit = LintEdit(
                                    rule_id=self.id,
                                    start_line=line_no,
                                    start_col=col_start,
                                    end_line=line_no,
                                    end_col=col_end,
                                    replacement=replacement,
                                )
                                violations.append(
                                    Violation(
                                        rule_id=self.id,
                                        message=(
                                            "LaTeX inline math delimiter '\\( ... \\)' is not rendered by GitHub. "
                                            "Convert to '$ ... $'."
                                        ),
                                        line=line_no,
                                        col=col_start,
                                        severity=self.severity,
                                        edit=edit,
                                    )
                                )

        # 2. Check for single-line display math \[ ... \] in PROSE zones
        for zone in zones:
            if zone.zone_type == Zone.PROSE:
                for line_idx, line in enumerate(zone.lines):
                    line_no = zone.start_line + line_idx
                    display_m = INLINE_DISPLAY_LATEX_RE.match(line)
                    if display_m:
                        leading_ws, inner, _trailing_ws = display_m.groups()
                        inner_clean = inner.strip()
                        if len(leading_ws) >= 2:
                            newline = "\n" if line.endswith("\n") else ""
                            replacement = f"{leading_ws}$${inner_clean}$${newline}"
                        else:
                            pad_above = ""
                            if line_no > 1 and lines[line_no - 2].strip() != "":
                                pad_above = "\n"

                            pad_below = ""
                            if line_no < len(lines) and lines[line_no].strip() != "":
                                pad_below = "\n"

                            replacement = f"{pad_above}$$\n{inner_clean}\n$$\n{pad_below}"
                        edit = LintEdit(
                            rule_id=self.id,
                            start_line=line_no,
                            start_col=1,
                            end_line=line_no,
                            end_col=len(line) + 1,
                            replacement=replacement,
                        )
                        violations.append(
                            Violation(
                                rule_id=self.id,
                                message=(
                                    "LaTeX display math delimiter '\\[ ... \\]' is not rendered by GitHub. "
                                    "Convert to standalone '$$'."
                                ),
                                line=line_no,
                                col=len(leading_ws) + 1,
                                severity=self.severity,
                                edit=edit,
                            )
                        )

        # 3. Check for multiline \[ ... \] blocks across lines
        prose_line_numbers = {
            line_no
            for zone in zones
            if zone.zone_type == Zone.PROSE
            for line_no in range(zone.start_line, zone.end_line + 1)
        }
        i = 0
        total = len(lines)
        while i < total:
            if (i + 1) not in prose_line_numbers:
                i += 1
                continue
            line = lines[i]
            if DISPLAY_LATEX_OPEN_RE.match(line):
                start_line_no = i + 1
                open_idx = i
                close_idx = -1
                j = i + 1
                while j < total and (j + 1) in prose_line_numbers:
                    if DISPLAY_LATEX_CLOSE_RE.match(lines[j]):
                        close_idx = j
                        break
                    j += 1

                if close_idx != -1:
                    inner_lines = lines[open_idx + 1 : close_idx]
                    inner_content = "".join(inner_lines).strip()
                    pad_above = ""
                    if open_idx > 0 and lines[open_idx - 1].strip() != "":
                        pad_above = "\n"
                    pad_below = ""
                    if close_idx + 1 < total and lines[close_idx + 1].strip() != "":
                        pad_below = "\n"

                    replacement = f"{pad_above}$$\n{inner_content}\n$$\n{pad_below}"
                    end_line_no = close_idx + 1
                    end_col = len(lines[close_idx]) + 1
                    edit = LintEdit(
                        rule_id=self.id,
                        start_line=start_line_no,
                        start_col=1,
                        end_line=end_line_no,
                        end_col=end_col,
                        replacement=replacement,
                    )
                    violations.append(
                        Violation(
                            rule_id=self.id,
                            message=(
                                "LaTeX display math block '\\[ ... \\]' is not rendered by GitHub. "
                                "Convert to standalone '$$'."
                            ),
                            line=start_line_no,
                            col=1,
                            severity=self.severity,
                            edit=edit,
                        )
                    )
                    i = close_idx + 1
                    continue
            i += 1

        return violations


class RuleM12(Rule):
    """GFM-M12: Inline Math Underscore Collision with CommonMark Emphasis."""

    id: str = "GFM-M12"
    name: str = "inline-math-underscore-collision"
    description: str = (
        "Escape flanking unescaped underscores in inline and single-line display dollar math spans "
        "to prevent CommonMark emphasis collision"
    )
    severity: str = "error"
    target: str = "dual"

    def check(self, lines: Sequence[str], zones: list[DocumentZone], file_path: str = "") -> list[Violation]:
        violations: list[Violation] = []

        def _macro_ranges(text: str) -> list[tuple[int, int]]:
            return [(start, end) for _, _, _, start, end in find_macro_calls(text, TEXT_MACROS)]

        for zone in zones:
            if zone.zone_type in (Zone.PROSE, Zone.TABLE):
                for line_idx, line in enumerate(zone.lines):
                    line_no = zone.start_line + line_idx
                    spans = scan_inline_spans(line, line_no)
                    colliding = find_colliding_math_underscores(spans, macro_ranges_fn=_macro_ranges)
                    for span, u_pos in colliding:
                        col_start = span.start_col + len(span.delimiter) + u_pos
                        col_end = col_start + 1
                        if self.target == "vscode":
                            replacement = " _ "
                            msg = (
                                "Flanking underscore in inline dollar math collides with CommonMark emphasis. "
                                "Space-pad as ' _ ' for KaTeX compatibility."
                            )
                        else:
                            replacement = "\\_"
                            msg = (
                                "Unescaped underscore in inline dollar math collides with CommonMark emphasis. "
                                "Escape as '\\_'."
                            )
                        edit = LintEdit(
                            rule_id=self.id,
                            start_line=line_no,
                            start_col=col_start,
                            end_line=line_no,
                            end_col=col_end,
                            replacement=replacement,
                        )
                        violations.append(
                            Violation(
                                rule_id=self.id,
                                message=msg,
                                line=line_no,
                                col=col_start,
                                severity=self.severity,
                                edit=edit,
                            )
                        )
        return violations


class RuleM13(Rule):
    """GFM-M13: Math Delimiter Boundary Violations."""

    id: str = "GFM-M13"
    name: str = "math-delimiter-boundaries"
    description: str = (
        "Ensure inline math delimiters satisfy GFM boundary rules (no glued units, opening delimiters, or compounds)"
    )
    severity: str = "error"

    def check(self, lines: Sequence[str], zones: list[DocumentZone], file_path: str = "") -> list[Violation]:
        violations: list[Violation] = []

        for zone in zones:
            if zone.zone_type in (Zone.PROSE, Zone.TABLE):
                for line_idx, line in enumerate(zone.lines):
                    line_no = zone.start_line + line_idx
                    spans = scan_inline_spans(line, line_no)
                    compound_span_starts: set[int] = set()

                    # 1. Check for compound math spans separated by hyphens or dashes ($A$-$B$)
                    # In GFM, an opening $ preceded by - or \u2013 is rejected as a delimiter.
                    k = 0
                    while k < len(spans) - 2:
                        s1 = spans[k]
                        s2 = spans[k + 1]
                        s3 = spans[k + 2]
                        if (
                            s1.zone_type == Zone.INLINE_MATH
                            and s1.delimiter == "$"
                            and s2.zone_type == Zone.PROSE
                            and s2.raw in ("-", "\u2013", "\u2014")
                            and s3.zone_type == Zone.INLINE_MATH
                            and s3.delimiter == "$"
                        ):
                            dash_char = s2.raw
                            replacement = f"${s1.content}\\text{{{dash_char}}}{s3.content}$"
                            compound_span_starts.add(s3.start_col)
                            edit = LintEdit(
                                rule_id=self.id,
                                start_line=line_no,
                                start_col=s1.start_col,
                                end_line=line_no,
                                end_col=s3.end_col,
                                replacement=replacement,
                            )
                            violations.append(
                                Violation(
                                    rule_id=self.id,
                                    message=(
                                        f"Compound math expression '{s1.raw}{dash_char}{s3.raw}' "
                                        f"violates GFM opening delimiter rules. "
                                        f"Combine into a single math span: '{replacement}'."
                                    ),
                                    line=line_no,
                                    col=s1.start_col,
                                    severity=self.severity,
                                    edit=edit,
                                )
                            )
                            k += 3
                            continue
                        k += 1

                    # 2. Check for closing $ glued to an alphanumeric character ($15\ ^\circ$C or $0.759$dB)
                    # In GFM, a closing $ immediately followed by a letter or digit is rejected as a closing delimiter.
                    for span in spans:
                        if span.zone_type == Zone.INLINE_MATH and span.delimiter == "$":
                            end_idx = span.end_col - 1
                            if end_idx < len(line) and line[end_idx].isalnum():
                                glued_m = re.match(r"[a-zA-Z0-9]+", line[end_idx:])
                                if glued_m:
                                    glued_word = glued_m.group(0)
                                    col_start = span.start_col
                                    col_end = span.end_col + len(glued_word)
                                    replacement = f"{span.raw} {glued_word}"
                                    edit = LintEdit(
                                        rule_id=self.id,
                                        start_line=line_no,
                                        start_col=col_start,
                                        end_line=line_no,
                                        end_col=col_end,
                                        replacement=replacement,
                                    )
                                    violations.append(
                                        Violation(
                                            rule_id=self.id,
                                            message=(
                                                f"Closing math delimiter '$' is glued to alphanumeric '{glued_word}', "
                                                f"causing GitHub to reject the delimiter. "
                                                f"Separate with space: '{replacement}'."
                                            ),
                                            line=line_no,
                                            col=col_start,
                                            severity=self.severity,
                                            edit=edit,
                                        )
                                    )

                    # 3. Check for closing $ immediately followed by ')' when math contains ')'
                    # In GFM, $(...) ... math(...)$) causes bracket pairing collision that breaks math rendering.
                    for span in spans:
                        if span.zone_type == Zone.INLINE_MATH and span.delimiter == "$":
                            end_idx = span.end_col - 1
                            if end_idx < len(line) and line[end_idx] == ")" and ")" in span.content:
                                col_start = span.start_col
                                col_end = span.end_col + 1  # include the trailing ')'
                                replacement = f"{span.raw} )"
                                edit = LintEdit(
                                    rule_id=self.id,
                                    start_line=line_no,
                                    start_col=col_start,
                                    end_line=line_no,
                                    end_col=col_end,
                                    replacement=replacement,
                                )
                                violations.append(
                                    Violation(
                                        rule_id=self.id,
                                        message=(
                                            f"Closing math delimiter '$' followed immediately by ')' collides with "
                                            f"parentheses inside math '{span.raw}'. "
                                            f"Separate with space: '{replacement}'."
                                        ),
                                        line=line_no,
                                        col=col_start,
                                        severity=self.severity,
                                        edit=edit,
                                    )
                                )

                    # 4. Check for opening $ glued to preceding '-', en-dash, em-dash, '/', or alphanumeric (REG-12)
                    for span in spans:
                        if (
                            span.zone_type == Zone.INLINE_MATH
                            and span.delimiter == "$"
                            and span.start_col not in compound_span_starts
                        ):
                            open_idx = span.start_col - 1
                            if open_idx > 0:
                                prev_ch = line[open_idx - 1]
                                if prev_ch in ("-", "\u2013", "\u2014"):
                                    if open_idx >= 2 and line[open_idx - 2].isalnum():
                                        edit = LintEdit(
                                            rule_id=self.id,
                                            start_line=line_no,
                                            start_col=open_idx,
                                            end_line=line_no,
                                            end_col=open_idx + 1,
                                            replacement=" ",
                                        )
                                    else:
                                        edit = LintEdit(
                                            rule_id=self.id,
                                            start_line=line_no,
                                            start_col=open_idx + 1,
                                            end_line=line_no,
                                            end_col=open_idx + 1,
                                            replacement=" ",
                                        )
                                    violations.append(
                                        Violation(
                                            rule_id=self.id,
                                            message=(
                                                f"Opening math delimiter '$' is glued to '{prev_ch}', "
                                                "causing GitHub to reject the math span."
                                            ),
                                            line=line_no,
                                            col=span.start_col,
                                            severity=self.severity,
                                            edit=edit,
                                        )
                                    )
                                elif prev_ch == "/" or prev_ch.isalnum():
                                    edit = LintEdit(
                                        rule_id=self.id,
                                        start_line=line_no,
                                        start_col=open_idx + 1,
                                        end_line=line_no,
                                        end_col=open_idx + 1,
                                        replacement=" ",
                                    )
                                    violations.append(
                                        Violation(
                                            rule_id=self.id,
                                            message=(
                                                f"Opening math delimiter '$' is glued to '{prev_ch}', "
                                                "causing GitHub to reject the math span."
                                            ),
                                            line=line_no,
                                            col=span.start_col,
                                            severity=self.severity,
                                            edit=edit,
                                        )
                                    )

        return violations


class RuleM14(Rule):
    """GFM-M14: Code Syntax and Identifiers Inside Math Delimiters (Issue #6 & REG-04)."""

    id: str = "GFM-M14"
    name: str = "code-syntax-in-math"
    description: str = "Convert code function identities and flag snake_case code identifiers inside math delimiters"
    severity: str = "warning"

    _FUNC_CALL_RE = re.compile(r"\\(?:text|mathrm)\{([a-zA-Z_][a-zA-Z0-9_]*)\}\s*\(")
    _CODE_MATH_COMPARISON_RE = re.compile(r"(?:\\equiv|==|!=|\\neq)")
    _GENUINE_MATH_RE = re.compile(r"(?:\\frac|\\int|\\sum|\\prod|\\lim|\\sqrt|\\mid|\\lvert|\^)")
    _SNAKE_CASE_IDENT_RE = re.compile(r"[a-zA-Z0-9]+(?:\\{0,2}_[a-zA-Z0-9]+)+|\\{0,2}_[a-zA-Z0-9]+")

    def check(self, lines: Sequence[str], zones: list[DocumentZone], file_path: str = "") -> list[Violation]:
        violations: list[Violation] = []

        # Sub-pattern B in DISPLAY_MATH zones
        for zone in zones:
            if zone.zone_type == Zone.DISPLAY_MATH and zone.is_closed:
                for line_idx, line in enumerate(zone.lines):
                    line_no = zone.start_line + line_idx
                    if DISPLAY_MATH_LINE_RE.match(line):
                        continue
                    for _, _, inner_text, inner_start, _ in find_macro_calls(line, TEXT_MACROS):
                        if self._SNAKE_CASE_IDENT_RE.search(inner_text):
                            col_start = inner_start + 1
                            violations.append(
                                Violation(
                                    rule_id=self.id,
                                    message=(
                                        f"Code or register identifier '{inner_text}' inside math mode "
                                        "should use inline code backticks or non-underscore notation."
                                    ),
                                    line=line_no,
                                    col=col_start,
                                    severity=self.severity,
                                    edit=None,
                                )
                            )

        # Sub-patterns A & B in PROSE / TABLE inline and single-line display math
        for zone in zones:
            if zone.zone_type not in (Zone.PROSE, Zone.TABLE):
                continue
            for line_idx, line in enumerate(zone.lines):
                line_no = zone.start_line + line_idx
                for span in scan_inline_spans(line, line_no):
                    if span.zone_type not in (Zone.INLINE_MATH, Zone.DISPLAY_MATH):
                        continue
                    if span.delimiter not in ("$", "$`", "$$"):
                        continue

                    # Sub-pattern A: Pseudo-code function identities in inline $...$
                    if (
                        span.zone_type == Zone.INLINE_MATH
                        and span.delimiter == "$"
                        and self._CODE_MATH_COMPARISON_RE.search(span.content)
                        and not self._GENUINE_MATH_RE.search(span.content)
                    ):
                        m_fn = self._FUNC_CALL_RE.search(span.content)
                        if m_fn and m_fn.group(1).lower() not in STANDARD_MATH_FUNCTIONS:
                            clean_expr = re.sub(r"\\(?:text|mathrm)\{([^{}]+)\}", r"\1", span.content)
                            clean_expr = (
                                clean_expr.replace(r"\equiv", "==")
                                .replace(r"\neq", "!=")
                                .replace(r"\le", "<=")
                                .replace(r"\ge", ">=")
                                .strip()
                            )
                            replacement = f"`{clean_expr}`"
                            edit = LintEdit(
                                rule_id=self.id,
                                start_line=line_no,
                                start_col=span.start_col,
                                end_line=line_no,
                                end_col=span.end_col,
                                replacement=replacement,
                            )
                            violations.append(
                                Violation(
                                    rule_id=self.id,
                                    message=(
                                        f"Code function identity '{span.raw}' wrapped in LaTeX math delimiters. "
                                        f"Use inline code backticks '{replacement}' to avoid MathML stacking artifacts."
                                    ),
                                    line=line_no,
                                    col=span.start_col,
                                    severity=self.severity,
                                    edit=edit,
                                )
                            )
                            continue

                    # Sub-pattern B: snake_case identifiers in \text{...} / \mathrm{...}
                    standalone_m = (
                        re.fullmatch(
                            r"\s*\\(?:text|mathrm|mathbf)\{([a-zA-Z0-9_\\-]+)\}\s*",
                            span.content,
                        )
                        if span.zone_type == Zone.INLINE_MATH
                        else None
                    )
                    if standalone_m and self._SNAKE_CASE_IDENT_RE.search(standalone_m.group(1)):
                        ident = standalone_m.group(1).replace(r"\\_", "_").replace(r"\_", "_")
                        replacement = f"`{ident}`"
                        edit = LintEdit(
                            rule_id=self.id,
                            start_line=line_no,
                            start_col=span.start_col,
                            end_line=line_no,
                            end_col=span.end_col,
                            replacement=replacement,
                        )
                        violations.append(
                            Violation(
                                rule_id=self.id,
                                message=(
                                    f"Code identifier '{span.raw}' wrapped in LaTeX math delimiters. "
                                    f"Use inline code backticks '{replacement}'."
                                ),
                                line=line_no,
                                col=span.start_col,
                                severity=self.severity,
                                edit=edit,
                            )
                        )
                        continue

                    for _, _, inner_text, inner_start, _ in find_macro_calls(span.content, TEXT_MACROS):
                        if self._SNAKE_CASE_IDENT_RE.search(inner_text):
                            col_start = span.start_col + len(span.delimiter) + inner_start
                            violations.append(
                                Violation(
                                    rule_id=self.id,
                                    message=(
                                        f"Code or register identifier '{inner_text}' inside math mode "
                                        "should use inline code backticks or non-underscore notation."
                                    ),
                                    line=line_no,
                                    col=col_start,
                                    severity=self.severity,
                                    edit=None,
                                )
                            )

        return violations


class RuleM15(Rule):
    """GFM-M15: Cross-Engine LaTeX Compatibility (dashes, unescaped/single-escaped %, pipe hazards)."""

    id: str = "GFM-M15"
    name: str = "cross-engine-latex-compat"
    description: str = "Flag Unicode dashes, bare or single-escaped % comments, and pipe entities in math expressions"
    severity: str = "error"

    _UNICODE_DASH_RE = re.compile(r"[\u2013\u2014]")
    _PIPE_ENTITY_RE = re.compile(r"(?:&#124;|&#x7c;|&verbar;|&vert;)", re.IGNORECASE)
    _BARE_OR_SINGLE_PERCENT_RE = re.compile(r"(?:(?<!\\)\\%|(?<!\\)%)")
    _BARE_PERCENT_RE = re.compile(r"(?<!\\)%")

    def check(self, lines: Sequence[str], zones: list[DocumentZone], file_path: str = "") -> list[Violation]:
        violations: list[Violation] = []

        def _check_unicode_dashes(text: str, line_no: int, base_col: int) -> None:
            macro_ranges = [(s, e) for _, _, _, s, e in find_macro_calls(text, TEXT_MACROS)]
            for m in self._UNICODE_DASH_RE.finditer(text):
                if any(s <= m.start() < e for s, e in macro_ranges):
                    continue
                col_start = base_col + m.start()
                edit = LintEdit(
                    rule_id=self.id,
                    start_line=line_no,
                    start_col=col_start,
                    end_line=line_no,
                    end_col=col_start + 1,
                    replacement="-",
                )
                violations.append(
                    Violation(
                        rule_id=self.id,
                        message="Unicode en-dash/em-dash inside math mode crashes KaTeX; use ASCII '-'.",
                        line=line_no,
                        col=col_start,
                        severity=self.severity,
                        edit=edit,
                    )
                )

        # 1. DISPLAY_MATH blocks
        for zone in zones:
            if zone.zone_type != Zone.DISPLAY_MATH or not zone.is_closed:
                continue
            for line_idx, line in enumerate(zone.lines):
                line_no = zone.start_line + line_idx
                if DISPLAY_MATH_LINE_RE.match(line):
                    continue
                _check_unicode_dashes(line, line_no, base_col=1)
                for m in self._BARE_OR_SINGLE_PERCENT_RE.finditer(line):
                    if is_escaped(line, m.start()) and line[m.start()] == "\\":
                        continue
                    col_start = m.start() + 1
                    violations.append(
                        Violation(
                            rule_id=self.id,
                            message=(
                                "Unescaped '%' or single-escaped '\\%' in display math acts as a TeX line comment "
                                "after CommonMark unescaping. Move '%' outside math or double-escape."
                            ),
                            line=line_no,
                            col=col_start,
                            severity=self.severity,
                            edit=None,
                        )
                    )
                for m in self._PIPE_ENTITY_RE.finditer(line):
                    col_start = m.start() + 1
                    violations.append(
                        Violation(
                            rule_id=self.id,
                            message=(
                                "HTML pipe entity inside display math is not decoded by MathJax/KaTeX; "
                                "use '\\lvert', '\\rvert', or '\\vert'."
                            ),
                            line=line_no,
                            col=col_start,
                            severity=self.severity,
                            edit=LintEdit(
                                rule_id=self.id,
                                start_line=line_no,
                                start_col=col_start,
                                end_line=line_no,
                                end_col=m.end() + 1,
                                replacement="\\vert",
                            ),
                        )
                    )

        # 2. Inline and single-line display math in PROSE and TABLE zones
        for zone in zones:
            if zone.zone_type not in (Zone.PROSE, Zone.TABLE):
                continue
            in_table = zone.zone_type == Zone.TABLE
            for line_idx, line in enumerate(zone.lines):
                line_no = zone.start_line + line_idx
                for span in scan_inline_spans(line, line_no):
                    if span.zone_type not in (Zone.INLINE_MATH, Zone.DISPLAY_MATH):
                        continue
                    if span.delimiter not in ("$", "$`", "$$"):
                        continue

                    base_col = span.start_col + len(span.delimiter)
                    _check_unicode_dashes(span.content, line_no, base_col=base_col)

                    # Table math HTML pipe entity compatibility notice (edit handled by GFM-T01)
                    if in_table and self._PIPE_ENTITY_RE.search(span.content):
                        violations.append(
                            Violation(
                                rule_id=self.id,
                                message=(
                                    "HTML pipe entity inside table math breaks GitHub MathJax; "
                                    "use '\\lvert ... \\rvert', '\\lVert ... \\rVert', or '\\vert'."
                                ),
                                line=line_no,
                                col=span.start_col,
                                severity=self.severity,
                                edit=None,
                            )
                        )
                    elif not in_table and self._PIPE_ENTITY_RE.search(span.content):
                        for m in self._PIPE_ENTITY_RE.finditer(span.content):
                            col_start = base_col + m.start()
                            violations.append(
                                Violation(
                                    rule_id=self.id,
                                    message=(
                                        "HTML pipe entity inside math is not decoded by MathJax/KaTeX; "
                                        "use '\\lvert', '\\rvert', or '\\vert'."
                                    ),
                                    line=line_no,
                                    col=col_start,
                                    severity=self.severity,
                                    edit=LintEdit(
                                        rule_id=self.id,
                                        start_line=line_no,
                                        start_col=col_start,
                                        end_line=line_no,
                                        end_col=base_col + m.end(),
                                        replacement="\\vert",
                                    ),
                                )
                            )

                    # Bare % or single-escaped \% in math (Issue #22 Bug 2 & syn_128)
                    if span.delimiter == "$`":
                        for m in self._BARE_PERCENT_RE.finditer(span.content):
                            col_start = base_col + m.start()
                            violations.append(
                                Violation(
                                    rule_id=self.id,
                                    message=(
                                        "Unescaped '%' inside backtick math acts as a TeX comment; escape as '\\%'."
                                    ),
                                    line=line_no,
                                    col=col_start,
                                    severity=self.severity,
                                    edit=LintEdit(
                                        rule_id=self.id,
                                        start_line=line_no,
                                        start_col=col_start,
                                        end_line=line_no,
                                        end_col=col_start + 1,
                                        replacement="\\%",
                                    ),
                                )
                            )
                    else:
                        has_percent_hazard = False
                        for m in self._BARE_OR_SINGLE_PERCENT_RE.finditer(span.content):
                            if span.content[m.start()] == "\\" and is_escaped(span.content, m.start()):
                                continue
                            has_percent_hazard = True
                            break
                        if has_percent_hazard:
                            if span.delimiter == "$":
                                fixed_inner = self._BARE_PERCENT_RE.sub(lambda _: r"\%", span.content)
                                replacement = f"$`{fixed_inner}`$"
                                edit: LintEdit | None = LintEdit(
                                    rule_id=self.id,
                                    start_line=line_no,
                                    start_col=span.start_col,
                                    end_line=line_no,
                                    end_col=span.end_col,
                                    replacement=replacement,
                                )
                                msg = (
                                    "Unescaped '%' or single-escaped '\\%' in inline dollar math is stripped to a TeX "
                                    "comment on GitHub. Wrap in GFM backtick math ($`...\\%...`$) or move '%' outside."
                                )
                            else:
                                edit = None
                                msg = (
                                    "Unescaped '%' or single-escaped '\\%' in display math is stripped to a TeX "
                                    "comment on GitHub. Move '%' outside math."
                                )
                            violations.append(
                                Violation(
                                    rule_id=self.id,
                                    message=msg,
                                    line=line_no,
                                    col=span.start_col,
                                    severity=self.severity,
                                    edit=edit,
                                )
                            )

        return violations


class RuleM16(Rule):
    """GFM-M16: Display Math EOL-Only Line Breaks (REG-09)."""

    id: str = "GFM-M16"
    name: str = "display-linebreak-eol"
    description: str = "Ensure \\\\ row breaks inside $$ ... $$ display math sit at the end of a line"
    severity: str = "error"

    _MIDLINE_BREAK_RE = re.compile(r"(?<!\\)\\\\(?![a-zA-Z\\])([ \t]*)(\S)")

    def check(self, lines: Sequence[str], zones: list[DocumentZone], file_path: str = "") -> list[Violation]:
        violations: list[Violation] = []

        for zone in zones:
            if zone.zone_type != Zone.DISPLAY_MATH or not zone.is_closed:
                continue
            for line_idx, line in enumerate(zone.lines):
                line_no = zone.start_line + line_idx
                if DISPLAY_MATH_LINE_RE.match(line):
                    continue
                macro_ranges = [(s, e) for _, _, _, s, e in find_macro_calls(line, TEXT_MACROS)]
                indent_prefix = ""
                m_ws = re.match(r"^(\s*(?:>\s*)*)", line)
                if m_ws:
                    indent_prefix = m_ws.group(1)
                for m in self._MIDLINE_BREAK_RE.finditer(line):
                    if any(s <= m.start() < e for s, e in macro_ranges):
                        continue
                    col_start = m.start() + 1
                    col_end = m.start() + 2 + len(m.group(1)) + 1
                    edit = LintEdit(
                        rule_id=self.id,
                        start_line=line_no,
                        start_col=col_start,
                        end_line=line_no,
                        end_col=col_end,
                        replacement=f"\\\\\n{indent_prefix}",
                    )
                    violations.append(
                        Violation(
                            rule_id=self.id,
                            message=(
                                "Mid-line '\\\\' inside display math collapses to '\\' on GitHub; "
                                "place a line break immediately after '\\\\'."
                            ),
                            line=line_no,
                            col=col_start,
                            severity=self.severity,
                            edit=edit,
                        )
                    )
        return violations


class RuleM17(Rule):
    """GFM-M17: Display Math Markdown Block Interruption (REG-10, REG-11)."""

    id: str = "GFM-M17"
    name: str = "display-line-block-start"
    description: str = "Prevent display math interior lines from opening CommonMark lists, headings, or blockquotes"
    severity: str = "error"

    _PM_START_RE = re.compile(r"^(\s{0,3})([+-])(\s+)")

    def check(self, lines: Sequence[str], zones: list[DocumentZone], file_path: str = "") -> list[Violation]:
        violations: list[Violation] = []

        for zone in zones:
            if zone.zone_type != Zone.DISPLAY_MATH or not zone.is_closed or len(zone.lines) < 3:
                continue
            for rel_idx, inner_line in enumerate(zone.lines[1:-1]):
                line_no = zone.start_line + 1 + rel_idx
                # Strip blockquote prefix if inside a blockquote
                check_line = (
                    re.sub(r"^\s*(?:>\s*)+", "", inner_line) if zone.parent_block == "blockquote" else inner_line
                )
                if not BLOCK_INTERRUPT_RE.match(check_line):
                    continue

                m_pm = self._PM_START_RE.match(inner_line)
                if m_pm:
                    ws, op, sp = m_pm.groups()
                    col_start = len(ws) + 1
                    col_end = col_start + len(op) + len(sp)
                    edit: LintEdit | None = LintEdit(
                        rule_id=self.id,
                        start_line=line_no,
                        start_col=col_start,
                        end_line=line_no,
                        end_col=col_end,
                        replacement=f"{{}}{op}{sp}",
                    )
                    msg = (
                        f"Line starting with '{op} ' inside display math opens a Markdown bullet list on GitHub. "
                        f"Prefix with '{{}}{op}' or move operator to end of preceding line."
                    )
                else:
                    edit = None
                    msg = (
                        "Line inside display math matches a CommonMark block construct (setext underline, heading, "
                        "ordered list, or blockquote) and fractures the equation on GitHub."
                    )
                violations.append(
                    Violation(
                        rule_id=self.id,
                        message=msg,
                        line=line_no,
                        col=1,
                        severity=self.severity,
                        edit=edit,
                    )
                )
        return violations


class RuleM18(Rule):
    """GFM-M18: Non-ASCII Scientific Glyphs in Math Mode (REG-15)."""

    id: str = "GFM-M18"
    name: str = "non-ascii-in-math"
    description: str = "Convert non-ASCII symbols inside math delimiters to portable LaTeX macros"
    severity: str = "warning"

    _TEXT_MICRO_RE = re.compile(r"\\text\{[µμ]([a-zA-Z]+)\}")
    _GLYPH_MAP: ClassVar[dict[str, str]] = {
        "\u00b5": "\\mu",  # micro sign
        "\u03bc": "\\mu",  # Greek small letter mu
        "\u00b0": "^\\circ",
        "\u00b2": "^2",
        "\u00b3": "^3",
        "\u00b7": "\\cdot",
        "\u2212": "-",
        "\u00d7": "\\times",
        "\u00b1": "\\pm",
        "\u2264": "\\le",
        "\u2265": "\\ge",
        "\u2260": "\\neq",
        "\u221e": "\\infty",
        "\u03b1": "\\alpha",
        "\u03b2": "\\beta",
        "\u03b3": "\\gamma",
        "\u03b4": "\\delta",
        "\u03b5": "\\epsilon",
        "\u03b8": "\\theta",
        "\u03bb": "\\lambda",
        "\u03c0": "\\pi",
        "\u03c3": "\\sigma",
        "\u03c4": "\\tau",
        "\u03c6": "\\phi",
        "\u03c9": "\\omega",
        "\u0394": "\\Delta",
        "\u03a3": "\\Sigma",
        "\u03a9": "\\Omega",
    }
    _GLYPH_RE = re.compile("[" + "".join(_GLYPH_MAP.keys()) + "]")

    def check(self, lines: Sequence[str], zones: list[DocumentZone], file_path: str = "") -> list[Violation]:
        violations: list[Violation] = []

        def _scan_text(text: str, line_no: int, base_col: int) -> None:
            handled_ranges: list[tuple[int, int]] = []
            for m in self._TEXT_MICRO_RE.finditer(text):
                handled_ranges.append((m.start(), m.end()))
                col_start = base_col + m.start()
                col_end = base_col + m.end()
                replacement = f"\\mu\\text{{{m.group(1)}}}"
                violations.append(
                    Violation(
                        rule_id=self.id,
                        message=(
                            f"Non-ASCII micro symbol in '{m.group(0)}' triggers KaTeX strict warnings; "
                            f"use '{replacement}'."
                        ),
                        line=line_no,
                        col=col_start,
                        severity=self.severity,
                        edit=LintEdit(
                            rule_id=self.id,
                            start_line=line_no,
                            start_col=col_start,
                            end_line=line_no,
                            end_col=col_end,
                            replacement=replacement,
                        ),
                    )
                )

            for m in self._GLYPH_RE.finditer(text):
                if any(s <= m.start() < e for s, e in handled_ranges):
                    continue
                ch = m.group(0)
                macro = self._GLYPH_MAP[ch]
                if macro.startswith("\\") and macro[-1].isalpha() and m.end() < len(text) and text[m.end()].isalpha():
                    macro = macro + " "
                col_start = base_col + m.start()
                violations.append(
                    Violation(
                        rule_id=self.id,
                        message=(
                            f"Non-ASCII symbol '{ch}' inside math mode triggers KaTeX strict warnings; "
                            f"use '{macro.strip()}'."
                        ),
                        line=line_no,
                        col=col_start,
                        severity=self.severity,
                        edit=LintEdit(
                            rule_id=self.id,
                            start_line=line_no,
                            start_col=col_start,
                            end_line=line_no,
                            end_col=col_start + 1,
                            replacement=macro,
                        ),
                    )
                )

        for zone in zones:
            if zone.zone_type == Zone.DISPLAY_MATH and zone.is_closed:
                for line_idx, line in enumerate(zone.lines):
                    line_no = zone.start_line + line_idx
                    if not DISPLAY_MATH_LINE_RE.match(line):
                        _scan_text(line, line_no, base_col=1)
            elif zone.zone_type in (Zone.PROSE, Zone.TABLE):
                for line_idx, line in enumerate(zone.lines):
                    line_no = zone.start_line + line_idx
                    for span in scan_inline_spans(line, line_no):
                        if span.zone_type in (Zone.INLINE_MATH, Zone.DISPLAY_MATH) and span.delimiter in (
                            "$",
                            "$`",
                            "$$",
                        ):
                            _scan_text(span.content, line_no, base_col=span.start_col + len(span.delimiter))

        return violations
