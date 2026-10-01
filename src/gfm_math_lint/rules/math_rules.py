"""GFM MathJax and KaTeX parsing rules (GFM-M01 through GFM-M13)."""

from __future__ import annotations

import re

from gfm_math_lint.fixer import LintEdit
from gfm_math_lint.rules.base import Rule, Violation
from gfm_math_lint.tokenizer import (
    DISPLAY_MATH_LINE_RE,
    DocumentZone,
    Zone,
    is_escaped,
    scan_inline_spans,
)

# Helper for parsing LaTeX macros with balanced braces
TEXT_MACROS = ("text", "mathrm", "mathbf", "operatorname")

INLINE_DISPLAY_MATH_RE = re.compile(r"^(\s*)\$\$(.+?)\$\$(\s*)$")
TEXT_UNDERSCORE_RE = re.compile(r"(?<!\\)(?:(\\_)|(_))")

LEFT_LBRACE_PATTERNS = [
    (re.compile(r"\\left\\\{"), "\\left\\lbrace", "Replace \\left\\{ with \\left\\lbrace"),
    (re.compile(r"\\right\\\}"), "\\right\\rbrace", "Replace \\right\\} with \\right\\rbrace"),
    (re.compile(r"(?<!\\)(?<!\\left)\\\{"), "\\lbrace", "Replace \\{ with \\lbrace"),
    (re.compile(r"(?<!\\)(?<!\\right)\\\}"), "\\rbrace", "Replace \\} with \\rbrace"),
]

RELATIONAL_LT_RE = re.compile(r"<([a-zA-Z])")

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
    description: str = "Convert ```math code fences to standalone $$ ... $$ block math"
    severity: str = "error"

    def check(self, lines: list[str], zones: list[DocumentZone], file_path: str = "") -> list[Violation]:
        violations: list[Violation] = []
        for zone in zones:
            if zone.zone_type == Zone.FENCED_CODE and zone.info.strip().lower() == "math":
                start_line = zone.start_line
                end_line = zone.end_line
                # Extract inner lines
                inner_lines = zone.lines[1:-1] if zone.is_closed and len(zone.lines) >= 2 else zone.lines[1:]
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


