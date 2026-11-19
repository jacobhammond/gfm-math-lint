# ADR 0005: Hierarchical Block-Context Tracking & CommonMark Math Emulator

## Status
Accepted

## Date
2026-11-18

## Context
The original 8-zone lexical state machine (ADR 0003) tokenized top-level `FENCED_CODE`, `DISPLAY_MATH`, `TABLE`, `COMMENT`, and `PROSE` blocks without retaining container nesting metadata. Consequently:
1. Rules such as `GFM-M01` and `GFM-M02` relied on fragile line-indentation heuristics and misclassified display math or ```` ```math ```` blocks nested inside list items or blockquotes (including `> $$` blocks).
2. Rule `GFM-M12` relied on counting underscores across an entire line without modeling CommonMark §6.2 delimiter-run flanking or excluding inline code spans, creating false positives on intra-word subscripts (`$a_1 + b_2$`) and adjacent code identifiers (`` `SENSOR_CR1` ``).
3. Offline rendering verification lacked a zero-dependency CommonMark math escape and block-interruption model.

## Decision
1. Extend `DocumentZone` in `src/gfm_math_lint/tokenizer.py` with:
   - `parent_block: str | None = None` (`None | "list_item" | "blockquote" | "table"`)
   - `indent_level: int = 0`
   - `list_marker: str = ""`
2. Extend `DISPLAY_MATH_LINE_RE` to match blockquote-prefixed display math lines (`^\s*(?:>\s*)*\$\$\s*$`) and track active list/blockquote context in `scan_document_zones()`.
3. Introduce `src/gfm_math_lint/emulator.py` (pure Python stdlib per ADR 0001) implementing CommonMark §2.4 math backslash-punctuation unescaping (`emulate_github_math_escapes`), CommonMark §6.2 delimiter-run flanking classification (`find_colliding_math_underscores`), and CommonMark display-math block interruption detection (`BLOCK_INTERRUPT_RE`).

## Consequences
### Positive
- Rules `GFM-M01`, `GFM-M02`, `GFM-M12`, `GFM-M16`, and `GFM-M17` share a single authoritative CommonMark container and delimiter model.
- Zero external runtime dependencies are added (ADR 0001 preserved).
- Offline conformance verification (`github_oracle.py`) accurately reproduces GitHub `cmark-gfm` math behavior without network access.

### Negative
- `scan_document_zones()` maintains lightweight list/blockquote state across lines, requiring careful handling of list continuation vs. column-0 resets.
