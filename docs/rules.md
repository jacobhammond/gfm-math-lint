# Complete Rule Catalog & Authoring Guide

This catalog provides detailed specifications for all 19 rules implemented in **gfm-math-lint**, explaining why each failure mode occurs on GitHub, how the auto-fixer repairs it, and how to write custom rules.

---

## Rule Summary Matrix

| Rule ID | Category | Name | Severity | Auto-Fix |
| :--- | :--- | :--- | :---: | :---: |
| [`GFM-M01`](#gfm-m01-math-code-fence-to-display) | Math | `math-code-fence-to-display` | Error | Yes |
| [`GFM-M02`](#gfm-m02-display-math-isolation) | Math | `display-math-isolation` | Error | Yes |
| [`GFM-M03`](#gfm-m03-text-mode-underscore-escape) | Math | `text-mode-underscore-escape` | Error | Yes |
| [`GFM-M04`](#gfm-m04-inline-math-whitespace) | Math | `inline-math-whitespace` | Error | Yes |
| [`GFM-M05`](#gfm-m05-curly-brace-escape) | Math | `curly-brace-escape` | Error | Yes |
| [`GFM-M06`](#gfm-m06-relational-operator-collision) | Math | `relational-operator-collision` | Error | Yes |
| [`GFM-M07`](#gfm-m07-asterisk-emphasis-collision) | Math | `asterisk-emphasis-collision` | Error | Yes |
| [`GFM-M08`](#gfm-m08-disallowed-macro-conversion) | Math | `disallowed-macro-conversion` | Error | Yes |
| [`GFM-M09`](#gfm-m09-align-environment) | Math | `align-environment` | Error | Yes |
| [`GFM-M10`](#gfm-m10-currency-dollar-sign) | Math | `currency-dollar-sign` | Warning | Yes |
| [`GFM-M11`](#gfm-m11-latex-delimiters-conversion) | Math | `latex-delimiters-conversion` | Error | Yes |
| [`GFM-M12`](#gfm-m12-inline-math-underscore-collision) | Math | `inline-math-underscore-collision` | Error | Yes |
| [`GFM-M13`](#gfm-m13-math-delimiter-boundaries) | Math | `math-delimiter-boundaries` | Error | Yes |
| [`GFM-T01`](#gfm-t01-table-pipe-collision) | Tables | `table-pipe-collision` | Error | Yes |
| [`GFM-C01`](#gfm-c01-nested-fence-length) | Code | `nested-fence-length` | Error | Yes |
| [`GFM-C02`](#gfm-c02-inline-code-backticks) | Code | `inline-code-backticks` | Error | Yes |
| [`GFM-D01`](#gfm-d01-mermaid-identifier) | Diagrams | `mermaid-identifier` | Warning | No |
| [`GFM-D02`](#gfm-d02-code-fence-symmetry) | Diagrams | `code-fence-symmetry` | Error | Yes |
| [`GFM-S01`](#gfm-s01-unsafe-shell-expansion) | Shell | `unsafe-shell-expansion` | Error | No |
| [`GFM-I01`](#gfm-i01-image-avif-format) | Images | `image-avif-format` | Warning | No |

---

## Math & LaTeX Rules (`GFM-M**`)

### GFM-M01: `math-code-fence-to-display`
- **Issue:** Code blocks fenced with ```` ```math ```` are proprietary GitHub extensions that break in VS Code, Obsidian, Pandoc, and MkDocs.
- **Auto-Fix:** Converts ```` ```math\n...\n``` ```` into universal `$$\n...\n$$` blocks.

### GFM-M02: `display-math-isolation`
- **Issue:** Display math `$$` blocks without blank lines above and below get combined into preceding or following paragraphs under CommonMark §4.5 Lazy Paragraph Continuation.
- **Auto-Fix:** Adds blank lines around `$$` delimiters and removes internal blank lines.

### GFM-M03: `text-mode-underscore-escape`
- **Issue:** In LaTeX, text-mode underscores are written `\_`. However, CommonMark §2.4 treats `_` as an ASCII punctuation character, causing `cmark-gfm` to strip the backslash during Markdown parsing. KaTeX receives `\text{ave_shift}`, triggering a fatal parse error.
- **Auto-Fix:** Replaces `\_` with double-escaped `\\_` inside `\text{...}` and `\mathrm{...}` macros.

### GFM-M04: `inline-math-whitespace`
- **Issue:** GitHub's inline math parser rejects dollar delimiters with inner whitespace (e.g. `$ x $`).
- **Auto-Fix:** Trims leading and trailing inner whitespace (`$ x $` → `$x$`).

### GFM-M05: `curly-brace-escape`
- **Issue:** In LaTeX, dynamic curly braces are written `\left\{ ... \right\}`. CommonMark §2.4 consumes the backslashes before `{` and `}`, causing KaTeX to receive `\left{` and crash.
- **Auto-Fix:** Converts `\{` and `\}` to `\lbrace` and `\rbrace`.

### GFM-M06: `relational-operator-collision`
- **Issue:** In math expressions like `$x < y$`, CommonMark's inline HTML scanner mistakes `<y` for an opening HTML tag (e.g. `<y>`), corrupting the equation and surrounding prose.
- **Auto-Fix:** Converts relational `<` to `\lt` when followed by an ASCII letter.

### GFM-M07: `asterisk-emphasis-collision`
- **Issue:** Raw asterisks inside math expressions (e.g. `$A^* B^*$`) trigger CommonMark emphasis parsing (`<em>...</em>`), destroying the formula.
- **Auto-Fix:** Replaces raw asterisks with `\ast`.

### GFM-M08: `disallowed-macro-conversion`
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
- **Issue:** Underscores in math expressions (e.g., `$x_1 + x_2$`) trigger CommonMark emphasis pairing (`_..._`), replacing formulas with italics.
- **Auto-Fix:** Escapes unescaped underscores (`\_`) in inline math spans.

### GFM-M13: `math-delimiter-boundaries`
- **Issue:** GitHub's inline math parser enforces strict boundary conditions:
  1. Hyphenated math pairs like `$A$–$B$` fail to parse because opening `$` requires whitespace/parenthesis.
  2. Trailing units like `$15\ ^\circ$C` fail to close because the closing `$` cannot be followed by an ASCII alphanumeric character.
  3. Closing `$` directly touching `)` in nested parentheses causes delimiter collisions.
- **Auto-Fix:** Combines hyphenated pairs (`$A\text{–}B$`), separates trailing units (`$15\ ^\circ$ C`), and spaces parenthesis boundaries.

---

## Table, Code, and Diagram Rules

### GFM-T01: `table-pipe-collision`
- **Issue:** Raw pipe characters (`|`) inside math formulas or code spans within table cells fracture Markdown table columns.
- **Auto-Fix:** Encodes math pipes as `&#124;` and code pipes as `\|`.

### GFM-C01: `nested-fence-length`
- **Issue:** Per CommonMark §4.5, outer code blocks containing nested code fences must use strictly longer backtick runs (e.g. four or five backticks).
- **Auto-Fix:** Lengthens outer code block delimiters to exceed inner fences.

### GFM-C02: `inline-code-backticks`
- **Issue:** Inline code spans containing literal backticks must use multi-backtick delimiters per CommonMark §6.3.
- **Auto-Fix:** Converts surrounding delimiters to double backticks (`` `code` ``).

### GFM-D01: `mermaid-identifier`
- **Issue:** Mermaid diagram node labels containing whitespace or special characters without explicit quotes cause parsing failures.
- **Remediation:** Enforces alphanumeric IDs and quoted labels: `id["Node Title"]`.

### GFM-D02: `code-fence-symmetry`
- **Issue:** Code blocks with mismatched opening and closing fence lengths or characters violate CommonMark block structure.
- **Auto-Fix:** Synchronizes closing fence characters and lengths to match the opening fence.

### GFM-S01: `unsafe-shell-expansion`
- **Issue:** Passing markdown bodies with double quotes (`-b "..."` or `--body "..."`) in `gh pr comment` / `gh issue comment` commands in bash scripts or CI workflows exposes LaTeX `$x$` expressions to unintended shell variable expansion.
- **Remediation:** Use stdin streaming: `gh pr comment --body-file - < report.md`.

### GFM-I01: `image-avif-format`
- **Issue:** Uncompressed PNG/JPEG assets increase repository bloat and slow down page loads.
- **Remediation:** Convert images to modern, high-efficiency `.avif` format.

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
