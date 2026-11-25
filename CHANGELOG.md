# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2026-11-25

### Added
- **Composite GitHub Action (`actions/gfm-math-lint-action`)**: Added a reusable composite GitHub Action supporting `check`, `fix`, `verify`, `probe`, and `check-shell` modes, `--format github`/`json` output, JSON report paths, and safe stdin-streamed PR summary comments (`post-comment`).
- **Expanded Pre-Commit Hooks (`.pre-commit-hooks.yaml`)**: Added `gfm-math-fix` (`gfm-math-lint fix`) and `gfm-math-verify` (`gfm-math-lint verify`) alongside `gfm-math-lint` and `gfm-shell-lint`.
- **One-Page Safe Subset Cheat Sheet (`docs/safe-subset-cheatsheet.md`)**: Published the dual-engine authoring cheat sheet (letter-named macros, EOL-only `\\`, column-0 `$$`, Mermaid `<br>` & `flowchart LR` + `-.->`, `GFM-T01` `\lvert...\rvert`), live-confirmed `P1`–`P11` GitHub `/markdown` Probe Ground-Truth Table, and explicit Privacy Model.
- **Diagnostic Documentation Links (`rules/base.py`, `linter.py`, `cli.py`)**: Added `SAFE_SUBSET_DOCS_URL` and `get_safe_subset_url()`, `"docs_url"` in JSON violation payloads, CLI `--help` epilog, and terminal diagnostic hints.
- **Archived Field Retrospectives & ADR 0006**: Extracted Session 1 & Session 2 forensic retrospectives to `docs/retrospectives/`, added [ADR 0006](docs/adr/0006-privacy-first-differential-verification.md), and refreshed `docs/README.md` and `docs/rules.md`.

### Changed
- **Production/Stable Release**: Promoted package classifier from `4 - Beta` to `5 - Production/Stable` (`1.0.0`) with all Phases 0–5 completed in `ROADMAP.md`.

## [0.4.0] - 2026-11-25

### Added
- **Unexplained Span-Diff Fallback (`GFM-E01`) & Telemetry (`linter.py`)**: Connected `emulate_gfm_document()` directly into `Linter.lint_string()`, populating `LintResult.span_diff` (`SpanDiffTelemetry`) and emitting `GFM-E01` whenever a GFM math span discrepancy (`span-dropped`, `span-mutated`, `span-count-mismatch`) is not already explained by `GFM-M01`–`GFM-M18` or `GFM-T01`.
- **Rule `GFM-C03` (`unrendered-math-or-diagram-fence`)**: Detects unrendered mathematical equations (`dU/dt = -γ U + Σ P_k`, `U = |a|²`, raw LaTeX macros) and 2D ASCII box-drawing topology diagrams (`┌───┐ ───►`) inside unlabelled or `text`/`plaintext` code fences (while excluding `tree`/`eza` directory listings).
- **Machine-Readable JSON Output (`--format json`)**: Added `--format json` across `check`, `fix`, `check-shell`, and `verify`, emitting structured diagnostics including `target` profile, `violations`, `fixed_violations`, `remaining_violations`, and `span_diff` telemetry.

## [0.3.0] - 2026-11-25

### Added
- **Zero-Dependency LaTeX Validator & Optional KaTeX Strict Runner (`latex.py`)**: Added pure-Python `validate_latex()` for balanced braces, `\begin`/`\end` environments, `\left`/`\right` delimiters, `\text{...}` raw underscores, `\frac` argument checks, and dangling/double scripts, plus optional local Node.js `run_local_katex_verification()` surfacing strict KaTeX warnings (`katex-warning`).
- **Differential Span Comparator & Full Local GFM Emulator (`emulator.py`)**: Added `extract_intended_math_spans()`, `emulate_gfm_document()`, and `compare_math_spans()` reporting `span-count-mismatch`, `span-dropped`, and `span-mutated` diffs offline.
- **Privacy-First Local `verify` Default (`verify` vs. `verify --remote`)**: `gfm-math-lint verify` now runs 100% locally by default using `emulator.py` + `latex.py` + optional local KaTeX without transmitting user documents over the network. Pass `--remote` to opt into live GitHub `/markdown` API rendering. Both modes report `Recognized X/Y math spans` and per-span diffs.
- **Synthetic Ground-Truth Calibrator (`gfm-math-lint probe`)**: Added `probe.py` and the `probe` CLI subcommand (`--offline`, `--format json`, `--token`) to validate `emulator.py` against the built-in `P1`–`P11` synthetic probe corpus in a single GitHub `/markdown` API call without transmitting user files, wired into `.github/workflows/conformance-gate.yml` on a weekly schedule.
- **Opportunistic Mermaid Parse Rule (`GFM-D06`) & Preview Renderer (`--preview-dir`)**: Added `RuleD06` (`mermaid-parse`) and `verify --preview-dir <dir>` using `mmdc` with desktop-quiet `chrome-headless-shell` (`PUPPETEER_SKIP_DOWNLOAD=1`, `"headless": "shell"`).

