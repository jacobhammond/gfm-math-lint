# ADR 0006: Privacy-First Differential Verification & Synthetic Probe Calibration

## Status
Accepted (supersedes default network transmission in [ADR 0004](0004-live-github-api-oracle.md))

## Date
2026-11-25

## Context
During Session 2 (`dual-doc-conversion-2026-11`), `gfm-math-lint verify` transmitted entire Markdown documents to `api.github.com/markdown` by default (ADR 0004), preventing verification of private or proprietary documents (Document B) and missing silent CommonMark mutations such as collapsed mid-line `\\` (`a \\ b` $\to$ `a \ b`) or stripped `\,` spacing inside `<math-renderer>`.

## Decision
1. **Local-First Differential `verify` Default:** `gfm-math-lint verify` runs **100% offline by default**, combining `emulate_gfm_document()` (`src/gfm_math_lint/emulator.py`), `validate_latex()` (`src/gfm_math_lint/latex.py`), optional local Node.js `katex` strict validation, and `compare_math_spans()` (`span-count-mismatch`, `span-dropped`, `span-mutated`).
2. **Explicit Network Opt-In (`--remote`):** Sending user documents to `api.github.com/markdown` requires passing `--remote` explicitly.
3. **Synthetic Ground-Truth Calibrator (`gfm-math-lint probe`):** Validate `emulator.py` against live GitHub `/markdown` using only the built-in synthetic probe corpus (`P1`–`P11` in `src/gfm_math_lint/probe.py`), never user files.
4. **Unified Linter Fallback (`GFM-E01`):** Wire `emulate_gfm_document()` into `Linter.lint_string()` so any unexplained span discrepancy is surfaced directly during `gfm-math-lint check`.

## Consequences
### Positive
- Proprietary documents can be verified locally with zero network transmission.
- Silent CommonMark mutations and dropped math spans are caught during both `check` (`GFM-E01`) and `verify`.
- Upstream GitHub `cmark-gfm` / MathJax drift is detected automatically via scheduled `gfm-math-lint probe` CI runs without exposing user content.

### Negative
- Local emulation relies on `emulator.py` staying calibrated with GitHub's `cmark-gfm` pipeline (mitigated by `probe` + Conformance Crucible gating).