class RuleM02(Rule):
    """GFM-M02: Block Math Boundary Isolation & Padding."""

    id: str = "GFM-M02"
    name: str = "display-math-isolation"
    description: str = (
        "Enforce display math $$ isolation on own lines with blank line padding and no internal blank lines"
    )
    severity: str = "error"

    def check(self, lines: list[str], zones: list[DocumentZone], file_path: str = "") -> list[Violation]:
        violations: list[Violation] = []

        # 1. Check PROSE zones for inline display math ($$...$$) on a single line
        for zone in zones:
            if zone.zone_type == Zone.PROSE:
                for line_idx, line in enumerate(zone.lines):
                    curr_line_no = zone.start_line + line_idx
                    m = INLINE_DISPLAY_MATH_RE.match(line)
                    if m:
                        leading_ws, inner, _trailing_ws = m.groups()
                        # Indented display math on a single line inside list items or blockquotes
                        # (e.g. 2+ spaces of leading whitespace) must be preserved as-is.
                        # Breaking it into unindented block math with surrounding blank lines
                        # closes the list environment and turns subsequent list items into
                        # CommonMark §4.4 indented code blocks (<pre><code>).
                        if len(leading_ws) >= 2:
                            continue

                        pad_above = ""
                        if curr_line_no > 1 and lines[curr_line_no - 2].strip() != "":
                            pad_above = "\n"

                        pad_below = ""
                        if curr_line_no < len(lines) and lines[curr_line_no].strip() != "":
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
                        violations.append(
                            Violation(
                                rule_id=self.id,
                                message="Display math ($$) must sit on isolated lines with blank line padding.",
                                line=curr_line_no,
                                col=len(leading_ws) + 1,
                                severity=self.severity,
                                edit=edit,
                            )
                        )

        # 2. Check DISPLAY_MATH zones for blank line padding above/below and internal blank lines
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

            has_internal_blanks = False
            cleaned_inner_lines: list[str] = []
            if len(zone.lines) > 2:
                for inner_idx, inner_line in enumerate(zone.lines[1:-1]):
                    actual_line_no = zone.start_line + 1 + inner_idx
                    if inner_line.strip() == "":
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
                        cleaned_inner_lines.append(inner_line)
            else:
                cleaned_inner_lines = zone.lines[1:-1] if len(zone.lines) > 1 else []

            # Check padding above
            need_pad_above = False
            if zone.start_line > 1:
                line_above = lines[zone.start_line - 2].strip()
                if line_above != "" and line_above != "---":
                    need_pad_above = True

            # Check padding below
            need_pad_below = False
            if zone.end_line < len(lines):
                line_below = lines[zone.end_line].strip()
                if line_below != "" and line_below != "---":
                    need_pad_below = True

            if need_pad_above or need_pad_below:
                msg = []
                if need_pad_above:
                    msg.append("above")
                if need_pad_below:
                    msg.append("below")
                violations.append(
                    Violation(
                        rule_id=self.id,
                        message=f"Display math block must be padded with a blank line {' and '.join(msg)}.",
                        line=zone.start_line,
                        col=1,
                        severity=self.severity,
                    )
                )

            # If there are internal blanks or missing padding, synthesize ONE unified edit for this block
            if has_internal_blanks or need_pad_above or need_pad_below:
                pad_above = "\n" if need_pad_above else ""
                pad_below = "\n" if need_pad_below else ""
                opening = zone.lines[0]
                if not opening.endswith("\n"):
                    opening += "\n"
                closing = zone.lines[-1] if len(zone.lines) > 1 else "$$\n"
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
                # Attach this edit to the first violation for this zone that doesn't have one
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
    """GFM-M03: Text Mode Underscore Double-Escaping."""

    id: str = "GFM-M03"
    name: str = "text-mode-underscore-escape"
    description: str = "Double-escape underscores inside text mode macros (\\text{ave\\\\_shift})"
    severity: str = "error"

    def check(self, lines: list[str], zones: list[DocumentZone], file_path: str = "") -> list[Violation]:
        violations: list[Violation] = []

        # Check DISPLAY_MATH zones
        for zone in zones:
            if zone.zone_type == Zone.DISPLAY_MATH:
                if not zone.is_closed:
                    continue
                for line_idx, line in enumerate(zone.lines):
                    line_no = zone.start_line + line_idx
                    macro_calls = find_macro_calls(line, TEXT_MACROS)
                    for _, _, inner_text, inner_start, _ in macro_calls:
                        for m in TEXT_UNDERSCORE_RE.finditer(inner_text):
                            col_start = inner_start + m.start() + 1
                            col_end = inner_start + m.end() + 1
                            edit = LintEdit(
                                rule_id=self.id,
                                start_line=line_no,
                                start_col=col_start,
                                end_line=line_no,
                                end_col=col_end,
                                replacement="\\\\_",
                            )
                            violations.append(
                                Violation(
                                    rule_id=self.id,
                                    message="Underscore in text-mode LaTeX macro must be double-escaped (\\\\_).",
                                    line=line_no,
                                    col=col_start,
                                    severity=self.severity,
                                    edit=edit,
                                )
                            )

        # Check INLINE_MATH spans in PROSE and TABLE zones
        for zone in zones:
            if zone.zone_type in (Zone.PROSE, Zone.TABLE):
                for line_idx, line in enumerate(zone.lines):
                    line_no = zone.start_line + line_idx
                    spans = scan_inline_spans(line, line_no)
                    for span in spans:
                        # Backtick math ($`...`$) is immune to backslash stripping
                        if span.zone_type == Zone.INLINE_MATH and span.delimiter == "$":
                            macro_calls = find_macro_calls(span.content, TEXT_MACROS)
                            for _, _, inner_text, inner_start, _ in macro_calls:
                                for m in TEXT_UNDERSCORE_RE.finditer(inner_text):
                                    col_start = span.start_col + len(span.delimiter) + inner_start + m.start()
                                    col_end = span.start_col + len(span.delimiter) + inner_start + m.end()
                                    edit = LintEdit(
                                        rule_id=self.id,
                                        start_line=line_no,
                                        start_col=col_start,
                                        end_line=line_no,
                                        end_col=col_end,
                                        replacement="\\\\_",
                                    )
                                    violations.append(
                                        Violation(
                                            rule_id=self.id,
                                            message=(
                                                "Underscore in text-mode LaTeX macro must be double-escaped (\\\\_)."
                                            ),
                                            line=line_no,
                                            col=col_start,
                                            severity=self.severity,
                                            edit=edit,
                                        )
                                    )
        return violations


