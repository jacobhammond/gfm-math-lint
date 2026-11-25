# gfm-math-lint

[![ci](https://github.com/jacobhammond/gfm-math-lint/actions/workflows/ci.yml/badge.svg)](https://github.com/jacobhammond/gfm-math-lint/actions/workflows/ci.yml)
[![pypi version](https://img.shields.io/pypi/v/gfm-math-lint.svg)](https://pypi.org/project/gfm-math-lint/)
[![license](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/jacobhammond/gfm-math-lint/blob/main/LICENSE)
[![python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)

Zero-dependency, high-performance GitHub Flavored Markdown (GFM) linter and auto-fixer specializing in LaTeX/MathJax & KaTeX dual-engine math syntax, CommonMark table escaping, fenced code nesting, Mermaid diagram boundaries, and shell script expansion guards.

> [!IMPORTANT]
> 🗺️ **Roadmap & Conformance Crucible (`v1.0.0` Shipped):**  
> Review [ROADMAP.md](ROADMAP.md) for the completed multi-phase development ledger, Dual-Engine compatibility matrix, and 156-scenario Conformance Crucible gating harness, or jump straight to the one-page [Safe Subset Cheat Sheet](docs/safe-subset-cheatsheet.md).

---

## Key Features

- **Pure Standard Library**: Zero third-party runtime dependencies. Runs instantly with Python 3.11+.
- **8-Zone Lexical State Machine**: High-fidelity tokenizer classifying document lines into `FRONTMATTER`, `FENCED_CODE`, `INLINE_CODE`, `DISPLAY_MATH`, `INLINE_MATH`, `TABLE`, `COMMENT`, and `PROSE` to eliminate false positives.
- **Reverse-Offset Edit Algebra**: Deterministic bottom-up, right-to-left fix application guaranteeing strict idempotency: `fix(fix(c)) == fix(c)`.
- **Unified Diff & In-Place Fixing**: Inspect exact changes in advance with `--diff` or auto-fix in-place with `fix` / `--fix`.
- **Privacy-First Local `verify` & GitHub Rendering Oracle**: Runs offline by default using the zero-dependency CommonMark emulator, pure-Python LaTeX validator, and optional local strict KaTeX runner—never sending user documents over the network unless `--remote` is explicitly passed. Reports `Recognized X/Y math spans`, per-span diffs, HTML tag pollution, and table mismatches.
- **Synthetic `probe` Calibration**: Validates the local emulator against GitHub's live `/markdown` API using only built-in synthetic snippets (`P1`–`P11`)—zero user data ever leaves the machine.
- **KaTeX Browser Preview with Zero Red Boxes**: Generates standalone HTML (`--html`) or opens a live browser preview (`--browser`) with automated entity normalization (e.g., restoring double-escaped `&amp;gt;` to `>`) and duplicate MathML clipboard suppression (`output: "html"`).
- **Safe GitHub Commenting**: Post markdown-rendered comments to PRs and issues via `gh` CLI with stdin streaming (`--body-file -`), preventing shell expansion corruption of LaTeX equations.
- **Pre-commit Native**: Exit code contract (`0` clean, `1` violations/fixes, `2` error) designed specifically for CI/CD and git hook workflows.

---

## Documentation Hub

Comprehensive technical guides, API references, and architectural records are maintained in the [`docs/`](docs/README.md) directory:

| Guide | Description |
| :--- | :--- |
| ⚡ **[Safe Subset Cheat Sheet](docs/safe-subset-cheatsheet.md)** | One-page dual-engine authoring reference, live-confirmed `P1`–`P11` GitHub probe table, and Privacy Model. |
| 🗺️ **[Development Roadmap](ROADMAP.md)** | Completed `v0.1.0`–`v1.0.0` engineering plan, Issue/Regression matrices, and Conformance Crucible harness. |
| 🏛️ **[Architecture & Engine Design](docs/architecture.md)** | 8-zone lexical state machine, multi-stage compilation pipeline, reverse-offset edit algebra, and verification mechanics. |
| 🐍 **[Python API Reference & Recipes](docs/api.md)** | Programmatic library reference (`Linter`, `LintResult`, `LintConfig`, `Verifier`) with recipes for pytest, CI, and Sphinx/MkDocs. |
| 📖 **[Complete Rule Catalog & Authoring Guide](docs/rules.md)** | In-depth specifications for all 29 rules (+ `GFM-E01` fallback), CommonMark/KaTeX failure mode mechanics, and custom rule development tutorial. |
| 🤖 **[GitHub Action Guide](actions/gfm-math-lint-action/README.md)** | Composite GitHub Action (`check`, `fix`, `verify`, `probe`, `check-shell`, JSON reports, and safe PR comments). |
| 🔎 **[Field Retrospectives](docs/retrospectives/README.md)** | Archived Session 1 (`session-harvest-trace-01`) and Session 2 (`dual-doc-conversion-2026-11`) forensic traces. |
| 📋 **[Architectural Decision Records (ADRs)](docs/adr/README.md)** | Technical justifications (`ADR 0001`–`0006`) for zero-dependency stdlib, edit algebra, tokenizer, and privacy-first verification. |

---

## Installation

### With `uv` (Recommended)

```bash
uv tool install gfm-math-lint
```

### With `pip`

```bash
pip install gfm-math-lint
```

---

## Quickstart & Usage

### 1. Checking & Fixing Markdown Files

Inspect files for syntax violations, preview unified diffs, or auto-fix in-place:

```bash
# Check files or directories for violations
gfm-math-lint check docs/ README.md

# Output violations in GitHub Actions workflow command format (::warning / ::error)
gfm-math-lint check --format github docs/

# Output machine-readable JSON diagnostics (including span_diff telemetry)
gfm-math-lint check --format json docs/

# Preview automated fixes as a unified diff without modifying files
gfm-math-lint check --diff docs/

# Automatically fix violations in-place using the 'fix' shortcut (exits 0 when clean)
gfm-math-lint fix docs/ README.md

# Target a specific rendering engine profile (dual, github, or vscode)
gfm-math-lint check --target dual docs/
```

### 2. Scanning Shell Scripts & CI Workflows

Scan bash/sh scripts and GitHub Actions workflows for unsafe double-quoted body arguments (`-b "..."` or `--body "..."`) in `gh` CLI commands that expose LaTeX `$x$` expressions to unintended shell expansion:

```bash
gfm-math-lint check-shell .github/workflows/ scripts/
```

### 3. Safe GitHub Commenting & Issue/PR Creation

Post comments, issues, and pull requests safely without shell expansion or argument size limits by streaming content via stdin directly to `gh` (or using the `post` command alias):

```bash
# Preview rendered markdown via GitHub REST API (POST /markdown with urllib fallback)
gfm-math-lint comment --preview --file report.md

# Post safely to an existing pull request or issue
gfm-math-lint comment --pr 42 --file report.md
gfm-math-lint comment --issue 108 --file notes.md

# Safely open a new issue via file streaming
gfm-math-lint comment --create-issue --title "Math Bug Report" --file report.md --label bug

# Or create a new pull request via stdin pipe
cat spec.md | gfm-math-lint post --create-pr --title "Algorithm Specs" --base main --head feat
```

### 4. Semantic Verification, Synthetic Probes & Diagram Previews

Audit documents locally by default (100% offline), opt into GitHub's live REST API with `--remote`, render Mermaid PNG previews, or calibrate against GitHub using synthetic probes:

```bash
# Verify markdown files locally (offline emulator + LaTeX validator + optional KaTeX)
gfm-math-lint verify docs/ README.md

# Opt into live GitHub /markdown API verification
gfm-math-lint verify --remote docs/ README.md

# Verify piped markdown stream from stdin
cat draft.md | gfm-math-lint verify -
git show HEAD:README.md | gfm-math-lint verify -

# Render high-DPI PNG previews of Mermaid diagrams via mmdc
gfm-math-lint verify --preview-dir build/previews docs/specification.md

# Calibrate local emulator against synthetic GitHub /markdown probes (zero user data sent)
gfm-math-lint probe
gfm-math-lint probe --offline

# Stream rendered HTML directly to stdout (diagnostics routed to stderr)
gfm-math-lint verify --stdout docs/specification.md
gfm-math-lint verify - --raw < draft.md > rendered.html

# Export full rendered HTML preview
gfm-math-lint verify --html preview.html docs/specification.md

# Launch KaTeX-rendered preview directly in your local default browser
gfm-math-lint verify --browser docs/specification.md
```

#### Feature Requirements & Authentication Matrix

`gfm-math-lint` follows an **offline-first** design: core linting, fixing, and default `verify` never require network access or a GitHub account.

| Feature / Command | Requires Internet? | Requires GitHub Account? | Rate Limit | Primary Transport |
| :--- | :---: | :---: | :--- | :--- |
| **`check` / `fix`** | **No** (100% Offline) | **No** | Unlimited (Local execution) | Built-in regex & 8-zone lexical state machine |
| **`check-shell`** | **No** (100% Offline) | **No** | Unlimited (Local execution) | Built-in shell script AST/regex scanner |
| **`verify` (Default)** | **No** (100% Offline) | **No** | Unlimited (Local execution) | Local GFM emulator, `latex.py`, optional local KaTeX |
| **`verify --remote`** | **Yes** | **Optional** | **60–5,000 req / hr** | `gh api /markdown` or HTTPS `POST` to `/markdown` |
| **`probe`** | **Yes** (`--offline` skips) | **Optional** | **1 req / run** (synthetic only) | Single batched `/markdown` request (`P1`–`P11`) |
| **`comment`** | **Yes** | **Yes** (Write access) | Standard GitHub API limits | GitHub CLI (`gh`) with stdin streaming |

> For full architectural details on token resolution order and API rate limit mechanics, see [Architecture & Engine Design: Section 2.D](docs/architecture.md#d-the-verifier--github-api-oracle-gfm_math_lintverifier) and the [Privacy Model](docs/safe-subset-cheatsheet.md#privacy-model).

### 5. Programmatic Python Library Usage

`gfm-math-lint` can be imported directly into Python applications, test suites, or documentation generators:

```python
from gfm_math_lint import Linter

linter = Linter()
result = linter.lint_string("# Document\n\n$x < y$", fix=True)

if result.has_violations:
    for violation in result.violations:
        print(f"Line {violation.line}:{violation.col} [{violation.rule_id}] {violation.message}")

if result.has_fixes:
    print("Fixed content:\n", result.fixed_content)
    print("Unified diff:\n", result.diff())
```

For full class methods, verifier functions, and pytest/CI recipes, see the [Python API Reference](docs/api.md).

---

## Pre-Commit & GitHub Action Integration

### Pre-Commit Hooks

Add `gfm-math-lint` to your `.pre-commit-config.yaml` to enforce valid equations, offline differential verification, and secure shell scripts on commit:

```yaml
repos:
  - repo: https://github.com/jacobhammond/gfm-math-lint
    rev: v1.0.0
    hooks:
      # Validates math, table, code fence, and boundary issues
      - id: gfm-math-lint
      # Optional: auto-fix safe violations in-place
      # - id: gfm-math-fix
      # Optional: run offline differential span & LaTeX verification
      # - id: gfm-math-verify
      # Guards against unsafe shell expansions in CI workflows and scripts
      - id: gfm-shell-lint
```

### GitHub Action

Run `gfm-math-lint` directly in GitHub Actions workflows using the included composite action (see [GitHub Action Guide](actions/gfm-math-lint-action/README.md) for `verify`, `probe`, JSON artifacts, and PR comments):

```yaml
- uses: jacobhammond/gfm-math-lint/actions/gfm-math-lint-action@v1.0.0
  with:
    mode: check
    paths: "README.md docs/"
    target: dual
    format: github
    version: "1.0.0"
```

---

## Configuration

Configure rules and exclusions in your project's `pyproject.toml` under `[tool.gfm-math-lint]`:

```toml
[tool.gfm-math-lint]
# Files or glob patterns to exclude from linting
exclude = [
    "docs/archive/*",
    "vendor/**",
]

# Target rendering engine profile: "dual" (default), "github", or "vscode"
target = "dual"

# Globally ignored rule IDs
ignore = [
    "GFM-M10",  # Allow unescaped currency dollar signs
]

# Per-file rule ignores
[tool.gfm-math-lint.per-file-ignores]
"docs/legacy/*.md" = ["GFM-M08", "GFM-M10"]
"docs/math_guide.md" = ["GFM-M05"]
```

### Inline Rule Suppression

Suppress individual rules directly within Markdown using HTML comments:

```markdown
<!-- gfm-math-lint-disable GFM-M02, GFM-M04 -->
$$
E = mc^2 \\
$$
<!-- gfm-math-lint-enable GFM-M02, GFM-M04 -->

<!-- gfm-math-lint-disable-next-line GFM-M10 -->
The price ranged from $10 to $20.
```

For full suppression options and scope rules, see [Rule Suppression Syntax](docs/rules.md#rule-suppression-syntax).

---

## Rule Catalog Summary

The following rules are enforced by `gfm-math-lint`. For detailed failure mode explanations, compliant examples, and custom rule development, consult the [Complete Rule Catalog](docs/rules.md).

| Rule ID | Category | Name | Severity | Auto-Fix | Canonical Guide |
| :--- | :--- | :--- | :---: | :---: | :--- |
| `GFM-M01` | Math | `math-fence-conversion` | Error | Yes | [Details](docs/rules.md#gfm-m01-math-fence-conversion) |
| `GFM-M02` | Math | `display-math-isolation` | Error | Yes | [Details](docs/rules.md#gfm-m02-display-math-isolation) |
| `GFM-M03` | Math | `text-mode-underscore-escape` | Error | Yes | [Details](docs/rules.md#gfm-m03-text-mode-underscore-escape) |
| `GFM-M04` | Math | `inline-math-whitespace` | Error | Yes | [Details](docs/rules.md#gfm-m04-inline-math-whitespace) |
| `GFM-M05` | Math | `backslash-punctuation-escape` | Error | Yes | [Details](docs/rules.md#gfm-m05-backslash-punctuation-escape) |
| `GFM-M06` | Math | `relational-operator-collision` | Error | Yes | [Details](docs/rules.md#gfm-m06-relational-operator-collision) |
| `GFM-M07` | Math | `asterisk-emphasis-collision` | Error | Yes | [Details](docs/rules.md#gfm-m07-asterisk-emphasis-collision) |
| `GFM-M08` | Math | `disallowed-macro` | Error | Yes | [Details](docs/rules.md#gfm-m08-disallowed-macro) |
| `GFM-M09` | Math | `align-environment` | Error | Yes | [Details](docs/rules.md#gfm-m09-align-environment) |
| `GFM-M10` | Math | `currency-dollar-sign` | Warning | Yes | [Details](docs/rules.md#gfm-m10-currency-dollar-sign) |
| `GFM-M11` | Math | `latex-delimiters-conversion` | Error | Yes | [Details](docs/rules.md#gfm-m11-latex-delimiters-conversion) |
| `GFM-M12` | Math | `inline-math-underscore-collision` | Error | Yes | [Details](docs/rules.md#gfm-m12-inline-math-underscore-collision) |
| `GFM-M13` | Math | `math-delimiter-boundaries` | Error | Yes | [Details](docs/rules.md#gfm-m13-math-delimiter-boundaries) |
| `GFM-M14` | Math | `code-syntax-in-math` | Warning | Yes | [Details](docs/rules.md#gfm-m14-code-syntax-in-math) |
| `GFM-M15` | Math | `cross-engine-latex-compat` | Error | Yes | [Details](docs/rules.md#gfm-m15-cross-engine-latex-compat) |
| `GFM-M16` | Math | `display-linebreak-eol` | Error | Yes | [Details](docs/rules.md#gfm-m16-display-linebreak-eol) |
| `GFM-M17` | Math | `display-line-block-start` | Error | Yes | [Details](docs/rules.md#gfm-m17-display-line-block-start) |
| `GFM-M18` | Math | `non-ascii-in-math` | Warning | Yes | [Details](docs/rules.md#gfm-m18-non-ascii-in-math) |
| `GFM-T01` | Tables | `table-pipe-collision` | Error | Yes | [Details](docs/rules.md#gfm-t01-table-pipe-collision) |
| `GFM-C01` | Code | `fence-nesting-length` | Error | Yes | [Details](docs/rules.md#gfm-c01-fence-nesting-length) |
| `GFM-C02` | Code | `inline-code-backtick-nesting` | Error | Yes | [Details](docs/rules.md#gfm-c02-inline-code-backtick-nesting) |
| `GFM-C03` | Code | `unrendered-math-or-diagram-fence` | Warning | No | [Details](docs/rules.md#gfm-c03-unrendered-math-or-diagram-fence) |
| `GFM-E01` | Emulator | `unexplained-span-diff` | Error | No | [Details](docs/rules.md#gfm-e01-unexplained-span-diff) |
| `GFM-D01` | Diagrams | `mermaid-identifier` | Warning | No | [Details](docs/rules.md#gfm-d01-mermaid-identifier) |
| `GFM-D02` | Diagrams | `fence-boundary-symmetry` | Error | Yes | [Details](docs/rules.md#gfm-d02-fence-boundary-symmetry) |
| `GFM-D03` | Diagrams | `mermaid-newline-linebreak` | Error | Yes | [Details](docs/rules.md#gfm-d03-mermaid-newline-linebreak) |
| `GFM-D04` | Diagrams | `mermaid-label-special-chars` | Error | Yes | [Details](docs/rules.md#gfm-d04-mermaid-label-special-chars) |
| `GFM-D05` | Diagrams | `math-in-mermaid` | Warning | No | [Details](docs/rules.md#gfm-d05-math-in-mermaid) |
| `GFM-D06` | Diagrams | `mermaid-parse` | Error | No | [Details](docs/rules.md#gfm-d06-mermaid-parse) |
| `GFM-S01` | Shell | `unsafe-shell-expansion` | Error | No | [Details](docs/rules.md#gfm-s01-unsafe-shell-expansion) |

---

## Architectural Rationale

`gfm-math-lint` is engineered around the multi-stage parsing pipeline implemented by GitHub's rendering engine (`cmark-gfm` followed by client-side MathJax/KaTeX). Because Markdown parsing executes *before* LaTeX parsing, standard TeX escape sequences can be intercepted and corrupted by CommonMark rules (such as backslash stripping under CommonMark §2.4, HTML tag collision, and emphasis pairing).

For deep architectural explanations and technical decision records, consult:
- 🏛️ **[Architecture & Engine Design](docs/architecture.md)** — Tokenizer zones, compilation sequence, and reverse-offset edit algebra.
- 📋 **[Architectural Decision Records (ADRs)](docs/adr/README.md)** — Context, alternatives, and rationale for architectural decisions.

---

## Contributing & Development

```bash
# Clone the repository
git clone https://github.com/jacobhammond/gfm-math-lint.git
cd gfm-math-lint

# Install development virtualenv and tools with uv
uv sync

# Install local pre-commit git hooks
uv run pre-commit install

# Run all pre-commit hooks across the repository
uv run --no-sync pre-commit run --all-files

# Run the test suite with coverage
uv run pytest

# Run linting and formatting checks
uv run ruff check .
uv run ruff format --check .

# Run strict type checking
uv run mypy src tests --strict

# Run self-checks on repository documents and scripts
uv run gfm-math-lint check README.md CHANGELOG.md CONTRIBUTING.md docs/ .github/
uv run gfm-math-lint check-shell .github/
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines.

---

## License

MIT License. See [LICENSE](https://github.com/jacobhammond/gfm-math-lint/blob/main/LICENSE) for details.
