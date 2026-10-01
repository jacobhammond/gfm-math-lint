# gfm-math-lint

[![ci](https://github.com/jacobhammond/gfm-math-lint/actions/workflows/ci.yml/badge.svg)](https://github.com/jacobhammond/gfm-math-lint/actions/workflows/ci.yml)
[![pypi version](https://img.shields.io/pypi/v/gfm-math-lint.svg)](https://pypi.org/project/gfm-math-lint/)
[![license](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/jacobhammond/gfm-math-lint/blob/main/LICENSE)
[![python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)

Zero-dependency, high-performance GitHub Flavored Markdown (GFM) linter and auto-fixer specializing in LaTeX/MathJax math syntax, CommonMark table escaping, fenced code nesting, Mermaid diagram boundaries, shell script expansion guards, and modern AVIF asset recommendations.

---

## Key Features

- **Pure Standard Library**: Zero third-party runtime dependencies. Runs instantly with Python 3.11+.
- **8-Zone Lexical State Machine**: High-fidelity tokenizer classifying document lines into `FRONTMATTER`, `FENCED_CODE`, `INLINE_CODE`, `DISPLAY_MATH`, `INLINE_MATH`, `TABLE`, `COMMENT`, and `PROSE`. Prevents false positives by ensuring rules only inspect their designated semantic zones.
- **Reverse-Offset Edit Algebra**: Deterministic bottom-up, right-to-left fix application guaranteeing idempotency: `fix(fix(c)) ≡ fix(c)`.
- **Unified Diff & In-Place Fixing**: Inspect exact changes in advance with `--diff` or auto-fix in-place with `fix` / `--fix`.
- **GitHub Rendering Oracle (`verify`)**: Directly audits documents against GitHub's live REST API (`POST /markdown` or `gh api /markdown`) to detect unrendered math in prose, HTML tag collisions, and broken table grids.
- **KaTeX Browser Preview with Zero Red Boxes**: Generates standalone HTML (`--html`) or opens a live browser preview (`--browser`) with automated HTML entity normalization (`&amp;gt;` → `>`) and duplicate MathML clipboard suppression (`output: "html"`), delivering clean math preview across Firefox, Chrome, and Safari.
- **Safe GitHub Commenting**: Post markdown-rendered comments to PRs and issues via `gh` CLI with stdin streaming (`--body-file -`), preventing shell expansion corruption of LaTeX equations, with live `--preview` rendering.
- **Pre-commit Native**: Exit code contract (`0` clean, `1` violations/fixes, `2` error) designed specifically for CI/CD and git hook workflows.


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

## Usage

### 1. Checking & Fixing Markdown Files

Check all markdown files in a directory or individually, preview diffs, and automatically fix violations:

```bash
# Check files for violations
gfm-math-lint check docs/ README.md

# Output violations in GitHub Actions workflow command format (::warning / ::error)
gfm-math-lint check --format github docs/

# Specify an explicit configuration file
gfm-math-lint check --config pyproject.toml docs/

# Preview automated fixes as a unified diff without modifying files
gfm-math-lint check --diff docs/

# Automatically fix violations in-place using the 'fix' shortcut
gfm-math-lint fix docs/ README.md

# Or equivalently via the check subcommand:
gfm-math-lint check --fix docs/ README.md
```

### 2. Scanning Shell Scripts & Workflows

Scan bash/sh scripts and GitHub Actions workflow files for unsafe double-quoted body arguments (`-b "..."` or `--body "..."`) in `gh pr comment` / `gh issue comment` commands that expose LaTeX `$x$` expressions to shell expansion:

```bash
gfm-math-lint check-shell .github/workflows/ scripts/
```

### 3. Safe GitHub Comment Posting

Post comments safely without shell expansion or argument size limits by piping content via stdin directly to `gh`:

```bash
# Preview rendered markdown via GitHub REST API (POST /markdown)
gfm-math-lint comment --preview --file report.md

# Post safely to a pull request
gfm-math-lint comment --pr 42 --file report.md

# Post safely to an issue
gfm-math-lint comment --issue 108 --file notes.md
```

### 4. Semantic Verification & Browser Preview (GitHub API Oracle)

Verify your documents directly against GitHub's live REST API markdown rendering oracle (`POST /markdown` or `gh api /markdown`) to catch unrendered math, HTML tag collisions, or table fracturing:

```bash
# Verify all markdown files against GitHub API oracle
gfm-math-lint verify docs/ README.md

# Authenticate with an explicit GitHub token (or uses $GITHUB_TOKEN / $GH_TOKEN)
gfm-math-lint verify --token "$GITHUB_TOKEN" docs/

# Verify and export full rendered HTML preview
gfm-math-lint verify --html preview.html docs/specification.md

# Verify and immediately launch KaTeX-rendered preview in local web browser
# (Features automated entity normalization & MathML duplicate clipboard suppression)
gfm-math-lint verify --browser docs/specification.md
```

---

## Rule Catalog

### Math & LaTeX Rules (`GFM-M**`)

| Rule ID | Name | Severity | Auto-Fix | Description |
| :--- | :--- | :---: | :---: | :--- |
| `GFM-M01` | `math-code-fence-to-display` | Error | Yes | Convert `` ```math `` code fences to standalone `$$` display math blocks. |
| `GFM-M02` | `display-math-isolation` | Error | Yes | Enforce display math `$$` opening/closing delimiters sit on isolated lines with blank line padding and no internal blanks. |
| `GFM-M03` | `text-mode-underscore-escape` | Error | Yes | Enforce double-escaped underscores (`\\_`) inside text-mode LaTeX macros (`\text{...}`, `\mathrm{...}`). |
| `GFM-M04` | `inline-math-whitespace` | Error | Yes | Strip leading and trailing inner whitespace from inline math delimiters (`$ x $` → `$x$`). |
| `GFM-M05` | `curly-brace-escape` | Error | Yes | Convert `\{` and `\}` delimiters in math expressions to `\lbrace` and `\rbrace` (e.g. `\left\{` → `\left\lbrace`). |
| `GFM-M06` | `relational-operator-collision` | Error | Yes | Encode relational operator (`<` to `\lt`) before letters in math to avoid HTML parser entity consumption. |
| `GFM-M07` | `asterisk-emphasis-collision` | Error | Yes | Convert raw asterisks (`*`) in superscripts, subscripts, and expressions to `\ast` to prevent GFM emphasis stripping. |
| `GFM-M08` | `disallowed-macro-conversion` | Error | Yes | Replace `\operatorname{...}` with `\mathop{\mathrm{...}}` and `\operatorname*{...}` with `\mathop{\mathrm{...}}\limits` to preserve operator limits. |
| `GFM-M09` | `align-environment` | Error | Yes | Replace unsupported `align`/`align*` environments with KaTeX `aligned` environment. |
| `GFM-M10` | `currency-dollar-sign` | Warning | Yes | Escape currency dollar signs on prose lines containing multiple dollars or coexisting with math (`$10 to $20` → `\$10 to \$20`). |
| `GFM-M11` | `latex-delimiters-conversion` | Error | Yes | Convert standard LaTeX display delimiters (`\[ ... \]`) to `$$` and inline delimiters (`\( ... \)`) to `$`. |
| `GFM-M12` | `inline-math-underscore-collision` | Error | Yes | Escape unescaped underscores (`\_`) in inline and single-line display dollar math spans to prevent CommonMark emphasis collision (`<em>...</em>`). |
| `GFM-M13` | `math-delimiter-boundaries` | Error | Yes | Enforce GitHub-compliant math delimiter boundaries: combine hyphenated math pairs (`$A$–$B$` → `$A\text{–}B$`), separate glued units (`$15\ ^\circ$C` → `$15\ ^\circ$ C`), and prevent bracket collisions (`$G(L)$)` → `$G(L)$ )`). |

### Table Rules (`GFM-T**`)

| Rule ID | Name | Severity | Auto-Fix | Description |
| :--- | :--- | :---: | :---: | :--- |
| `GFM-T01` | `table-pipe-collision` | Error | Yes | Escape raw pipes in table math spans (`&#124;`) and code spans (`\|`) to prevent column fracturing. |

### Code & Fence Nesting Rules (`GFM-C**`)

| Rule ID | Name | Severity | Auto-Fix | Description |
| :--- | :--- | :---: | :---: | :--- |
| `GFM-C01` | `nested-fence-length` | Error | Yes | Ensure outer fenced code blocks enclosing inner backtick fences use strictly longer backtick runs per CommonMark §4.5. |
| `GFM-C02` | `inline-code-backticks` | Error | Yes | Ensure inline code spans containing backticks use multi-backtick delimiters (`` `...` ``) per CommonMark §6.3. |

### Diagram Rules (`GFM-D**`)

| Rule ID | Name | Severity | Auto-Fix | Description |
| :--- | :--- | :---: | :---: | :--- |
| `GFM-D01` | `mermaid-identifier` | Warning | No | Enforce alphanumeric IDs for Mermaid subgraphs and multi-word node labels with explicit quoted titles. |
| `GFM-D02` | `code-fence-symmetry` | Error | Yes | Require identical opening and closing fence lengths and characters for code blocks. |

### Shell Scanner Rules (`GFM-S**`)

| Rule ID | Name | Severity | Auto-Fix | Description |
| :--- | :--- | :---: | :---: | :--- |
| `GFM-S01` | `unsafe-shell-expansion` | Error | No | Scan shell scripts and workflows for unsafe double-quoted body arguments in `gh` CLI invocations. |

### Asset & Image Rules (`GFM-I**`)

| Rule ID | Name | Severity | Auto-Fix | Description |
| :--- | :--- | :---: | :---: | :--- |
| `GFM-I01` | `image-avif-format` | Warning | No | Enforce modern `.avif` format for markdown images and figures. |

---

## Architectural Rationale & Standards Alignment

`gfm-math-lint` is engineered around the multi-stage parsing pipeline implemented by GitHub's rendering engine (`cmark-gfm` followed by client-side MathJax). Understanding this compilation model clarifies why these rules exist, why specific conversions are preferred, and how they align with authoritative web standards.

### 1. The Multi-Stage GFM Parsing Pipeline

When GitHub processes a Markdown document containing mathematical formulas, it executes stages in strict sequence:
1. **CommonMark / GFM Inline Parser (`cmark-gfm`)**: Parses block structure, escapes, links, code spans, HTML tags, and emphasis.
2. **HTML Sanitization**: Filters and scrubs disallowed HTML elements and attributes.
3. **Client-Side Math Engine (MathJax)**: Identifies delimited math zones (`$...$` and `$$...$$`) and compiles LaTeX syntax into HTML/MathML DOM nodes.

Because **Markdown parsing executes before LaTeX parsing**, standard TeX escaping conventions can be intercepted and destroyed by CommonMark.

### 2. CommonMark §2.4 Backslash Escapes

Per [CommonMark Spec 0.30 §2.4 (Backslash escapes)](https://spec.commonmark.org/0.30/#backslash-escapes):
> Any ASCII punctuation character may be backslash-escaped:
> `! " # $ % & ' ( ) * + , - . / : ; < = > ? @ [ \ ] ^ _ ` { | } ~`
> Backslashes before other characters are treated as literal backslashes.

This rule directly dictates the design of several core rules:
- **`GFM-M03` (`text-mode-underscore-escape`)**: In LaTeX, an underscore inside text mode is escaped as `\_` (e.g. `\text{ave\_shift}`). However, because `_` is one of CommonMark's 32 ASCII punctuation characters, `cmark-gfm` strips the backslash during stage 1. KaTeX receives `\text{ave_shift}`, triggering a fatal syntax error. `GFM-M03` enforces double-escaped backslashes (`\\_`), ensuring one backslash survives stage 1 to reach KaTeX as `\_`.
- **`GFM-M05` (`curly-brace-escape`)**: In TeX, dynamic curly braces are written `\left\{ ... \right\}`. Because `{` and `}` are CommonMark ASCII punctuation characters, the backslashes are consumed during stage 1. KaTeX receives `\left{`, throwing `Missing or unrecognized delimiter for \left`. `GFM-M05` converts `\{` and `\}` to `\lbrace` and `\rbrace` (e.g. `\left\lbrace ... \right\rbrace`), which do not rely on fragile punctuation escapes.
- **CommonMark §6.1 / §6.3 Immunity of Code Spans**: Per [CommonMark Spec 0.30 §6.1](https://spec.commonmark.org/0.30/#code-spans), *"Backslash escapes do not work in code spans."* Inside backticks, backslashes are preserved literally. That is why backtick math (`` $`\text{ave_shift}`$ ``) is natively immune to backslash stripping, whereas standard dollar math requires double escaping.

### 3. Delimiter Portability & Standards Alignment

#### `GFM-M01`: Why Convert `` ```math `` to `$$`?
[GitHub's official guide on writing mathematical expressions](https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/writing-mathematical-expressions) documents ```` ```math ```` code fences as an alternative display block syntax.
However, `gfm-math-lint` converts ```` ```math ```` to canonical `$$\n...\n$$` blocks for cross-platform portability:
- Outside GitHub's proprietary web view, tools such as **VS Code Markdown Preview, PyCharm, Obsidian, Jupyter Notebooks, Pandoc, MkDocs (Material), and Sphinx** do *not* recognize ```` ```math ```` as math blocks, rendering them as unrendered code fences.
- Converting to standalone `$$` ensures 100% universal rendering across all major Markdown and LaTeX tooling while rendering flawlessly on GitHub.

#### `GFM-M11`: Why Convert `\[ ... \]` and `\( ... \)`?
Standard LaTeX documents written for paper publishing or ArXiv use `\[ ... \]` for display math and `\( ... \)` for inline math.
- GitHub's Markdown parser does **not** recognize `\[ ... \]` or `\( ... \)` as math delimiters.
- Furthermore, per CommonMark §2.4, `[` and `(` are ASCII punctuation characters. When `cmark-gfm` runs, it strips the backslashes, leaving raw unrendered text (e.g., `[ x = 1 ]` or `( x + y )`).
- `GFM-M11` converts standard LaTeX delimiters to GitHub-compatible delimiters (`$$` and `$`).

#### `GFM-M02`: Display Math Blank Line Isolation
GitHub Docs notes that display blocks can be preceded by a backslash newline. However, `gfm-math-lint` enforces full blank line padding above and below `$$` display blocks:
- CommonMark §4.5 (Lazy Paragraph Continuation) allows lines following a paragraph to be grouped into the same block unless separated by a blank line.
- Enforcing blank lines guarantees clear AST separation and satisfies common Markdown linters such as `markdownlint` (rule MD031).

#### `GFM-M10`: Currency Dollar Signs (`\$` vs `<span>$</span>`)
GitHub Docs mentions using `<span>$</span>` to prevent literal dollar signs from triggering math rendering.
`gfm-math-lint` deliberately enforces backslash escaping (`\$` per CommonMark §2.4) instead:
- `\$` maintains pure, readable Markdown without polluting documents with raw HTML tags.
- Both GitHub and CommonMark officially specify `\$` as an escaped literal character.

#### `GFM-M13`: GitHub Delimiter Boundary & Punctuation Constraints
GitHub's inline math parser enforces strict boundary conditions on opening and closing `$` delimiters:
- **Opening `$` Delimiter Boundary:** An opening `$` is only parsed as math if preceded by whitespace, start-of-line, or an opening parenthesis `(`. Preceding punctuation characters such as hyphens (`-`), en-dashes (`–`), em-dashes (`—`), slashes (`/`), or brackets (`[`) cause GitHub to reject the `$` as math. Expressions like `$A$–$B$` leave `–$B$` as plain text. `GFM-M13` combines compound expressions into `$A\text{–}B$`.
- **Closing `$` Delimiter Boundary:** A closing `$` is rejected if immediately followed by an ASCII letter or digit (`[a-zA-Z0-9]`). Units glued to math expressions (`$15\ ^\circ$C`, `$0.759$dB`) fail to close and render as literal text. `GFM-M13` automatically separates trailing alphanumeric units with a space (`$15\ ^\circ$ C`, `$0.759$ dB`).
- **Parenthesis Collisions:** In nested parenthetical prose like `($A = B$ instead of $G(L)$)`, the closing `$` directly preceding `)` collides with bracket matching in `cmark-gfm`. `GFM-M13` inserts a space (`$G(L)$ )`) ensuring flawless delimiter recognition.

---

## Configuration

Configure `gfm-math-lint` in your project's `pyproject.toml` under `[tool.gfm-math-lint]`:

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

---

## Inline Rule Suppression

Suppress rules directly in Markdown files using HTML comments:

### Multi-line Block Suppression

```markdown
<!-- gfm-math-lint-disable GFM-M02, GFM-M04 -->
$$
E = mc^2 \\
$$
<!-- gfm-math-lint-enable GFM-M02, GFM-M04 -->
```

### Next-Line Suppression

```markdown
<!-- gfm-math-lint-disable-next-line GFM-M10 -->
The price varied between $10 and $20 per unit.
```

Omit the rule IDs to disable or enable all rules for the target scope:

```markdown
<!-- gfm-math-lint-disable-next-line -->
| Metric | $||x|| < 1e-9$ |
```

---

## Pre-Commit Hook Integration

### Using `gfm-math-lint` in Your Repository

Add `gfm-math-lint` to your `.pre-commit-config.yaml` to validate equations and guard shell scripts:

```yaml
repos:
  - repo: https://github.com/jacobhammond/gfm-math-lint
    rev: v0.1.0
    hooks:
      # Validates math, table, code fence, and boundary issues
      - id: gfm-math-lint
      # Guards against unsafe shell expansions in CI workflows and scripts
      - id: gfm-shell-lint
```

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

---

## License

MIT License. See [LICENSE](https://github.com/jacobhammond/gfm-math-lint/blob/main/LICENSE) for details.