class RuleM04(Rule):
    """GFM-M04: Inline Math Whitespace Stripping."""

    id: str = "GFM-M04"
    name: str = "inline-math-whitespace"
    description: str = "Strip leading and trailing inner whitespace from inline math delimiters ($x$)"
    severity: str = "error"

    def check(self, lines: list[str], zones: list[DocumentZone], file_path: str = "") -> list[Violation]:
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
    """GFM-M05: Curly Brace Escape Conversion (\\left\\{ -> \\left\\lbrace)."""

    id: str = "GFM-M05"
    name: str = "curly-brace-escape"
    description: str = "Convert \\{ and \\} delimiters in math expressions to \\lbrace and \\rbrace"
    severity: str = "error"

    def check(self, lines: list[str], zones: list[DocumentZone], file_path: str = "") -> list[Violation]:
        violations: list[Violation] = []

        def check_text(text: str, line_no: int, base_col: int) -> None:
            for pattern, repl, desc in LEFT_LBRACE_PATTERNS:
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

        # 2. INLINE_MATH and single-line DISPLAY_MATH in PROSE/TABLE
        for zone in zones:
            if zone.zone_type in (Zone.PROSE, Zone.TABLE):
                for line_idx, line in enumerate(zone.lines):
                    line_no = zone.start_line + line_idx
                    spans = scan_inline_spans(line, line_no)
                    for span in spans:
                        if span.zone_type in (Zone.INLINE_MATH, Zone.DISPLAY_MATH):
                            check_text(span.content, line_no, base_col=span.start_col + len(span.delimiter))

        return violations


class RuleM06(Rule):
    """GFM-M06: HTML Relational Operator Tag Collision (<i -> \\lt i)."""

    id: str = "GFM-M06"
    name: str = "relational-operator-collision"
    description: str = "Replace < before letters with \\lt to prevent HTML tag collisions"
    severity: str = "error"

    def check(self, lines: list[str], zones: list[DocumentZone], file_path: str = "") -> list[Violation]:
        violations: list[Violation] = []

        def check_text(text: str, line_no: int, base_col: int) -> None:
            for m in RELATIONAL_LT_RE.finditer(text):
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

    def check(self, lines: list[str], zones: list[DocumentZone], file_path: str = "") -> list[Violation]:
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

    def check(self, lines: list[str], zones: list[DocumentZone], file_path: str = "") -> list[Violation]:
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

    def check(self, lines: list[str], zones: list[DocumentZone], file_path: str = "") -> list[Violation]:
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

    def check(self, lines: list[str], zones: list[DocumentZone], file_path: str = "") -> list[Violation]:
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

    def check(self, lines: list[str], zones: list[DocumentZone], file_path: str = "") -> list[Violation]:
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
        "Escape unescaped underscores in inline and single-line display dollar math spans "
        "to prevent CommonMark emphasis collision (\\_)"
    )
    severity: str = "error"

    def check(self, lines: list[str], zones: list[DocumentZone], file_path: str = "") -> list[Violation]:
        violations: list[Violation] = []

        for zone in zones:
            if zone.zone_type in (Zone.PROSE, Zone.TABLE):
                for line_idx, line in enumerate(zone.lines):
                    line_no = zone.start_line + line_idx
                    # Count total unescaped underscores on the entire line
                    raw_underscores = len(re.findall(r"(?<!\\)_", line))
                    if raw_underscores < 2:
                        continue

                    spans = scan_inline_spans(line, line_no)
                    for span in spans:
                        # Target inline dollar math ($...$) and single-line display math ($$...$$) in prose/table zones
                        if span.delimiter not in ("$", "$$"):
                            continue
                        if span.zone_type not in (Zone.INLINE_MATH, Zone.DISPLAY_MATH):
                            continue

                        # Find regions inside text macros (\text{...}, \mathrm{...}, etc.)
                        # Underscores inside text macros are handled separately by Rule M03 (\\_)
                        macro_calls = find_macro_calls(span.content, TEXT_MACROS)
                        macro_ranges = [(start, end) for _, _, _, start, end in macro_calls]

                        for m in re.finditer(r"(?<!\\)_", span.content):
                            u_pos = m.start()
                            in_macro = any(start <= u_pos < end for start, end in macro_ranges)
                            if in_macro:
                                continue

                            col_start = span.start_col + len(span.delimiter) + u_pos
                            col_end = col_start + 1
                            edit = LintEdit(
                                rule_id=self.id,
                                start_line=line_no,
                                start_col=col_start,
                                end_line=line_no,
                                end_col=col_end,
                                replacement="\\_",
                            )
                            violations.append(
                                Violation(
                                    rule_id=self.id,
                                    message=(
                                        "Unescaped underscore in inline dollar math collides with CommonMark emphasis. "
                                        "Escape as '\\_'."
                                    ),
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
        "Ensure inline math delimiters satisfy GFM boundary rules (no glued units or compound hyphenation)"
    )
    severity: str = "error"

    def check(self, lines: list[str], zones: list[DocumentZone], file_path: str = "") -> list[Violation]:
        violations: list[Violation] = []

        for zone in zones:
            if zone.zone_type in (Zone.PROSE, Zone.TABLE):
                for line_idx, line in enumerate(zone.lines):
                    line_no = zone.start_line + line_idx
                    spans = scan_inline_spans(line, line_no)

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

        return violations
