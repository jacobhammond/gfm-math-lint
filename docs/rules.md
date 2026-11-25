# Complete Rule Catalog & Authoring Guide

This catalog provides detailed specifications for all 29 rules (plus `GFM-E01` differential fallback) implemented in **gfm-math-lint**, explaining why each failure mode occurs on GitHub, how the auto-fixer repairs it, and how to write custom rules.

---

## Rule Summary Matrix

| Rule ID | Category | Name | Severity | Auto-Fix |
| :--- | :--- | :--- | :---: | :---: |
| [`GFM-M01`](#gfm-m01-math-fence-conversion) | Math | `math-fence-conversion` | Error | Yes |
| [`GFM-M02`](#gfm-m02-display-math-isolation) | Math | `display-math-isolation` | Error | Yes |
| [`GFM-M03`](#gfm-m03-text-mode-underscore-escape) | Math | `text-mode-underscore-escape` | Error | Yes |
| [`GFM-M04`](#gfm-m04-inline-math-whitespace) | Math | `inline-math-whitespace` | Error | Yes |
| [`GFM-M05`](#gfm-m05-backslash-punctuation-escape) | Math | `backslash-punctuation-escape` | Error | Yes |
| [`GFM-M06`](#gfm-m06-relational-operator-collision) | Math | `relational-operator-collision` | Error | Yes |
| [`GFM-M07`](#gfm-m07-asterisk-emphasis-collision) | Math | `asterisk-emphasis-collision` | Error | Yes |
| [`GFM-M08`](#gfm-m08-disallowed-macro) | Math | `disallowed-macro` | Error | Yes |
| [`GFM-M09`](#gfm-m09-align-environment) | Math | `align-environment` | Error | Yes |
| [`GFM-M10`](#gfm-m10-currency-dollar-sign) | Math | `currency-dollar-sign` | Warning | Yes |
| [`GFM-M11`](#gfm-m11-latex-delimiters-conversion) | Math | `latex-delimiters-conversion` | Error | Yes |
| [`GFM-M12`](#gfm-m12-inline-math-underscore-collision) | Math | `inline-math-underscore-collision` | Error | Yes |
| [`GFM-M13`](#gfm-m13-math-delimiter-boundaries) | Math | `math-delimiter-boundaries` | Error | Yes |
| [`GFM-M14`](#gfm-m14-code-syntax-in-math) | Math | `code-syntax-in-math` | Warning | Yes |
| [`GFM-M15`](#gfm-m15-cross-engine-latex-compat) | Math | `cross-engine-latex-compat` | Error | Yes |
| [`GFM-M16`](#gfm-m16-display-linebreak-eol) | Math | `display-linebreak-eol` | Error | Yes |
| [`GFM-M17`](#gfm-m17-display-line-block-start) | Math | `display-line-block-start` | Error | Yes |
| [`GFM-M18`](#gfm-m18-non-ascii-in-math) | Math | `non-ascii-in-math` | Warning | Yes |
| [`GFM-T01`](#gfm-t01-table-pipe-collision) | Tables | `table-pipe-collision` | Error | Yes |
| [`GFM-C01`](#gfm-c01-fence-nesting-length) | Code | `fence-nesting-length` | Error | Yes |
| [`GFM-C02`](#gfm-c02-inline-code-backtick-nesting) | Code | `inline-code-backtick-nesting` | Error | Yes |
| [`GFM-C03`](#gfm-c03-unrendered-math-or-diagram-fence) | Code | `unrendered-math-or-diagram-fence` | Warning | No |
| [`GFM-E01`](#gfm-e01-unexplained-span-diff) | Emulator | `unexplained-span-diff` | Error | No |
| [`GFM-D01`](#gfm-d01-mermaid-identifier) | Diagrams | `mermaid-identifier` | Warning | No |
| [`GFM-D02`](#gfm-d02-fence-boundary-symmetry) | Diagrams | `fence-boundary-symmetry` | Error | Yes |
| [`GFM-D03`](#gfm-d03-mermaid-newline-linebreak) | Diagrams | `mermaid-newline-linebreak` | Error | Yes |
| [`GFM-D04`](#gfm-d04-mermaid-label-special-chars) | Diagrams | `mermaid-label-special-chars` | Error | Yes |
| [`GFM-D05`](#gfm-d05-math-in-mermaid) | Diagrams | `math-in-mermaid` | Warning | No |
| [`GFM-D06`](#gfm-d06-mermaid-parse) | Diagrams | `mermaid-parse` | Error | No |
| [`GFM-S01`](#gfm-s01-unsafe-shell-expansion) | Shell | `unsafe-shell-expansion` | Error | No |

---

## Math & LaTeX Rules (`GFM-M**`)

### GFM-M01: `math-fence-conversion`
- **Issue:** Root-level code blocks fenced with ```` ```math ```` are proprietary GitHub extensions that break in VS Code, Obsidian, Pandoc, and MkDocs. Inside lists and blockquotes, however, ```` ```math ```` is preserved because indented `$$` blocks fail on GitHub.
- **Auto-Fix:** Converts standalone column-0 ```` ```math\n...\n``` ```` into universal `$$\n...\n$$` blocks (when safe and free of CommonMark block interruptions).

### GFM-M02: `display-math-isolation`
- **Issue:** Display math `$$` blocks without blank lines above and below get combined into preceding or following paragraphs under CommonMark §4.5 Lazy Paragraph Continuation, and indented `$$` blocks inside lists or blockquotes fail to compile on GitHub.
- **Auto-Fix:** Breaks indented/list-nested `$$` blocks out to column 0, adds blank lines around `$$` delimiters, and removes internal blank lines.

### GFM-M03: `text-mode-underscore-escape`
- **Issue:** In LaTeX, underscores inside `\text{...}` or `\mathrm{...}` cause CommonMark emphasis collisions when unescaped, and double-escaped `\\_` crashes local KaTeX (`ParseError: Expected 'EOF', got '_'`).
- **Auto-Fix:** Replaces underscores inside `\text{...}` / `\mathrm{...}` embedded in equations with `-` (while standalone `\text{snake_case}` spans are converted to inline code backticks by `GFM-M14`).

### GFM-M04: `inline-math-whitespace`
- **Issue:** GitHub's inline math parser rejects dollar delimiters with inner whitespace (e.g. `$ x $`).
- **Auto-Fix:** Trims leading and trailing inner whitespace (`$ x $` → `$x$`).

### GFM-M05: `backslash-punctuation-escape`
- **Issue:** CommonMark §2.4 consumes backslashes before ASCII punctuation inside `$...$` and `$$...$$` before MathJax sees them, turning `\{` into `{`, `\,` into `,`, `\|` into `|`, etc.
- **Auto-Fix:** Converts backslash-punctuation sequences to letter-named macros: `\{` → `\lbrace`, `\}` → `\rbrace`, `\,` → `\thinspace`, `\:` → `\medspace`, `\;` → `\thickspace`, `\!` → `\negthinspace`, and `\|` → `\Vert` (or `\left\lVert` / `\right\rVert`).

### GFM-M06: `relational-operator-collision`
- **Issue:** In math expressions like `$x < y$`, CommonMark's inline HTML scanner mistakes `<y` for an opening HTML tag (e.g. `<y>`), corrupting the equation and surrounding prose.
- **Auto-Fix:** Converts relational `<` to `\lt` when followed by an ASCII letter (skipping valid HTML tags).

### GFM-M07: `asterisk-emphasis-collision`
- **Issue:** Raw asterisks inside math expressions (e.g. `$A^* B^*$`) trigger CommonMark emphasis parsing (`<em>...</em>`), destroying the formula.
- **Auto-Fix:** Replaces raw asterisks with `\ast`.

### GFM-M08: `disallowed-macro`
- **Issue:** KaTeX does not support `\operatorname{...}` or `\operatorname*{...}` in default rendering environments.
- **Auto-Fix:** Converts `\operatorname{name}` to `\mathop{\mathrm{name}}` and `\operatorname*{name}` to `\mathop{\mathrm{name}}\limits`.

### GFM-M09: `align-environment`
- **Issue:** Standalone `\begin{align}` is unsupported in KaTeX without full AMS-LaTeX document encapsulation.
- **Auto-Fix:** Replaces `align` and `align*` environments with `aligned`.

### GFM-M10: `currency-dollar-sign`
- **Issue:** Multiple literal currency dollar signs on a prose line (e.g., `"Costs $10 to $20"`) trigger accidental inline math rendering.
- **Auto-Fix:** Backslash-escapes literal dollar signs (`\$10 to \$20`).

### GFM-M11: `latex-delimiters-conversion`
- **Issue:** Standard LaTeX delimiters `\[ ... \]` and `\( ... \)` are not recognized by GitHub's math renderer and their backslashes get stripped by CommonMark §2.4.
- **Auto-Fix:** Converts `\[ ... \]` to `$$...$$` and `\( ... \)` to `$ ... $`.

### GFM-M12: `inline-math-underscore-collision`
- **Issue:** Flanking underscores in math expressions (e.g., `$P_{\text{primary}}$ and $P_{\text{secondary}}$`) trigger CommonMark §6.2 emphasis pairing (`_..._`), replacing formulas with italics. Intra-word subscripts (`$a_1 + b_2$`) and adjacent inline code spans are ignored.
- **Auto-Fix:** Escapes colliding underscores (`\_`) for `dual`/`github` targets or space-pads (` _ `) for the `vscode` target.

### GFM-M13: `math-delimiter-boundaries`
- **Issue:** GitHub's inline math parser enforces strict boundary conditions:
  1. Hyphenated math pairs like `$A$–$B$` fail to parse because opening `$` requires whitespace/parenthesis.
  2. Glued opening delimiters like `base-$e$` or `x$y$` fail to open math mode.
  3. Trailing units like `$15\ ^\circ$C` fail to close because the closing `$` cannot be followed by an ASCII alphanumeric character.
  4. Closing `$` directly touching `)` in nested parentheses causes delimiter collisions.
- **Auto-Fix:** Combines hyphenated pairs (`$A\text{–}B$`), inserts spaces at glued opening/closing delimiters (`base $e$`, `$15\ ^\circ$ C`), and spaces parenthesis boundaries.

### GFM-M14: `code-syntax-in-math`
- **Issue:** Programming function identities (e.g. `$\text{fix}(\text{fix}(c)) \equiv \text{fix}(c)$`) cause KaTeX MathML vertical stacking artifacts, and `snake_case` code/register identifiers inside `\text{...}` break KaTeX or trigger CommonMark collisions.
- **Auto-Fix:** Converts code function identities (`fix(fix(c)) == fix(c)`) and standalone `$\text{snake_case}$` identifiers into inline code backticks; flags embedded identifiers alongside `GFM-M03`.

### GFM-M15: `cross-engine-latex-compat`
- **Issue:** Unicode dashes (`–`, `—`) inside math crash KaTeX, HTML pipe entities (`&#124;`) inside `$...$` are not decoded before MathJax/KaTeX, and bare `%` or single-escaped `\%` inside `$...$` / `$$...$$` is stripped by CommonMark to a TeX line comment (`%`), silently truncating formulas.
- **Auto-Fix:** Replaces Unicode dashes with `-`, replaces HTML pipe entities with `\vert`, and wraps inline `$...$` containing `%` / `\%` in GFM backtick math (`` $`...\%...`$ ``).

### GFM-M16: `display-linebreak-eol`
- **Issue:** GitHub CommonMark collapses mid-line `\\` inside `$$...$$` into a single `\`, collapsing single-line matrices into one row. Only `\\` at the end of a line survives.
- **Auto-Fix:** Inserts a line break immediately after mid-line `\\` inside display math blocks.

### GFM-M17: `display-line-block-start`
- **Issue:** Lines inside `$$...$$` starting with CommonMark block markers (`+ `, `- `, `* `, `> `, `#`, `1. `, or setext `===`/`---`) interrupt the display math block on GitHub and shatter the equation into lists or headings.
- **Auto-Fix:** Prefixes leading `+ ` / `- ` continuation operators with `{}` (`{}+ `, `{}- `); flags setext underlines, headings, and ordered lists as errors.

### GFM-M18: `non-ascii-in-math`
- **Issue:** Non-ASCII scientific glyphs (`µ`, `°`, `²`, `³`, `·`, `−`, Unicode Greek) inside math trigger KaTeX strict-mode `unknownSymbol` warnings.
- **Auto-Fix:** Converts non-ASCII characters to portable LaTeX macros (`\text{µs}` → `\mu\text{s}`, `°` → `^\circ`, `α` → `\alpha`, etc.).

---

## Table, Code, and Diagram Rules

### GFM-T01: `table-pipe-collision`
- **Issue:** Raw pipe characters (`|`, `\|`, `||`) inside table math or code spans fracture Markdown table columns, while HTML pipe entities (`&#124;`) inside `$...$` fail in GitHub MathJax and KaTeX.
- **Auto-Fix:** Replaces paired bars and HTML pipe entities in table math with `\lvert ... \rvert` or `\lVert ... \rVert`, unpaired pipes with `\vert`, and code-span pipes with `\|`.

### GFM-C01: `fence-nesting-length`
- **Issue:** Per CommonMark §4.5, outer code blocks containing nested code fences must use strictly longer backtick runs (e.g. four or five backticks).
- **Auto-Fix:** Lengthens outer code block delimiters to exceed inner fences.

### GFM-C02: `inline-code-backtick-nesting`
- **Issue:** Inline code spans containing literal backticks must use multi-backtick delimiters per CommonMark §6.3.
- **Auto-Fix:** Converts surrounding delimiters to double backticks (`` `code` ``).

### GFM-C03: `unrendered-math-or-diagram-fence`
- **Issue:** Mathematical equations (`dU/dt = -γ U + Σ P_k`) or 2D ASCII box-drawing topology diagrams placed inside unlabelled or `text`/`plaintext` code fences are skipped by Markdown math/diagram renderers.
- **Remediation:** Convert equations to `$$ ... $$` display math or ASCII diagrams to ```` ```mermaid ```` blocks (directory `tree` listings are excluded).

### GFM-E01: `unexplained-span-diff`
- **Issue:** Fallback differential emulator diagnostic emitted when `emulate_gfm_document()` detects a math span drop or CommonMark mutation not already covered by `GFM-M01`–`GFM-M18` or `GFM-T01`.
- **Remediation:** Inspect the reported line with `gfm-math-lint verify` and rewrite using the GFM safe subset (or suppress with `<!-- gfm-math-lint-disable-next-line GFM-E01 -->`).

### GFM-D01: `mermaid-identifier`
- **Issue:** Mermaid diagram node labels containing whitespace or special characters without explicit quotes cause parsing failures.
- **Remediation:** Enforces alphanumeric IDs and quoted labels: `id["Node Title"]`.

### GFM-D02: `fence-boundary-symmetry`
- **Issue:** Code blocks with mismatched opening and closing fence lengths or characters violate CommonMark block structure.
- **Auto-Fix:** Synchronizes closing fence characters and lengths to match the opening fence.

### GFM-D03: `mermaid-newline-linebreak`
- **Issue:** Literal `\n` escape sequences inside Mermaid node or subgraph labels render as raw `\n` text on GitHub instead of line breaks.
- **Auto-Fix:** Replaces literal `\n` inside Mermaid labels with `<br>`.

### GFM-D04: `mermaid-label-special-chars`
- **Issue:** Unquoted Mermaid node labels containing `( ) { } |` and pipe-delimited edge labels containing an internal `|` (e.g. `-->|"U = |a|²"|`) cause Mermaid parser errors.
- **Auto-Fix:** Quotes unquoted node labels containing special characters (`A["Value (dB)"]`); flags internal pipes in `-->|...|` edge labels for `-- "..." -->` syntax.

### GFM-D05: `math-in-mermaid`
- **Issue:** GitHub's Mermaid renderer does not typeset LaTeX `$...$` or macros inside diagram labels.
- **Remediation:** Replace LaTeX math in Mermaid labels with Unicode symbols (`Δ`, `α`, `²`).

### GFM-D06: `mermaid-parse`
- **Issue:** Syntactically invalid Mermaid diagrams fail to render on GitHub and in local previewers.
- **Remediation:** Opportunistically validates Mermaid blocks using `mmdc` (`@mermaid-js/mermaid-cli`) with desktop-quiet `chrome-headless-shell` when installed on `PATH`; gracefully skips when `mmdc` or a headless browser is absent.

### GFM-S01: `unsafe-shell-expansion`
- **Issue:** Passing markdown bodies with double quotes (`-b "..."` or `--body "..."` / `--notes "..."`) in `gh pr comment`, `gh issue comment`, `gh release create`, `gh issue create`, or `gh pr create` commands in bash scripts or CI workflows exposes LaTeX `$x$` expressions and math variables to unintended shell variable expansion and subshell execution (`$(...)`).
- **Remediation:** Use stdin streaming or single-quoted heredocs: `gh issue create --body-file - < report.md` or `gh pr create --body-file - << 'EOF'`.

---

## Rule Suppression Syntax

To disable a rule for a specific line or block in Markdown:

```markdown
<!-- gfm-math-lint-disable GFM-M05 -->
$$
\left\{ x \in \mathbb{R} \right\}
$$
<!-- gfm-math-lint-enable GFM-M05 -->
```

Or disable a rule for the next line only:

```markdown
<!-- gfm-math-lint-disable-next-line GFM-M06 -->
$x < y$
```

---

## Authoring Custom Rules

You can extend `gfm-math-lint` with custom rules by subclassing `gfm_math_lint.rules.base.Rule`:

```python
from gfm_math_lint.rules.base import Rule, Violation, Severity
from gfm_math_lint.tokenizer import Token, ZoneType

class RuleCustom01(Rule):
    id = "GFM-X01"
    name = "custom-math-check"
    description = "Example custom rule checking math expressions."
    severity = Severity.WARNING

    def check_token(self, token: Token, file_path: str) -> list[Violation]:
        violations = []
        if token.zone_type == ZoneType.INLINE_MATH and "\\foo" in token.content:
            violations.append(
                Violation(
                    rule_id=self.id,
                    rule_name=self.name,
                    message="Use of \\foo is deprecated in math formulas.",
                    line=token.line,
                    col=token.col,
                    severity=self.severity,
                )
            )
        return violations
```
