# gfm-math-lint

[![ci](https://github.com/jacobhammond/gfm-math-lint/actions/workflows/ci.yml/badge.svg)](https://github.com/jacobhammond/gfm-math-lint/actions/workflows/ci.yml)
[![pypi version](https://img.shields.io/pypi/v/gfm-math-lint.svg)](https://pypi.org/project/gfm-math-lint/)
[![license](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/jacobhammond/gfm-math-lint/blob/main/LICENSE)
[![python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)

Zero-dependency, high-performance GitHub Flavored Markdown (GFM) linter and auto-fixer specializing in LaTeX/MathJax math syntax, CommonMark table escaping, fenced code nesting, Mermaid diagram boundaries, shell script expansion guards, and modern AVIF asset recommendations.

---

## Key Features

- **Pure Standard Library**: Zero third-party runtime dependencies. Runs instantly with Python 3.11+.
- **8-Zone Lexical State Machine**: High-fidelity tokenizer classifying document lines into `FRONTMATTER`, `FENCED_CODE`, `INLINE_CODE`, `DISPLAY_MATH`, `INLINE_MATH`, `TABLE`, `COMMENT`, and `PROSE` to eliminate false positives.
- **Reverse-Offset Edit Algebra**: Deterministic bottom-up, right-to-left fix application guaranteeing strict idempotency: $\text{fix}(\text{fix}(c)) \equiv \text{fix}(c)$.
- **Unified Diff & In-Place Fixing**: Inspect exact changes in advance with `--diff` or auto-fix in-place with `fix` / `--fix`.
- **GitHub Rendering Oracle (`verify`)**: Directly audits documents against GitHub's live REST API (`POST /markdown` or `gh api /markdown`) to detect unrendered math in prose, HTML tag collisions, and broken table grids.
- **KaTeX Browser Preview with Zero Red Boxes**: Generates standalone HTML (`--html`) or opens a live browser preview (`--browser`) with automated HTML entity normalization (`&amp;gt;` → `>`) and duplicate MathML clipboard suppression (`output: "html"`).
- **Safe GitHub Commenting**: Post markdown-rendered comments to PRs and issues via `gh` CLI with stdin streaming (`--body-file -`), preventing shell expansion corruption of LaTeX equations.
- **Pre-commit Native**: Exit code contract (`0` clean, `1` violations/fixes, `2` error) designed specifically for CI/CD and git hook workflows.

---

## Documentation Hub

Comprehensive technical guides, API references, and architectural records are maintained in the [`docs/`](docs/README.md) directory:

| Guide | Description |
| :--- | :--- |
| 🏛️ **[Architecture & Engine Design](docs/architecture.md)** | 8-zone lexical state machine, multi-stage compilation pipeline, reverse-offset edit algebra, and verification mechanics. |
| 🐍 **[Python API Reference & Recipes](docs/api.md)** | Programmatic library reference (`Linter`, `LintResult`, `LintConfig`, `Verifier`) with recipes for pytest, CI, and Sphinx/MkDocs. |
| 📖 **[Complete Rule Catalog & Authoring Guide](docs/rules.md)** | In-depth specifications for all 19 rules, CommonMark/KaTeX failure mode mechanics, and custom rule development tutorial. |
| 📋 **[Architectural Decision Records (ADRs)](docs/adr/README.md)** | Technical justifications for zero-dependency stdlib, reverse-offset edit algebra, state-machine tokenization, and live GitHub API verification. |

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

# Preview automated fixes as a unified diff without modifying files
gfm-math-lint check --diff docs/

# Automatically fix violations in-place using the 'fix' shortcut
gfm-math-lint fix docs/ README.md
```

### 2. Scanning Shell Scripts & CI Workflows

Scan bash/sh scripts and GitHub Actions workflows for unsafe double-quoted body arguments (`-b "..."` or `--body "..."`) in `gh` CLI commands that expose LaTeX `$x$` expressions to unintended shell expansion:

```bash
gfm-math-lint check-shell .github/workflows/ scripts/
```

### 3. Safe GitHub Comment Posting

Post comments safely to GitHub issues and pull requests without shell expansion or argument size limits by piping content via stdin directly to `gh`:

```bash
# Preview rendered markdown via GitHub REST API (POST /markdown)
gfm-math-lint comment --preview --file report.md

# Post safely to a pull request
gfm-math-lint comment --pr 42 --file report.md

# Post safely to an issue
gfm-math-lint comment --issue 108 --file notes.md
```

### 4. Semantic Verification & KaTeX Browser Preview

Audit documents directly against GitHub's live REST API rendering oracle or generate a standalone preview:

```bash
# Verify markdown files against GitHub API oracle
gfm-math-lint verify docs/ README.md

# Export full rendered HTML preview
gfm-math-lint verify --html preview.html docs/specification.md

# Launch KaTeX-rendered preview directly in your local default browser
gfm-math-lint verify --browser docs/specification.md
```

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

## Pre-Commit Hook Integration

Add `gfm-math-lint` to your `.pre-commit-config.yaml` to enforce valid equations and secure shell scripts on commit:

```yaml
repos:
  - repo: https://github.com/jacobhammond/gfm-math-lint
    rev: v0.1.1
    hooks:
      # Validates math, table, code fence, and boundary issues
      - id: gfm-math-lint
      # Guards against unsafe shell expansions in CI workflows and scripts
      - id: gfm-shell-lint
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

# Globally ignored rule IDs
ignore = [
    "GFM-I01",  # Allow PNG/JPEG images without AVIF conversion warning
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
| `GFM-M01` | Math | `math-code-fence-to-display` | Error | Yes | [Details](docs/rules.md#gfm-m01-math-code-fence-to-display) |
| `GFM-M02` | Math | `display-math-isolation` | Error | Yes | [Details](docs/rules.md#gfm-m02-display-math-isolation) |
| `GFM-M03` | Math | `text-mode-underscore-escape` | Error | Yes | [Details](docs/rules.md#gfm-m03-text-mode-underscore-escape) |
| `GFM-M04` | Math | `inline-math-whitespace` | Error | Yes | [Details](docs/rules.md#gfm-m04-inline-math-whitespace) |
| `GFM-M05` | Math | `curly-brace-escape` | Error | Yes | [Details](docs/rules.md#gfm-m05-curly-brace-escape) |
| `GFM-M06` | Math | `relational-operator-collision` | Error | Yes | [Details](docs/rules.md#gfm-m06-relational-operator-collision) |
| `GFM-M07` | Math | `asterisk-emphasis-collision` | Error | Yes | [Details](docs/rules.md#gfm-m07-asterisk-emphasis-collision) |
| `GFM-M08` | Math | `disallowed-macro-conversion` | Error | Yes | [Details](docs/rules.md#gfm-m08-disallowed-macro-conversion) |
| `GFM-M09` | Math | `align-environment` | Error | Yes | [Details](docs/rules.md#gfm-m09-align-environment) |
| `GFM-M10` | Math | `currency-dollar-sign` | Warning | Yes | [Details](docs/rules.md#gfm-m10-currency-dollar-sign) |
| `GFM-M11` | Math | `latex-delimiters-conversion` | Error | Yes | [Details](docs/rules.md#gfm-m11-latex-delimiters-conversion) |
| `GFM-M12` | Math | `inline-math-underscore-collision` | Error | Yes | [Details](docs/rules.md#gfm-m12-inline-math-underscore-collision) |
| `GFM-M13` | Math | `math-delimiter-boundaries` | Error | Yes | [Details](docs/rules.md#gfm-m13-math-delimiter-boundaries) |
| `GFM-T01` | Tables | `table-pipe-collision` | Error | Yes | [Details](docs/rules.md#gfm-t01-table-pipe-collision) |
| `GFM-C01` | Code | `nested-fence-length` | Error | Yes | [Details](docs/rules.md#gfm-c01-nested-fence-length) |
| `GFM-C02` | Code | `inline-code-backticks` | Error | Yes | [Details](docs/rules.md#gfm-c02-inline-code-backticks) |
| `GFM-D01` | Diagrams | `mermaid-identifier` | Warning | No | [Details](docs/rules.md#gfm-d01-mermaid-identifier) |
| `GFM-D02` | Diagrams | `code-fence-symmetry` | Error | Yes | [Details](docs/rules.md#gfm-d02-code-fence-symmetry) |
| `GFM-S01` | Shell | `unsafe-shell-expansion` | Error | No | [Details](docs/rules.md#gfm-s01-unsafe-shell-expansion) |
| `GFM-I01` | Images | `image-avif-format` | Warning | No | [Details](docs/rules.md#gfm-i01-image-avif-format) |

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
