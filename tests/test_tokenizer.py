"""Unit tests for the lexical zone tokenizer."""

from __future__ import annotations

from gfm_math_lint.tokenizer import (
    Zone,
    scan_document_zones,
    scan_inline_spans,
)


def test_frontmatter_detection() -> None:
    lines = [
        "---\n",
        "title: Test\n",
        "tags: [latex, math]\n",
        "---\n",
        "\n",
        "# Header\n",
    ]
    zones = scan_document_zones(lines)
    assert len(zones) >= 2
    assert zones[0].zone_type == Zone.FRONTMATTER
    assert zones[0].start_line == 1
    assert zones[0].end_line == 4
    assert zones[0].is_closed is True


def test_fenced_code_blocks() -> None:
    lines = [
        "```python\n",
        "def hello():\n",
        "    return 'world'\n",
        "```\n",
    ]
    zones = scan_document_zones(lines)
    assert len(zones) == 1
    assert zones[0].zone_type == Zone.FENCED_CODE
    assert zones[0].info == "python"
    assert zones[0].fence_char == "`"
    assert zones[0].fence_len == 3
    assert zones[0].is_closed is True
    assert zones[0].start_line == 1
    assert zones[0].end_line == 4


def test_display_math_blocks() -> None:
    lines = [
        "$$\n",
        "x = y + 1\n",
        "$$\n",
    ]
    zones = scan_document_zones(lines)
    assert len(zones) == 1
    assert zones[0].zone_type == Zone.DISPLAY_MATH
    assert zones[0].start_line == 1
    assert zones[0].end_line == 3
    assert zones[0].is_closed is True


def test_table_zones() -> None:
    lines = [
        "| Header 1 | Header 2 |\n",
        "| :--- | :--- |\n",
        "| Cell 1 | Cell 2 |\n",
        "\n",
        "Prose line.\n",
    ]
    zones = scan_document_zones(lines)
    assert len(zones) == 3
    assert zones[0].zone_type == Zone.TABLE
    assert zones[0].start_line == 1
    assert zones[0].end_line == 3
    assert zones[1].zone_type == Zone.PROSE
    assert zones[2].zone_type == Zone.PROSE


def test_multiline_comment_zones() -> None:
    lines = [
        "<!--\n",
        "This is a comment\n",
        "-->\n",
        "Prose\n",
    ]
    zones = scan_document_zones(lines)
    assert zones[0].zone_type == Zone.COMMENT
    assert zones[0].is_closed is True
    assert zones[0].start_line == 1
    assert zones[0].end_line == 3

    # Test HTML5 comment end bang state (--!>)
    lines_bang = [
        "<!--\n",
        "This is a comment ending with bang\n",
        "--!>\n",
        "Prose\n",
    ]
    zones_bang = scan_document_zones(lines_bang)
    assert zones_bang[0].zone_type == Zone.COMMENT
    assert zones_bang[0].is_closed is True
    assert zones_bang[0].start_line == 1
    assert zones_bang[0].end_line == 3


def test_scan_inline_spans() -> None:
    line = "Here is $`x^2`$ and `code` and $y + 1$ and <!-- inline comment --> and <!-- bang comment --!> prose."
    spans = scan_inline_spans(line, line_no=1)

    types = [s.zone_type for s in spans]
    assert Zone.INLINE_MATH in types
    assert Zone.INLINE_CODE in types
    assert Zone.COMMENT in types
    assert Zone.PROSE in types

    # Check backtick math span
    bt_math = next(s for s in spans if s.delimiter == "$`")
    assert bt_math.content == "x^2"

    # Check code span
    code = next(s for s in spans if s.zone_type == Zone.INLINE_CODE)
    assert code.content == "code"

    # Check inline math span
    math_span = next(s for s in spans if s.delimiter == "$")
    assert math_span.content == "y + 1"

    # Check comment spans (both standard --> and bang --!>)
    comments = [s for s in spans if s.zone_type == Zone.COMMENT]
    assert len(comments) == 2
    assert comments[0].content == "inline comment"
    assert comments[1].content == "bang comment"


