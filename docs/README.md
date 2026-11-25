# Documentation

Welcome to the **gfm-math-lint** technical documentation. This directory provides the one-page Safe Subset Cheat Sheet, architecture explanations, Python library API references, complete rule guides, archived field retrospectives, and Architectural Decision Records (ADRs).

---

## Documentation Index

### 1. [Safe Subset Cheat Sheet, Probe Ground Truth & Privacy Model](safe-subset-cheatsheet.md)
One-page author reference for dual-engine compatibility (GitHub Web + VS Code / KaTeX):
- **Letter-Named Macros:** Before/after conversions for `\,`, `\{`, `\|`, `<`, `*`, `\%`, and Unicode glyphs.
- **Display & Inline Structure:** Column-0 `$$`, EOL-only `\\`, block-opener guards, and table `\lvert...\rvert` delimiters.
- **Mermaid & Code/Shell:** `<br>` linebreaks, quoted labels, `flowchart LR` + `-.->`, `GFM-C03`, and `GFM-S01`.
- **GitHub Probe Ground Truth (`P1`–`P11`) & Privacy Model:** Live-confirmed probe matrix and offline-first network guarantees.

### 2. [Architecture & Engine Design](architecture.md)
Detailed walkthrough of the internal parsing and transformation pipeline:
- **Lexical Segmentation:** 8-zone lexical state machine (`Tokenizer`) with hierarchical block-context tracking (`ADR 0005`).
- **Rule Lifecycle & Differential Emulator:** Violation detection across semantic zones plus `emulate_gfm_document()` (`GFM-E01`).
- **Deterministic Edit Algebra:** Bottom-up reverse-offset fix application (`Fixer`) with Safe-Fix Guard.
- **Rendering Verification:** Privacy-first local `verify`, optional `--remote` GitHub `/markdown` oracle, `probe`, and KaTeX previewer.

### 3. [Python API Reference](api.md)
Comprehensive programmatic guide for integrating `gfm-math-lint` as a library:
- Core classes: `Linter`, `LintResult`, `LintConfig`, `SpanDiffTelemetry`, `Violation`.
- Verification & Probe APIs: `verify_markdown`, `verify_file`, `verify_markdown_detailed`, `run_probes`, `validate_latex`, and `build_preview_html`.
- Practical recipes for CI pipelines, pytest suites, and pre-commit integrations.

### 4. [Complete Rule Catalog & Authoring Guide](rules.md)
Deep dive into all 29 built-in rules (plus `GFM-E01` differential fallback):
- Full specifications for `GFM-M01` through `GFM-M18` (Math & KaTeX), `GFM-T01` (Tables), `GFM-C01`–`C03` (Code), `GFM-E01` (Emulator), `GFM-D01`–`D06` (Mermaid), and `GFM-S01` (Shell).
- Rule suppression directives and custom `Rule` authoring tutorial.

### 5. [Field Retrospectives](retrospectives/README.md)
Archived empirical forensic traces from Session 1 (`session-harvest-trace-01`) and Session 2 (`dual-doc-conversion-2026-11`).

### 6. [GitHub Action Integration](../actions/gfm-math-lint-action/README.md)
Composite GitHub Action (`actions/gfm-math-lint-action`) supporting `check`, `fix`, `verify`, `probe`, `check-shell`, JSON reports, and safe PR summary comments.

### 7. [Architectural Decision Records (ADRs)](adr/README.md)
Historical records of key architectural and technical trade-offs:
- [ADR 0001: Zero External Runtime Dependencies](adr/0001-zero-dependency-stdlib.md)
- [ADR 0002: Reverse-Offset Edit Algebra for Idempotent Fixing](adr/0002-reverse-offset-edit-algebra.md)
- [ADR 0003: Lexical Zone State Machine vs. Full AST Parsing](adr/0003-lexical-zone-state-machine.md)
- [ADR 0004: Live GitHub API Rendering Oracle](adr/0004-live-github-api-oracle.md)
- [ADR 0005: Hierarchical Block-Context Tracking & CommonMark Math Emulator](adr/0005-hierarchical-block-context.md)
- [ADR 0006: Privacy-First Differential Verification & Synthetic Probe Calibration](adr/0006-privacy-first-differential-verification.md)
