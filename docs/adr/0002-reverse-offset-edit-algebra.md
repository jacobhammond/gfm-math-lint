# ADR 0002: Reverse-Offset Edit Algebra for Idempotent Fixing

## Status
Accepted

## Date
2026-09-30

## Context
When multiple linter rules detect violations in the same document, applying text edits in sequential order (top-to-bottom or left-to-right) corrupts character offsets:
1. Inserting or deleting characters on line $L$ shifts the column indices of all subsequent violations on line $L$.
2. Inserting or removing lines shifts line numbers for all subsequent violations.
3. Complex cascading calculations or multi-pass re-tokenization degrade performance and can induce infinite loops or non-idempotent cycles.

## Decision
All automated fixes are applied using a **reverse-offset edit algebra**:
1. Rules emit atomic edit tuples: `(start_line, start_col, end_line, end_col, replacement_text)`.
2. The fixer sorts all pending edits in descending order:
   - Primary key: `start_line` descending.
   - Secondary key: `start_col` descending.
3. Edits are applied from bottom-to-top and right-to-left.

## Consequences
### Positive
- Mutating text at line $L$, column $C$ has zero effect on any coordinates at earlier lines or earlier columns on line $L$.
- Eliminates offset recalculation overhead.
- Guarantees strict idempotency:
  $$\text{fix}(\text{fix}(c)) \equiv \text{fix}(c)$$

### Negative
- Overlapping edit ranges from different rules must be detected and de-duplicated to prevent collisions (handled by the fixer's collision rejection pass).