def test_is_table_delimiter_row() -> None:
    from gfm_math_lint.tokenizer import is_table_delimiter_row

    assert is_table_delimiter_row("| :--- | :---: | ---: |") is True
    assert is_table_delimiter_row("|---|---|") is True
    assert is_table_delimiter_row("||") is False
    assert is_table_delimiter_row("| |") is False
    assert is_table_delimiter_row("| abc | def |") is False


def test_is_escaped() -> None:
    from gfm_math_lint.tokenizer import is_escaped

    assert is_escaped("$foo", 0) is False
    assert is_escaped(r"\$foo", 1) is True
    assert is_escaped(r"\\$foo", 2) is False
    assert is_escaped(r"\\\$foo", 3) is True


def test_inline_math_numeric_and_currency_disambiguation() -> None:
    # Numbers in closed math delimiters must be recognized as inline math
    line = r"Bounds $0 \le f(x) \le 1$ and scalar $0.75$ and factor: $3.85$."
    spans = scan_inline_spans(line, line_no=1)
    math_spans = [s for s in spans if s.zone_type == Zone.INLINE_MATH]
    assert len(math_spans) == 3
    assert math_spans[0].content == r"0 \le f(x) \le 1"
    assert math_spans[1].content == "0.75"
    assert math_spans[2].content == "3.85"

    # Currency pairs in prose (e.g. "$10 to $20") must NOT be treated as inline math
    curr_line = "The price is $10 to $20 for each."
    curr_spans = scan_inline_spans(curr_line, line_no=1)
    curr_math = [s for s in curr_spans if s.zone_type == Zone.INLINE_MATH]
    assert len(curr_math) == 0


def test_hierarchical_block_context_tracking() -> None:
    lines = [
        "* List step:\n",
        "  > Note:\n",
        "  > $$\n",
        "  > x = 1\n",
        "  > $$\n",
        "\n",
        "  ```math\n",
        "  y = 2\n",
        "  ```\n",
        "\n",
        "Root prose resets list state.\n",
        "\n",
        "```math\n",
        "z = 3\n",
        "```\n",
    ]
    zones = scan_document_zones(lines)
    dm_zones = [z for z in zones if z.zone_type == Zone.DISPLAY_MATH]
    assert len(dm_zones) == 1
    assert dm_zones[0].is_closed is True
    assert dm_zones[0].parent_block == "list_item"
    assert dm_zones[0].indent_level == 2
    assert dm_zones[0].list_marker == "*"

    fence_zones = [z for z in zones if z.zone_type == Zone.FENCED_CODE]
    assert len(fence_zones) == 2
    assert fence_zones[0].parent_block == "list_item"
    assert fence_zones[0].indent_level == 2
    assert fence_zones[1].parent_block is None
    assert fence_zones[1].indent_level == 0


def test_emulator_escapes_flanking_and_block_interrupt() -> None:
    from gfm_math_lint.emulator import (
        emulate_github_math_escapes,
        find_colliding_math_underscores,
        has_block_interrupt,
        is_flanking_underscore,
    )

    assert emulate_github_math_escapes(r"x\,y \{z\} \lvert w\rvert", display=False) == r"x,y {z} \lvert w\rvert"
    assert emulate_github_math_escapes("a \\\\ b", display=True) == "a \\ b"
    assert emulate_github_math_escapes("a \\\\\nb", display=True) == "a \\\\\nb"

    assert is_flanking_underscore("a_1", 1) is False
    assert is_flanking_underscore("P _ {x}", 2) is False
    assert is_flanking_underscore("P_{x}", 1) is True

    # Intra-word only line must not collide; flanking line must collide; code span underscore ignored
    intra_spans = scan_inline_spans("Let $a_1 + b_2$ and $c_3$.", 1)
    assert find_colliding_math_underscores(intra_spans) == []

    code_adj_spans = scan_inline_spans("Register `SENSOR_CR1` satisfies $P_a \\ge 0.5$.", 1)
    assert find_colliding_math_underscores(code_adj_spans) == []

    flank_spans = scan_inline_spans(r"Let $P_{\text{primary}}$ and $P_{\text{secondary}}$ be powers.", 1)
    assert len(find_colliding_math_underscores(flank_spans)) == 2

    assert has_block_interrupt(["P = U\n", "+ Z\n"]) is True
    assert has_block_interrupt(["P = U +\n", "Z\n"]) is False