## [0.2.0] - 2026-11-18

### Added
- **Hierarchical Block-Context Tokenizer (`ADR 0005`)**: Extended `DocumentZone` with `parent_block`, `indent_level`, and `list_marker`, plus blockquote display math (`> $$`) recognition.
- **Zero-Dependency CommonMark Math Emulator (`emulator.py`)**: Implemented CommonMark §2.4 math backslash-punctuation unescaping, §6.2 underscore delimiter-run flanking analysis, and block-interruption detection.
- **Target Engine Profiles (`target` / `--target`)**: Added `"dual"` (default), `"github"`, and `"vscode"` rendering profiles in `[tool.gfm-math-lint]` and CLI `check`/`fix`.
- **Rule `GFM-M14` (`code-syntax-in-math`, closes #6)**: Detects and converts pseudo-code function identities (`$\text{fix}(\text{fix}(c)) \equiv \text{fix}(c)$`) and standalone `snake_case` identifiers in math to inline code backticks, avoiding KaTeX MathML vertical stacking artifacts.
- **Rule `GFM-M15` (`cross-engine-latex-compat`, closes #22)**: Flags Unicode en/em-dashes, bare `%` and single-escaped `\%` in `$...$` / `$$...$$` (wrapping inline spans in GFM backtick math `` $`...\%...`$ ``), and HTML pipe entities (`&#124;`, `&#x7c;`, `&verbar;`) in math spans.
- **Rule `GFM-M16` (`display-linebreak-eol`)**: Flags mid-line `\\` inside `$$...$$` display math (which CommonMark collapses to `\`) and inserts line breaks after `\\`.
- **Rule `GFM-M17` (`display-line-block-start`)**: Flags interior display math lines starting with Markdown block openers (`+ `, `- `, `* `, `> `, `#`, `1. `, setext underlines) and auto-fixes leading `+ ` / `- ` with `{}+ ` / `{}- `.
- **Rule `GFM-M18` (`non-ascii-in-math`)**: Flags and converts non-ASCII symbols (`µ`, `°`, `²`, `³`, `·`, `−`, Unicode Greek) in math to portable LaTeX macros.
- **Mermaid Rules `GFM-D03`, `GFM-D04`, `GFM-D05`**: Replaces literal `\n` in Mermaid labels with `<br>`, quotes unquoted node labels with `() {} |`, flags internal pipes in `-->|...|` edge labels, and warns on LaTeX math inside Mermaid diagrams.
- **Safe-Fix Guard & Post-Fix Re-Check Contract**: `Linter.lint_string(..., fix=True)` records `fixed_violations` and `remaining_violations`, rolls back unsafe edits that introduce net-new unfixable violations, and `gfm-math-lint fix` / `check --fix` exits `0` when all violations are resolved.

### Changed
- **Rule `GFM-T01` Portable Table Delimiters (closes #22)**: Replaced `&#124;` math auto-fixes (which break GitHub MathJax and KaTeX) with `\lvert ... \rvert`, `\lVert ... \rVert`, and `\vert`, and added cleanup for legacy HTML pipe entities.
- **Rule `GFM-M01` & `GFM-M02` List Reconciliation**: `GFM-M01` preserves ```` ```math ```` fences nested inside lists and blockquotes (and skips fences with unfixable block interruptions); `GFM-M02` detects and breaks out indented/list-nested `$$` blocks to column 0.
- **Rule `GFM-M03` Safe Fix**: Removed harmful `\\_` double-escape replacement (which crashed KaTeX); embedded text-mode underscores in equations are converted to hyphens while standalone identifiers move to inline code via `GFM-M14`.
- **Rule `GFM-M05` Generalization (`backslash-punctuation-escape`)**: Expanded beyond braces to cover `\,` (`\thinspace`), `\:` (`\medspace`), `\;` (`\thickspace`), `\!` (`\negthinspace`), and `\|` (`\Vert` / `\left\lVert` / `\right\rVert`).
- **Rule `GFM-M12` Flanking Precision**: Uses CommonMark §6.2 delimiter-run flanking so intra-word subscripts (`$a_1 + b_2$`) and adjacent code spans no longer false-positive.
- **Rule `GFM-M13` Glued Opening Delimiter**: Added detection and spacing auto-fix for opening `$` glued to hyphens, dashes, slashes, or alphanumerics (`base-$e$`).
- **Strict Conformance Crucible CI Gate**: Enforced `--strict` 100% gating across the 156-scenario Conformance Crucible in `.github/workflows/conformance-gate.yml`.

### Removed
- **Rule `GFM-I01` (`image-avif-format`)**: Removed out-of-scope AVIF image format rule (`image_rules.py` and `test_image_rules.py`).

## [0.1.2] - 2026-10-26

### Added
- **Stdin Input (`-`) Support in `verify`**: Added ability to verify piped markdown streams via standard input (`cat doc.md | gfm-math-lint verify -` or `git show HEAD:README.md | gfm-math-lint verify -`).
- **Raw HTML Streaming (`--stdout` / `--raw`)**: Added `--stdout` flag (with alias `--raw`) to stream rendered HTML directly to stdout while cleanly routing diagnostic logs and audit reports to stderr.
- **Buffered Block Container Traversal**: `GFMHTMLValidator` buffers text data across inline tag boundaries inside block containers (`<p>`, `<li>`, `<td>`, `<blockquote>`) to catch unrendered math delimiters split across formatting tags like `<em>` and `<strong>`.
- **MathML Pseudo-Code Stacking Detection**: Added heuristic scanner inside `<math-renderer>` elements to detect programming function composition placed in math delimiters, emitting `pseudo-code-stacking` verification warnings for formulas that cause vertical character stacking in environments without KaTeX CSS.
- **GFM-S01 Shell Scanner Expansion**: Extended `RuleS01` (`unsafe-shell-expansion`) to scan `gh issue create` and `gh pr create` commands alongside existing comment and release commands, preventing LaTeX corruption from shell parameter expansions.
- **Safe GitHub Issue & PR Creation**: Added `--create-issue` and `--create-pr` workflows to `gfm-math-lint comment` (with `post` CLI alias) supporting metadata options (`--title`, `--label`, `--assignee`, `--milestone`, `--base`, `--head`), streaming markdown content via stdin to prevent LaTeX corruption.
- **Headless HTTP REST API Fallback**: Added standard library `urllib.request` fallback in `comment.py` (`preview_markdown`, `create_issue`, `create_pr`) using `$GITHUB_TOKEN` or `$GH_TOKEN` when the `gh` CLI is absent.
- **Conformance Crucible Benchmark Pipeline**: Added 4-stage validation runner (`conformance.runner`) testing formula detection completeness, fix convergence, KaTeX AST validity, and GitHub API HTML rendering.
- **Combinatorial Conformance Matrix**: Added 145-scenario test corpus across nested lists, blockquotes, tables, diagrams, and math constructs with synthetic generator (`scripts/generate_conformance_matrix.py`) and manifest.
- **CI Conformance Gate Workflow**: Integrated automated Conformance Crucible gating workflow in `.github/workflows/conformance-gate.yml`.

### Security
- Support HTML5 comment end bang state (`--!>`) across tokenizer and diagram rules, remediating CodeQL alerts #1 and #2 (`py/bad-tag-filter`).

## [0.1.1] - 2026-09-30

### Fixed
- Fixed release asset upload in CI publishing workflow by explicitly targeting the repository.

## [0.1.0] - 2026-09-30

- Initial release.

[1.0.0]: https://github.com/jacobhammond/gfm-math-lint/compare/v0.4.0...v1.0.0
[0.4.0]: https://github.com/jacobhammond/gfm-math-lint/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/jacobhammond/gfm-math-lint/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/jacobhammond/gfm-math-lint/compare/v0.1.2...v0.2.0
[0.1.2]: https://github.com/jacobhammond/gfm-math-lint/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/jacobhammond/gfm-math-lint/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/jacobhammond/gfm-math-lint/releases/tag/v0.1.0
