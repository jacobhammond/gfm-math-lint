# Documentation

Welcome to the **gfm-math-lint** technical documentation. This directory provides in-depth architecture explanations, Python library API references, exhaustive rule guides, and Architectural Decision Records (ADRs).

---

## Documentation Index

### 1. [Architecture & Engine Design](architecture.md)
Detailed walkthrough of the internal parsing and transformation pipeline:
- **Lexical Segmentation:** 8-zone lexical state machine (`Tokenizer`).
- **Rule Lifecycle:** Violation detection across semantic document zones.
- **Deterministic Edit Algebra:** Bottom-up reverse-offset fix application (`Fixer`).
- **Rendering Verification:** GitHub REST API oracle and standalone KaTeX preview generator (`Verifier`).

### 2. [Python API Reference](api.md)
Comprehensive programmatic guide for integrating `gfm-math-lint` as a library:
- Core classes: `Linter`, `LintResult`, `Violation`, `LintConfig`.
- Verification APIs: `verify_markdown`, `verify_file`, and `build_preview_html`.
- Practical recipes for CI pipelines, test harnesses (pytest), and pre-commit integrations.

### 3. [Complete Rule Catalog](rules.md)
Deep dive into every built-in rule:
- Full specifications for `GFM-M01` through `GFM-M13` (Math & KaTeX).
- Table, code fence, diagram, shell scanner, and image asset rules.
- CommonMark and KaTeX failure mode explanations with compliant examples.
- Step-by-step tutorial on authoring custom rules by subclassing `Rule`.

### 4. [Architectural Decision Records (ADRs)](adr/README.md)
Historical records of key architectural and technical trade-offs:
- [ADR 0001: Zero External Runtime Dependencies](adr/0001-zero-dependency-stdlib.md)
- [ADR 0002: Reverse-Offset Edit Algebra for Idempotent Fixing](adr/0002-reverse-offset-edit-algebra.md)
- [ADR 0003: Lexical Zone State Machine vs. Full AST Parsing](adr/0003-lexical-zone-state-machine.md)
- [ADR 0004: Live GitHub API Rendering Oracle](adr/0004-live-github-api-oracle.md)
