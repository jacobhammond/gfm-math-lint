# Software Engineering Project Plan: `gfm-math-lint`

## Comprehensive Specification for Automated GitHub Flavored Markdown (GFM), MathJax/KaTeX, and Relative Link Rule Enforcement

---

## 1. Executive Summary & Problem Statement

### 1.1 Context & Background

Repositories that are geared towards scientific work usually contain extensive technical documentation. Disciplines like physics, engineering, mathematics, and other related fields often include rich content within the documentation like math equation rendering, plots, tables, graphs, and links to supporting content sources within the repository. 

When authors (both human engineers and automated AI coding tools) author documentation, they frequently write LaTeX equations and Markdown links assuming standard TeX/LaTeX or GitBook rendering behavior. However, GitHub renders Markdown on web views, pull request diff reviews, mobile interfaces, release notes, and notification emails using `cmark-gfm` (CommonMark) combined with KaTeX/MathJax v3 in a security-restricted rendering sandbox. This disconnect introduces formatting anti-patterns that silently break equation rendering, table structures, diagram parsing, and cross-document navigation.

### 1.2 Identified Technical Pitfalls & Detailed Edge Cases

1. **CommonMark §6.4 Backslash Stripping in LaTeX Text Mode (`\_` -> `_`)**:
* *Mechanism*: `cmark-gfm` parses Markdown *before* passing the DOM to KaTeX. Under CommonMark §6.4, any ASCII punctuation character preceded by a backslash is treated as a Markdown escape character.
* *Failure Mode*: `\text{ave\_shift}` has its single backslash stripped by CommonMark, sending `\text{ave_shift}` to KaTeX. In TeX text mode, an unescaped underscore `_` is an illegal subscript character, triggering fatal syntax errors (`Missing $ inserted` or subscript error).
* *Resolution*: Underscores inside `\text{...}`, `\mathrm{...}`, `\mathbf{...}`, or `\operatorname{...}` must be double-escaped (`\text{ave\\_shift}`) so CommonMark consumes the first backslash and passes `\_` to KaTeX, or wrapped in backtick math spans (``$`\text{ave_shift}`$``).


2. **Curly Brace Escape Stripping in Delimiters (`\left\{` -> `\left{`)**:
* *Mechanism*: In equations using set notation or piecewise functions, TeX uses `\{` and `\}` to render literal curly braces. CommonMark §6.4 treats `\{` as a Markdown character escape and strips the backslash before KaTeX receives the input.
* *Failure Mode*: KaTeX receives `\left{ \dots \right}` instead of `\left\{ \dots \right\}`. Because `{` is a TeX group parameter rather than a valid delimiter, KaTeX throws `Missing or unrecognized delimiter for \left`.
* *Unmangled Input Example*:

```latex
$$\cos(\phi_{\text{net}, 1}) = 0 \implies \phi_{\text{net}, 1} = \phi_1 - \delta \in \left\{ \frac{3\pi}{2} + 2\pi m, \; \frac{\pi}{2} + 2\pi m \right\}, \quad m \in \mathbb{Z}$$
```

* *Resolution*: Convert `\{` and `\}` in `\left`/`\right` expressions to explicit TeX macro commands `\lbrace` and `\rbrace`:

```latex
$$\cos(\phi_{\text{net}, 1}) = 0 \implies \phi_{\text{net}, 1} = \phi_1 - \delta \in \left\lbrace \frac{3\pi}{2} + 2\pi m, \; \frac{\pi}{2} + 2\pi m \right\rbrace, \quad m \in \mathbb{Z}$$
```

$$
\cos(\phi_{\text{net}, 1}) = 0 \implies \phi_{\text{net}, 1} = \phi_1 - \delta \in \left\lbrace \frac{3\pi}{2} + 2\pi m, \; \frac{\pi}{2} + 2\pi m \right\rbrace, \quad m \in \mathbb{Z}
$$



3. **HTML Relational Operator Tag Collision (`<i` -> `<i>`)**:
* *Mechanism*: When LaTeX equations contain relational inequalities or indexed variables involving `<` followed immediately by a letter (such as `<i` in `$W_{<i}$`), GFM's HTML pre-parser misinterprets `<i` as the start of an HTML italic tag (`<i>`).
* *Failure Mode*: The HTML parser strips or mangles the bracket structure inside the TeX expression, leaving an unmatched opening brace when passed to KaTeX, throwing `Extra open brace or missing close brace`.
* *Unmangled Input Example*:

```latex
$$v(k) = \sum_{i \in \text{Z}} \min\!\left( \max\!\left(0, \, k_h - W_{<i} \right), \, w_i \right) m_i$$
```

* *Resolution*: Replace raw `<` characters before letters with the TeX macro `\lt`:

```latex
$$v(k) = \sum_{i \in \text{Z}} \min\!\left( \max\!\left(0, \, k_h - W_{\lt i} \right), \, w_i \right) m_i$$
```

$$
v(k) = \sum_{i \in \text{Z}} \min\!\left( \max\!\left(0, \, k_h - W_{\lt i} \right), \, w_i \right) m_i
$$

4. **Asterisk Emphasis Tag Collision (`y^*[n]` -> `<em>`)**:
* *Mechanism*: GFM's inline formatting parser scans for pairs of asterisks `*` to convert enclosed text to Markdown emphasis (`<em>...</em>`). When multiple LaTeX equations on the same line or in the same block contain superscript/subscript asterisks (e.g., `$y^*[n]$`), GFM pairs the asterisks across the equation.
* *Failure Mode*: GFM transforms `y^*[n] ... y^*[n]` into `y^<em>[n] ... y</em>[n]`. When KaTeX parses `y^` followed immediately by the HTML tag `<em...`, it fails to locate a valid single character or opening `{`, throwing `Missing open brace for superscript`.
* *Unmangled Input Example*:

```latex
$$y^*[n] = r \cdot y_{\text{peak}} \cdot \frac{P_{\text{in}}[n]}{P_{\text{in},0}}, \qquad \Delta[n] = \delta_{\text{db}} \cdot y^*[n]$$
```

* *Resolution*: Convert asterisks used in superscripts/subscripts to TeX macros `\ast` enclosed in braces (`^{\ast}`):

```latex
$$y^{\ast}[n] = r \cdot y_{\text{peak}} \cdot \frac{P_{\text{in}}[n]}{P_{\text{in},0}}, \qquad \Delta[n] = \delta_{\text{db}} \cdot y^{\ast}[n]$$
```

$$
y^{\ast}[n] = r \cdot y_{\text{peak}} \cdot \frac{P_{\text{in}}[n]}{P_{\text{in},0}}, \qquad \Delta[n] = \delta_{\text{db}} \cdot y^{\ast}[n]
$$

5. **Restricted TeX Macro Commands (`\operatorname` -> `\text`)**:
* *Mechanism*: GitHub runs KaTeX in a security-restricted sandbox mode that explicitly disallows dynamic macro-defining commands like `\operatorname`.
* *Failure Mode*: Using `\operatorname{clamp}` throws `The following macros are not allowed: operatorname`.
* *Unmangled Input Example*:

```latex
$$I[n+1] = \operatorname{clamp}\!\left( I[n] + K_i \, e_s[n], \, 0, \, I_{\max} \right), \qquad k[n] = \operatorname{clamp}\!\left( I[n+1] + K_p \, e_s[n] \right)$$
```

* *Resolution*: Replace `\operatorname{...}` with `\text{...}` or `\mathrm{...}`:

```latex
$$I[n+1] = \text{clamp}\!\left( I[n] + K_i \, e_s[n], \, 0, \, I_{\max} \right), \qquad k[n] = \text{clamp}\!\left( I[n+1] + K_p \, e_s[n] \right)$$
```

$$
I[n+1] = \text{clamp}\!\left( I[n] + K_i \, e_s[n], \, 0, \, I_{\max} \right), \qquad k[n] = \text{clamp}\!\left( I[n+1] + K_p \, e_s[n] \right)
$$

6. **Top-Level `align` Environment Disallowance (`\begin{align}` -> `\begin{aligned}`)**:
* *Mechanism*: KaTeX on GitHub operates inside an existing display math container (`$$ ... $$`). Top-level TeX document environments like `\begin{align}` or `\begin{align*}` are unsupported inside display math containers.
* *Failure Mode*: Throws `KaTeX parse error: No such environment: align`.
* *Resolution*: Replace `\begin{align}` and `\end{align}` with `\begin{aligned}` and `\end{aligned}`.


7. **Unescaped Currency Dollar Sign Hijacking (`$10 to $20`)**:
* *Mechanism*: Multiple currency dollar signs on a single line in standard body prose (e.g., `Costs $10 to $20`) are misidentified by GFM as inline math delimiters.
* *Failure Mode*: GFM attempts to parse `$10 to $` as LaTeX, mangling body text.
* *Resolution*: Auto-escape unescaped currency dollar signs in text spans as `\$10`.


8. **GFM Table Pipe Collisions (`|` vs `&#124;`)**:
* *Mechanism*: GFM table parsers treat every raw pipe character (`|`) as a column boundary—even when enclosed inside inline math spans like `$||x|| < 1e-9$`.
* *Failure Mode*: Fractures table structure and corrupts column counts.
* *Resolution*: Convert raw pipes inside table cells to HTML entity `&#124;` or TeX double vertical bar macro `\Vert`.


9. **Non-Portable Display Math Fences (`` ```math `` vs `$$\n...\n$$`)**:
* *Mechanism*: GitHub's `` ```math `` code fences render as raw, unformatted code blocks on mobile views, pull request diff reviews, notification emails, release notes, and external static doc generators (MkDocs, Docusaurus, VitePress).
* *Resolution*: Enforce standalone display math using `$$\n<math>\n$$` isolated on its own lines with blank line padding above and below.


10. **Inline Math Delimiter Whitespace Padding (`$ x $` vs `$x$`)**:
* *Mechanism*: GFM disables inline math parsing when whitespace immediately borders the inner dollar delimiters.
* *Resolution*: Strip inner boundary whitespace so delimiters tightly hug the expression (`$x$`).


11. **Shell Parameter Expansion Equation Loss (`gh pr comment -b "..."`)**:
* *Mechanism*: When developers, scripts, or CI pipelines post GFM content to GitHub via `gh pr comment -b "Variance is $x_1$"`, double-quoted strings trigger Bash parameter expansion before the payload is sent. Bash treats `$x_1$` as an uninitialized shell variable and expands it to an empty string, silently deleting equations.
* *Resolution*: Scan shell scripts and GHA workflows to forbid `-b "..."` or `--body "..."` when posting math. Enforce posting via stdin (`--body-file -`) using single-quoted HEREDOCs (`cat << 'EOF'`). Provide a wrapper CLI subcommand `gfm-math-lint comment`.


12. **Local Filesystem URIs & Absolute Paths (`file:///Users/...`)**:
* *Mechanism*: Authors and coding agents insert machine-specific absolute paths (`file:///Users/...` or `/home/...`). These links fail on GitHub web due to security restrictions.
* *Resolution*: Enforce relative Markdown links (`../src/...` or `other-doc.md`) and validate via Lychee link checker integration.


13. **Code Block Fence Nesting Truncation (`N_{outer} > N_{inner}`)**:
* *Mechanism*: Under CommonMark §4.5, a code block opened by $N$ backticks terminates at any line with $N$ or more backticks (ignoring info strings). When documentation authors write markdown tutorials, plan documents, or code examples that embed fenced blocks (such as ```` ```math ```` or ```` ```bash ````) inside a standard triple-backtick fence (```` ```markdown ````), the inner fence prematurely terminates the outer block.
* *Failure Mode*: Headings, lists, and prose immediately following the inner fence get swallowed into the code block, and subsequent closing fences become orphaned or invert code block rendering across the rest of the document.
* *Resolution*: Enforce that any code fence containing inner code fences must have length strictly greater than the maximum inner fence ($N\_{outer} \ge N\_{inner} + 1$, e.g., 4 or 5 backticks).


14. **Table Pipe Splitting in Inline Code Spans (`|` inside `...`)**:
* *Mechanism*: The GFM table parser splits columns on raw pipe characters `|` *before* inline code span delimiters are parsed. Authors commonly assume enclosing pipes in backticks (e.g., `` ` | ` `` or `` `a | b` ``) protects them from being interpreted as column delimiters, but in GFM tables, it does not.
* *Failure Mode*: Fractures table cell boundaries, shifts subsequent columns, and truncates the rightmost columns of the table.
* *Resolution*: Always escape literal pipes in table cells as `\|` (even inside code spans, e.g., `` `\|` ``) or use HTML entity `&#124;`.


15. **Shell Command Substitution Hazard in Math Payloads (`$(...)`)**:
* *Mechanism*: In shell scripts and CI workflows using double quotes to post math content (e.g. `gh pr comment -b "..."`), expressions containing parentheses preceded by `$` (such as `$\phi(x)$` or `$(a + b)$`) are interpreted by Bash/zsh as command substitutions rather than literal text.
* *Failure Mode*: The shell attempts to execute `\phi(x)` or `a + b` as a shell command, throwing `command not found` or `parse error`, terminating CI workflows, or posting corrupted equations.
* *Resolution*: Strictly prohibit double-quoted `-b` / `--body` invocations containing `$` in CI and shell scripts. Enforce `--body-file -` with single-quoted HEREDOCs (`cat << 'EOF'`) or dedicated CLI wrapper `gfm-math-lint comment`.


16. **Display Math Internal Blank Line Fragmentation**:
* *Mechanism*: GFM display math containers (`$$ ... $$`) expect continuous LaTeX input. When authors insert blank lines inside a display math block (e.g., separating derivation steps), GFM breaks out of the display math container, rendering raw math markup and broken paragraphs.
* *Resolution*: Disallow blank lines inside `$$ ... $$` display math blocks; enforce LaTeX line breaks `\\` or aligned environments (`\begin{aligned}...\end{aligned}`).

17. **Figures and Image Rendering**:
* *Mechanism*: To render images and figures, GFM requires that the file either live in the repository locally and is linked in a compatible format, or a weblink to the image file. While there are many possible formats for images, the preferred format is `.avif` due to its small file size (good for git repos with long histories and regenerating images). Many times, a `figs/` or `images/` directory exists in the repository relative to a given document and is used to display and render images accordingly.  
* *Resolution*: Enforce `.avif` format of any images that are rendered in markdown. If files are a different format like `.jpg`, `.jpeg`, `.png`, `.webp`, `.svg` (static images only, this does not apply to `.gif` or other animated formats), convert it to the correct format using `ffmpeg` for decoding and encoding:

```bash
for f in *.webp; do ffmpeg -i "$f" -c:v libsvtav1 -crf 28 "${f%.webp}.avif"; done
```

* Note that this feature may require dependencies/pre-requisites like `ffmpeg` and `libsvtav1` (for example), and possibly other tools to support all formats. What is in scope for this resolution is to include the ability to enforce this conversion if possible and is supported on the system already (i.e., scan for any images or figures in the markdown, if the file type is `!= .avif`, convert if possible. If conversion fails, warn. Since this is a python package, you should consider including any existing dependencies in the project to help and no reinvent the wheel. Packages like `pillow`, `pillow-heif`, `av`, `imageio`, or `imageio-ffmpeg` should be considered as possible options for this feature. Consult section 2.2, for guidance here - the goal is a lightweight, fast, efficient, standalone-tool (where possible), without unnecessary bloat or crazy dependencies where possible. 

18. **Standard LaTeX Math Delimiters Conversion (`\[ ... \]` and `\( ... \)`)**:
* *Mechanism*: Authors frequently paste standard LaTeX markup from scientific publications and ArXiv papers using `\[ ... \]` for display math and `\( ... \)` for inline math.
* *Failure Mode*: GitHub's Markdown parser does not recognize `\[ ... \]` or `\( ... \)` as math environments. Furthermore, per CommonMark Spec 0.30 §2.4, `[` and `(` are ASCII punctuation characters whose leading backslashes are stripped by `cmark-gfm` during inline parsing, corrupting expressions into literal unrendered text (`[ ... ]` and `( ... )`).
* *Resolution*: Automatically convert standard LaTeX inline math `\( ... \)` to `$ ... $` and display math `\[ ... \]` to isolated `$$\n...\n$$` blocks with blank line padding.

---

## 2. Existing Tooling Analysis & Strategic Recommendation

### 2.1 Tool Evaluation Matrix

| Problem Category | Existing Off-the-Shelf Tooling | Status / Gap Analysis | Strategic Recommendation |
| --- | --- | --- | --- |
| **Local File & Absolute Links** | **Lychee** (`lychee-crate`) | **Fully Solved**. Lychee natively validates local filesystem paths, broken anchors, and `file://` URIs using remap rules. | **Delegate to Lychee**. Do not write custom link checkers. |
| **Fence Closure & Diagram Syntax** | `markdownlint` (MD040/MD046) + `mermaid-cli` (`mmdc`) | **Fully Solved**. `markdownlint` enforces fence symmetry; `mmdc` validates Mermaid DAG definitions. | **Delegate to standard linters**. |
| **Display Math Delimiters** | `mdformat` / `markdownlint-cli2` | **Partially Solved**. Enforces fence formats, but lacks GitHub-specific padding (`$$\n...\n$$`) or inner whitespace rules. | **Build Custom Rule** (`GFM-M01`, `GFM-M02`). |
| **LaTeX Backslash / AST Escaping** | **None** | **Unsolved**. Standard linters parse Markdown AST *before* LaTeX, missing `cmark-gfm` backslash stripping (`\text{_}`), brace stripping (`\left\{`), and operator errors (`\operatorname`). | **Build Custom Rule** (`GFM-M03` through `GFM-M10`). |
| **Table Pipe Collisions** | `mdformat-gfm` | **Unsolved**. Standard GFM parsers split on `\|` even inside inline math spans in table cells. | **Build Custom Rule** (`GFM-T01`). |
| **Code Block Fence & Nesting** | `markdownlint` (MD040/MD046) | **Partially Solved**. Validates fence closure symmetry, but fails to check nested fence length ($N\_{outer} > N\_{inner}$) or inline backtick escaping. | **Build Custom Rule** (`GFM-C01`, `GFM-C02`). |
| **Shell Expansion Safeguards** | **None** | **Unsolved**. No tool checks shell scripts or CI steps for unsafe `gh pr comment -b` usage or `$(...)` subshell execution. | **Build Custom Rule** (`GFM-S01`). |

### 2.2 Strategic Recommendation: Standalone Python Tool (`gfm-math-lint`)

We recommend building a lightweight, zero-dependency Python package (`gfm-math-lint`) published to PyPI/Wheels, deployed alongside **Lychee** and **markdownlint** in pre-commit workflows. A standalone python package ensures:

* Non-Python repositories can consume the pre-commit hook directly without script duplication.
* Centralized rule updates propagate cleanly across all downstream projects via standard dependency/pre-commit versioning.

---

## 3. Detailed Feature Specifications & Rules Engine

### 3.1 MathJax & KaTeX Parsing Rules (`GFM-M**`)

#### `GFM-M01`: Math Code Fence Conversion

* **Severity**: Error (Auto-Fixable)
* **Description**: Identifies math code fences and converts them to standalone `$$\n...\n$$` block math.
* **Bad Syntax**:
````markdown
```math
x = \frac{-b \pm \sqrt{b^2-4ac}}{2a}
```
````

* **Fixed Syntax**:
````markdown
$$
x = \frac{-b \pm \sqrt{b^2-4ac}}{2a}
$$
````

#### `GFM-M02`: Block Math Boundary Isolation & Padding

* **Severity**: Error (Auto-Fixable)
* **Description**: Enforces that display math `$$` delimiters sit on their own isolated lines with blank line padding above and below to ensure proper CommonMark block isolation, and forbids internal blank lines within display math blocks (which prematurely collapses KaTeX display mode into broken paragraph text).
* **Bad Syntax**:
```markdown
Some text above
$$x = y + 1$$
Some text below

```


* **Fixed Syntax**:
```markdown
Some text above

$$
x = y + 1
$$

Some text below

```



#### `GFM-M03`: Text Mode Underscore Double-Escaping

* **Severity**: Error (Auto-Fixable)
* **Description**: Scans LaTeX expressions inside `\text{...}`, `\mathrm{...}`, `\mathbf{...}`, and `\operatorname{...}`. Standard single-escaped underscores (`\_`) are consumed by `cmark-gfm` before reaching KaTeX. They must be double-escaped (`\\_`) or wrapped in backtick math spans (``$`\text{ave_shift}`$``).
* **Bad Syntax**: `$\text{ave\_shift}$`
* **Fixed Syntax**: `$\text{ave\\_shift}$` or ``$`\text{ave_shift}`$``

#### `GFM-M04`: Inline Math Whitespace Stripping

* **Severity**: Error (Auto-Fixable)
* **Description**: GFM disables math parsing if inner whitespace borders the inline `$ ... $` delimiter.
* **Bad Syntax**: `The result is $ x + y $ for all inputs.`
* **Fixed Syntax**: `The result is $x + y$ for all inputs.`

#### `GFM-M05`: Curly Brace Escape Conversion (`\left\{` -> `\left\lbrace`)

* **Severity**: Error (Auto-Fixable)
* **Description**: GFM treats `\{` and `\}` as Markdown character escapes and strips the backslash before KaTeX receives the token. `\left\{` becomes `\left{`, triggering `Missing or unrecognized delimiter for \left`.
* **Bad Syntax**:
```markdown
$$\cos(\phi_{\text{net}, 1}) = 0 \implies \phi_{\text{net}, 1} = \phi_1 - \delta \in \left\{ \frac{3\pi}{2} + 2\pi m, \; \frac{\pi}{2} + 2\pi m \right\}, \quad m \in \mathbb{Z}$$

```


* **Fixed Syntax**:
```markdown
$$\cos(\phi_{\text{net}, 1}) = 0 \implies \phi_{\text{net}, 1} = \phi_1 - \delta \in \left\lbrace \frac{3\pi}{2} + 2\pi m, \; \frac{\pi}{2} + 2\pi m \right\rbrace, \quad m \in \mathbb{Z}$$

```



#### `GFM-M06`: HTML Relational Operator Tag Collision (`<i` -> `\lt i`)

* **Severity**: Error (Auto-Fixable)
* **Description**: GFM's HTML pre-parser treats `<i` (and similar letter combinations after `<`) as the opening of an HTML `<i>` tag, stripping the text and corrupting brace structure (`Extra open brace or missing close brace`).
* **Bad Syntax**:
```markdown
$$v(k) = \sum_{i \in \text{heater}} \min\!\left( \max\!\left(0, \, k_h - W_{<i} \right), \, w_i \right) m_i$$

```


* **Fixed Syntax**:
```markdown
$$v(k) = \sum_{i \in \text{heater}} \min\!\left( \max\!\left(0, \, k_h - W_{\lt i} \right), \, w_i \right) m_i$$

```



#### `GFM-M07`: Asterisk Emphasis Collision (`y^*[n]` -> `y^{\ast}[n]`)

* **Severity**: Error (Auto-Fixable)
* **Description**: Two raw asterisks `*` in the same LaTeX block (e.g., `y^*[n] ... y^*[n]`) are parsed by GFM as Markdown emphasis (`<em>...</em>`), corrupting KaTeX tokens (`Missing open brace for superscript`).
* **Bad Syntax**:
```markdown
$$y^*[n] = r \cdot y_{\text{peak}} \cdot \frac{P_{\text{in}}[n]}{P_{\text{in},0}}, \qquad \Delta[n] = \delta_{\text{db}} \cdot y^*[n]$$

```


* **Fixed Syntax**:
```markdown
$$y^{\ast}[n] = r \cdot y_{\text{peak}} \cdot \frac{P_{\text{in}}[n]}{P_{\text{in},0}}, \qquad \Delta[n] = \delta_{\text{db}} \cdot y^{\ast}[n]$$

```



#### `GFM-M08`: Disallowed Macro Conversion (`\operatorname` -> `\text`)

* **Severity**: Error (Auto-Fixable)
* **Description**: GitHub's KaTeX security sandbox explicitly disallows dynamic macro-defining commands like `\operatorname` (`The following macros are not allowed: operatorname`).
* **Bad Syntax**:
```markdown
$$I[n+1] = \operatorname{clamp}\!\left( I[n] + K_i \, e_s[n], \, 0, \, I_{\max} \right), \qquad k[n] = \operatorname{clamp}\!\left( I[n+1] + K_p \, e_s[n] \right)$$

```


* **Fixed Syntax**:
```markdown
$$I[n+1] = \text{clamp}\!\left( I[n] + K_i \, e_s[n], \, 0, \, I_{\max} \right), \qquad k[n] = \text{clamp}\!\left( I[n+1] + K_p \, e_s[n] \right)$$

```



#### `GFM-M09`: Top-Level `align` Environment Disallowance (`\begin{align}` -> `\begin{aligned}`)

* **Severity**: Error (Auto-Fixable)
* **Description**: KaTeX operates inside an existing display math container (`$$`) and does not support top-level LaTeX `\begin{align}` environments, throwing `KaTeX parse error: No such environment: align`.
* **Bad Syntax**:
```markdown
$$
\begin{align}
a &= b \\
c &= d
\end{align}
$$

```


* **Fixed Syntax**:
```markdown
$$
\begin{aligned}
a &= b \\
c &= d
\end{aligned}
$$

```



#### `GFM-M10`: Unescaped Currency Dollar Sign Hijacking

* **Severity**: Warning (Auto-Fixable)
* **Description**: Detects unescaped currency dollar signs on a single line in standard prose that contain either multiple currency symbols (e.g., `$10 to $20`) or a currency symbol coexisting with an inline/display math span (e.g., `To split $100 in half, we calculate $100/2$`). GFM misidentifies these unescaped dollars as LaTeX math delimiters. Per GitHub documentation and CommonMark §2.4, currency symbols must be escaped as `\$`.
* **Bad Syntax**: `The price increased from $10 to $20 per unit.` or `To split $100 in half, we calculate $100/2$.`
* **Fixed Syntax**: `The price increased from \$10 to \$20 per unit.` or `To split \$100 in half, we calculate $100/2$.`

#### `GFM-M11`: Standard LaTeX Math Delimiters Conversion (`\[` -> `$$`, `\(` -> `$`)

* **Severity**: Error (Auto-Fixable)
* **Description**: Converts LaTeX standard display math delimiters (`\[ ... \]`) to `$$\n...\n$$` and inline delimiters (`\( ... \)`) to `$ ... $`. GitHub does not recognize `\[` or `\(` as math delimiters, and `cmark-gfm` strips the backslashes per CommonMark §2.4 backslash escape rules before KaTeX runs, leaving broken brackets in rendered prose.
* **Bad Syntax**:
```markdown
Here is inline \( x + y = z \) and display math:
\[
a^2 + b^2 = c^2
\]
```
* **Fixed Syntax**:
```markdown
Here is inline $x + y = z$ and display math:

$$
a^2 + b^2 = c^2
$$
```

#### `GFM-M12`: Inline Math Underscore Collision with CommonMark Emphasis (`_` -> `\_`)

* **Severity**: Error (Auto-Fixable)
* **Description**: `cmark-gfm` parses emphasis delimiters (`_..._` -> `<em>...</em>`) before GitHub's math renderer (KaTeX) processes math. When multiple inline math expressions with unescaped subscript underscores appear on a line (e.g. `$a_0$ at $b_{\text{max}}$`), or within a single complex formula (e.g. `$\langle x\rangle = y_0 z_{\text{ref}}$`), CommonMark pairs the underscores into HTML `<em>` tags across or within the math delimiters. This corrupts the LaTeX delimiters and turns the math into raw plain text. Escaping subscript underscores outside text macros as `\_` prevents CommonMark from forming emphasis tags; per CommonMark §2.4 backslash escape rules, CommonMark strips the backslash and passes the clean formula to KaTeX.
* **Bad Syntax**:
```markdown
| Parameter | Description |
| :--- | :--- |
| $a_0$ at $b_{\text{max}}$ | Value |
```
* **Fixed Syntax**:
```markdown
| Parameter | Description |
| :--- | :--- |
| $a\_0$ at $b\_{\text{max}}$ | Value |
```

#### `GFM-M13`: Math Delimiter Boundary Violations

* **Severity**: Error (Auto-Fixable)
* **Description**: GitHub's inline math parser enforces strict boundary constraints on opening and closing `$` delimiters:
  1. **Compound Math Expressions**: An opening `$` preceded by a hyphen or dash (`-`, `–`, `—`, `/`) is rejected as a delimiter. Expressions like `$A$–$B$` render `$A$` as math and leave `–$B$` as plain text. Auto-fixed by combining them into `$A\text{–}B$`.
  2. **Glued Closing Units**: A closing `$` immediately followed by an ASCII alphanumeric character (`[a-zA-Z0-9]`) is rejected as a closing delimiter. Expressions like `$15\ ^\circ$C` or `$0.759$dB` fail to close and render as plain text. Auto-fixed by separating with a space (`$15\ ^\circ$ C`, `$0.759$ dB`).
  3. **Parenthesis Boundary Collisions**: A closing `$` immediately followed by `)` when the math expression itself contains parentheses causes `cmark-gfm` bracket pairing to misalign delimiters (e.g. `($A = B$ instead of $G(L)$)`). Auto-fixed by inserting whitespace (`$G(L)$ )`).
* **Bad Syntax**:
```markdown
The $A$–$B$ curve from $15\ ^\circ$C to $85\ ^\circ$C ($A = B$ instead of $G(L)$).
```
* **Fixed Syntax**:
```markdown
The $A\text{–}B$ curve from $15\ ^\circ$ C to $85\ ^\circ$ C ($A = B$ instead of $G(L)$ ).
```

---

### 3.2 GFM Table Rules (`GFM-T**`)

#### `GFM-T01`: Table Math Pipe Collision

* **Severity**: Error (Auto-Fixable)
* **Description**: GFM table parsers treat raw pipe characters (`|`) as column boundaries—even when enclosed inside inline math (`$||x|| < 1e-9$`) or inline code spans (`\|` inside backticks). Literal pipes inside table cells must be escaped as `\|` or `&#124;`.
* **Bad Syntax**:
```markdown
| Metric | Condition |
| :--- | :--- |
| Norm | $||x|| < 1e-9$ |
```

* **Fixed Syntax**:
```markdown
| Metric | Condition |
| :--- | :--- |
| Norm | $&#124;&#124;x&#124;&#124; < 1e-9$ |
```

*(Alternative: Use double vertical bar LaTeX symbols `\Vert x \Vert` or `&#124;`).*

---

### 3.3 Mermaid Diagram Rules (`GFM-D**`)

#### `GFM-D01`: Explicit Subgraph & Node Label Identifier Enforcement

* **Severity**: Error
* **Description**: Multi-word labels or labels containing spaces passed directly as node identifiers (e.g., `Module Alpha --> Module Beta`) cause Mermaid parsing failures (`Parse error ... got 'NODE_STRING'`).
* **Bad Syntax**: `subgraph Module Alpha --> Module Beta`
* **Fixed Syntax**:
```mermaid
subgraph MA ["Module Alpha"]
    MB ["Module Beta"]
    MA --> MB
end
```



#### `GFM-D02`: Code Block Fence Boundary Symmetry

* **Severity**: Error
* **Description**: Unclosed or asymmetrical triple backtick fences swallow subsequent code blocks, forcing IDEs and renderers to parse code as diagram syntax.
* **Validation**: Verifies equal opening/closing backtick counts across all `` ``` `` blocks.

---

### 3.4 Code Block & Fence Nesting Rules (`GFM-C**`)

#### `GFM-C01`: Code Block Fence Nesting Length (`N_{outer} > N_{inner}`)

* **Severity**: Error (Auto-Fixable)
* **Description**: Under CommonMark §4.5, a code block fence of $N$ backticks terminates at any subsequent line containing $N$ backticks. When a markdown code fence embeds inner code fences (e.g., markdown tutorials or math documentation demonstrating ``` blocks), the outer fence must be strictly longer than any enclosed fence ($N\_{outer} \ge N\_{inner} + 1$).
* **Bad Syntax**:
````markdown
```markdown
```math
x = y + 1
```
```
````

* **Fixed Syntax**:
`````markdown
````markdown
```math
x = y + 1
```
````
`````

#### `GFM-C02`: Inline Code Span Backtick Nesting

* **Severity**: Error (Auto-Fixable)
* **Description**: Enforces that inline code spans containing backtick characters (such as GitHub backtick math `` $`...`$ `` or code fence references `` ```math ``) use multi-backtick delimiters with single whitespace padding per CommonMark §6.3, preventing accidental code span termination.
* **Bad Syntax**: ``(`$`\text{shift}`$`)`` and ``(` ```math `)``
* **Fixed Syntax**: ``(``$`\text{shift}`$``)`` and ``(`` ```math ``)``

---

### 3.5 Shell Expansion & CLI Posting Safeguards (`GFM-S**`)

#### `GFM-S01`: Unsafe Shell Argument Scanner

* **Severity**: Error
* **Description**: Scans repository shell scripts (`*.sh`) and GitHub Actions workflows (`.github/workflows/*.yml`) for `gh pr comment`, `gh issue comment`, or `gh release create` calls using inline double-quoted body arguments (`-b "..."` or `--body "..."`). Detects both parameter expansion (`$var`) equation loss and command substitution (`$(...)`) subshell hazards.
* **Bad Syntax**: `gh pr comment $PR_NO --body "Calculated: $x_1$ ± $sigma$"`
* **Fixed Syntax**:
```bash
gh pr comment $PR_NO --body-file - << 'EOF'
Calculated: $x_1$ ± $sigma$
EOF

```

---

### 3.6 Inline Rule Suppression System (`<!-- gfm-math-lint-... -->`)

In technical documentation, style guides, and tutorial documents that intentionally showcase anti-patterns and faulty syntax (such as this project plan itself), authors must be able to selectively suppress rules without disabling the entire linter across the file.

`gfm-math-lint` parses standard HTML comment directives:

* **Block Suppression**:
````markdown
<!-- gfm-math-lint-disable GFM-M03 -->
$\text{ave\_shift}$
<!-- gfm-math-lint-enable GFM-M03 -->
````

* **Next-Line Suppression**:
````markdown
<!-- gfm-math-lint-disable-next-line GFM-T01 -->
| Metric | $||x|| < 1e-9$ |
````

* **Multi-Rule Comma Separation**:
````markdown
<!-- gfm-math-lint-disable-next-line GFM-M05, GFM-M06 -->
$$\phi \in \left\{ 1 \right\}, \quad W_{<i}$$
````

---

## 4. Architectural Design & Package Structure

`gfm-math-lint` is built as a pure Python 3.10+ package with zero third-party runtime dependencies, using a zero-dependency lexical zone tokenizer, reverse-offset edit algebra, and regular expressions.

### 4.1 Repository Layout

```text
gfm-math-lint/
├── .github/
│   └── workflows/
│       └── ci.yml
├── gfm_math_lint/
│   ├── __init__.py
│   ├── cli.py
│   ├── comment.py
│   ├── config.py
│   ├── fixer.py
│   ├── linter.py
│   ├── tokenizer.py
│   ├── verifier.py
│   └── rules/
│       ├── __init__.py
│       ├── math_rules.py
│       ├── table_rules.py
│       ├── diagram_rules.py
│       ├── code_rules.py
│       └── shell_rules.py
├── tests/
│   ├── test_tokenizer.py
│   ├── test_fixer.py
│   ├── test_math_rules.py
│   ├── test_table_rules.py
│   ├── test_diagram_rules.py
│   ├── test_code_rules.py
│   ├── test_shell_rules.py
│   ├── test_cli.py
│   ├── test_verifier.py
│   └── test_github_api_oracle.py
├── pyproject.toml
├── README.md
└── LICENSE

```

### 4.2 Lexical Zone Tokenizer Architecture (`tokenizer.py`)

Applying regular expressions globally across a raw Markdown document leads to severe false positives (e.g., escaping underscores in Python snake_case identifiers inside code blocks, or splitting on pipes in bash commands).

`gfm_math_lint/tokenizer.py` implements a zero-dependency, single-pass **Lexical Zone State Machine** that segments documents into discrete semantic zones before rules execute:

```python
from enum import Enum

class Zone(Enum):
    FRONTMATTER  = "frontmatter"   # YAML metadata between opening --- and ---
    FENCED_CODE  = "fenced_code"   # ``` or ~~~ code blocks (tracks fence length N)
    INLINE_CODE  = "inline_code"   # `...` or ``...`` inline code spans
    DISPLAY_MATH = "display_math"  # Standalone $$ ... $$ display blocks
    INLINE_MATH  = "inline_math"   # Inline $...$ or $`...`$ math spans
    TABLE        = "table"         # GFM table rows (| col | col |)
    COMMENT      = "comment"       # HTML comments (<!-- ... -->)
    PROSE        = "prose"         # Standard body paragraphs and headers
```

Each rule declares its required target zones:
* `GFM-M01`: Scans `Zone.FENCED_CODE` for info strings matching `math`.
* `GFM-M02`: Scans `Zone.DISPLAY_MATH` boundaries and verifies isolation from `Zone.PROSE`.
* `GFM-M03` .. `GFM-M09`: Subscribe strictly to `Zone.INLINE_MATH` and `Zone.DISPLAY_MATH`.
* `GFM-M10`: Subscribes strictly to `Zone.PROSE` (never matching inside code or math).
* `GFM-T01`: Subscribes strictly to `Zone.TABLE`.
* `GFM-C01`: Subscribes strictly to `Zone.FENCED_CODE`.
* `GFM-C02`: Subscribes strictly to `Zone.INLINE_CODE`.

#### Core Zone Scanning Loop (`gfm_math_lint/tokenizer.py`)

```python
import re
from dataclasses import dataclass
from typing import Iterator

@dataclass(frozen=True)
class DocumentZone:
    zone_type: Zone
    content: str
    start_line: int
    end_line: int
    fence_char: str = ""
    fence_len: int = 0

def scan_document_zones(lines: list[str]) -> list[DocumentZone]:
    zones: list[DocumentZone] = []
    i = 0
    total = len(lines)
    
    while i < total:
        line = lines[i]
        
        # Check fenced code blocks (``` or ~~~)
        m_fence = re.match(r"^(\s*)(`{3,}|~{3,})(.*)$", line)
        if m_fence:
            indent, fence, info = m_fence.groups()
            fence_char, fence_len = fence[0], len(fence)
            start_line = i + 1
            code_lines = [line]
            i += 1
            while i < total:
                code_lines.append(lines[i])
                m_close = re.match(r"^(\s*)(`{3,}|~{3,})\s*$", lines[i])
                if m_close and m_close.group(2)[0] == fence_char and len(m_close.group(2)) >= fence_len:
                    break
                i += 1
            zones.append(DocumentZone(
                zone_type=Zone.FENCED_CODE,
                content="".join(code_lines),
                start_line=start_line,
                end_line=i + 1,
                fence_char=fence_char,
                fence_len=fence_len
            ))
            i += 1
            continue
            
        # Check display math blocks ($$)
        if line.strip() == "$$":
            start_line = i + 1
            math_lines = [line]
            i += 1
            while i < total:
                math_lines.append(lines[i])
                if lines[i].strip() == "$$":
                    break
                i += 1
            zones.append(DocumentZone(
                zone_type=Zone.DISPLAY_MATH,
                content="".join(math_lines),
                start_line=start_line,
                end_line=i + 1
            ))
            i += 1
            continue

        # Check table rows
        if line.strip().startswith("|") and line.strip().endswith("|"):
            start_line = i + 1
            table_lines = [line]
            i += 1
            while i < total and lines[i].strip().startswith("|") and lines[i].strip().endswith("|"):
                table_lines.append(lines[i])
                i += 1
            zones.append(DocumentZone(
                zone_type=Zone.TABLE,
                content="".join(table_lines),
                start_line=start_line,
                end_line=i
            ))
            continue

        # Standard prose paragraph
        zones.append(DocumentZone(
            zone_type=Zone.PROSE,
            content=line,
            start_line=i + 1,
            end_line=i + 1
        ))
        i += 1

    return zones
```

### 4.3 Reverse-Offset Edit Algebra & Idempotency Engine (`fixer.py`)

When auto-fixing multiple violations in a single document (or on the same line), character replacements shift string offsets. Forward-order application corrupts subsequent edit coordinates.

`gfm_math_lint/fixer.py` enforces a **Reverse-Order Edit Application**:
1. Rules produce atomic `LintEdit` records:
   ```python
   @dataclass(frozen=True)
   class LintEdit:
       rule_id: str
       start_line: int  # 1-indexed
       start_col: int   # 1-indexed
       end_line: int
       end_col: int
       replacement: str
   ```
2. The fixer sorts all pending edits by `(start_line DESC, start_col DESC)` (bottom-up, right-to-left).
3. Replacements are applied cleanly without invalidating preceding line and column offsets.
4. **Idempotency Guarantee**: Every rule must satisfy the idempotent property:

$$
\text{fix}(\text{fix}(\text{content})) \equiv \text{fix}(\text{content})
$$

Re-running the fixer over already-fixed content results in a zero-change no-op.

#### Fix Application & Diff Generation Engine (`gfm_math_lint/fixer.py`)

```python
import difflib
from dataclasses import dataclass

@dataclass(frozen=True)
class LintEdit:
    rule_id: str
    start_line: int  # 1-indexed
    start_col: int   # 1-indexed
    end_line: int    # 1-indexed
    end_col: int     # 1-indexed
    replacement: str

def apply_edits(content: str, edits: list[LintEdit]) -> str:
    """Apply atomic edits in reverse coordinate order to maintain offset validity."""
    if not edits:
        return content

    lines = content.splitlines(keepends=True)
    # Sort reverse: descending line number, then descending column number
    sorted_edits = sorted(edits, key=lambda e: (e.start_line, e.start_col), reverse=True)

    for edit in sorted_edits:
        s_line = edit.start_line - 1
        s_col = edit.start_col - 1
        e_line = edit.end_line - 1
        e_col = edit.end_col - 1

        if s_line == e_line:
            # Single-line substitution
            target_line = lines[s_line]
            lines[s_line] = target_line[:s_col] + edit.replacement + target_line[e_col:]
        else:
            # Multi-line block substitution
            first_line = lines[s_line][:s_col]
            last_line = lines[e_line][e_col:]
            lines[s_line:e_line + 1] = [first_line + edit.replacement + last_line]

    return "".join(lines)

def generate_unified_diff(original: str, fixed: str, filename: str) -> str:
    """Generate colorized unified diff for dry-run inspection (--diff)."""
    orig_lines = original.splitlines(keepends=True)
    fixed_lines = fixed.splitlines(keepends=True)
    diff = list(difflib.unified_diff(
        orig_lines,
        fixed_lines,
        fromfile=f"a/{filename}",
        tofile=f"b/{filename}"
    ))
    return "".join(diff)
```

### 4.4 CLI Engine, Pre-Commit Contract & GitHub Actions Formatting (`cli.py`)

```bash
# Standard Linting across files/directories
gfm-math-lint check docs/ README.md

# Dry-run patch preview (Unified diff to stdout without modifying files)
gfm-math-lint check --diff docs/

# Auto-Fix Mode (Modifies files in place)
gfm-math-lint check --fix docs/ README.md

# GitHub Actions CI Mode (Emits workflow annotation commands)
gfm-math-lint check --format=github docs/

# Scan shell scripts & GHA workflows for unsafe math expansion
gfm-math-lint check-shell .github/workflows/

# Safe PR Comment Posting Wrapper (Bypasses Shell Parameter Expansion)
gfm-math-lint comment --pr 123 --file docs/summary.md
```

#### Pre-Commit Exit Code Contract
* `0`: Clean. All files passed validation with zero errors.
* `1`: Violations found, or files were modified by `--fix` (signals git pre-commit to halt commit so author can stage auto-fixes).
* `2`: CLI invocation error, missing file, or invalid configuration.

#### GitHub Actions Workflow Annotations (`--format=github`)
When running in GitHub Actions CI, `gfm-math-lint` prints native workflow commands that render directly on PR diff views:
```text
::error file=docs/optics.md,line=42,col=15,title=GFM-M05::Delimiter \left\{ is stripped by CommonMark. Use \lbrace.
::warning file=docs/pricing.md,line=12,col=8,title=GFM-M10::Unescaped currency dollar signs trigger inline LaTeX.
```

### 4.5 Safe CLI Comment Subcommand Architecture (`comment.py`)

To eliminate shell parameter expansion (`$var`) and command substitution (`$(...)`) hazards when posting technical comments from CI jobs or CLI:

```python
# gfm_math_lint/comment.py
import subprocess

def post_pr_comment(pr_number: int, content: str, repo: str | None = None) -> None:
    # Direct process execution (shell=False) with stdin piping guarantees
    # Bash/zsh never parses or evaluates $ variables or $(...) subshells.
    cmd = ["gh", "pr", "comment", str(pr_number), "--body-file", "-"]
    if repo:
        cmd.extend(["--repo", repo])

    subprocess.run(
        cmd,
        input=content.encode("utf-8"),
        shell=False,
        check=True
    )
```

The subcommand also supports `--preview`, which renders the payload via `gh api /markdown` in the browser or terminal before posting.

### 4.6 Configuration Schema (`pyproject.toml`)

`gfm-math-lint` uses standard library `tomllib` (Python 3.11+) with fallback to read `pyproject.toml`:

```toml
[tool.gfm-math-lint]
exclude = [
    "docs/archive/*",
    "vendor/*"
]
ignore = ["GFM-M10"]  # Disable currency warnings

[tool.gfm-math-lint.per-file-ignores]
"docs/tutorials/common_pitfalls.md" = ["GFM-M03", "GFM-M05", "GFM-C01"]
```

### 4.7 Automated Verification Oracle (`tests/test_github_api_oracle.py`)

To guarantee that auto-fixes and linting rules match GitHub's exact rendering behavior and never suffer from regex/parser drift, integration tests execute directly against GitHub's production Markdown endpoint (`POST /markdown`).

#### Test Harness Implementation (`tests/test_github_api_oracle.py`)

Repurposed directly from empirical testing fixtures, this suite validates that documents pass all GitHub rendering assertions:

```python
import json
import re
import shutil
import subprocess
import pytest

def render_gfm_via_github_api(markdown_content: str) -> str:
    gh_bin = shutil.which("gh")
    if not gh_bin:
        pytest.skip("GitHub CLI ('gh') not installed; skipping live API oracle test.")

    payload = json.dumps({"text": markdown_content, "mode": "gfm"})
    result = subprocess.run(
        [gh_bin, "api", "/markdown", "--input", "-"],
        input=payload,
        text=True,
        capture_output=True,
        timeout=15
    )
    if result.returncode != 0:
        raise RuntimeError(f"GitHub Markdown API failed: {result.stderr}")
    return result.stdout

def assert_gfm_rendering_clean(html: str) -> None:
    # 1. KaTeX parse errors check
    katex_errors = [
        "Missing or unrecognized delimiter",
        "The following macros are not allowed",
        "Extra open brace or missing close brace",
        "Missing open brace for superscript",
        "Missing $ inserted",
        "KaTeX parse error"
    ]
    for err in katex_errors:
        assert err not in html, f"Found KaTeX error in rendered HTML: '{err}'"

    # 2. Table column consistency check
    rows = re.findall(r"<tr>(.*?)</tr>", html, re.DOTALL)
    if rows:
        col_counts = [len(re.findall(r"<t[dh][^>]*>", r)) for r in rows]
        assert len(set(col_counts)) == 1, (
            f"GFM table column mismatch detected across rows: {col_counts}. "
            "Likely caused by unescaped pipe '|' inside table cells."
        )

    # 3. HTML tag collision check (<i tag misinterpretation)
    assert "W_<i>" not in html and "W_<em>" not in html, (
        "Inequality or subscript expression was corrupted by GFM HTML/emphasis parser."
    )

def test_fixed_document_oracle():
    with open("gfm-math-lint-plan.md", "r", encoding="utf-8") as f:
        content = f.read()

    rendered_html = render_gfm_via_github_api(content)
    assert_gfm_rendering_clean(rendered_html)
```

* **Self-Compliance Verification**: `gfm-math-lint` lints its own documentation, plan documents, and test fixtures as part of CI to enforce self-compliance and prevent meta-documentation regressions.

---

## 5. Phased Implementation Roadmap

```text
┌─────────────────────────────────────────────────────────────────────────┐
│ Phase 1: Core Engine & Math Rules (GFM-M01 .. GFM-M10)                   │
├─────────────────────────────────────────────────────────────────────────┤
│ Phase 2: Table, Fence, Diagram & Shell Rules (GFM-T, GFM-C, GFM-D, S01) │
├─────────────────────────────────────────────────────────────────────────┤
│ Phase 3: CLI Subcommand `comment`, Auto-Fix Engine & GitHub API Oracle  │
├─────────────────────────────────────────────────────────────────────────┤
│ Phase 4: PyPI Packaging, Pre-Commit Hooks & Lychee Integration          │
├─────────────────────────────────────────────────────────────────────────┤
│ Phase 5: Template Integration (copier, AGENTS.md, contributing.md)      │
└─────────────────────────────────────────────────────────────────────────┘

```

### Phase 1: Lexical Zone Tokenizer & Math Rules (`GFM-M01` .. `GFM-M10`)

* Implement `tokenizer.py` with the 8-zone state machine (`Zone.PROSE`, `Zone.INLINE_MATH`, `Zone.DISPLAY_MATH`, `Zone.FENCED_CODE`, `Zone.TABLE`, etc.).
* Implement rules `GFM-M01` through `GFM-M10` in `math_rules.py` targeting strictly isolated zones.
* Write comprehensive test suites in `tests/test_tokenizer.py` and `tests/test_math_rules.py`.

### Phase 2: Table, Fence, Diagram & Shell Rules (`GFM-T`, `GFM-C`, `GFM-D`, `GFM-S`)

* Implement `GFM-T01` (table pipe escaping in cells and code spans), `GFM-C01`/`GFM-C02` (code fence nesting length & inline backtick nesting), `GFM-D01`/`GFM-D02` (Mermaid node IDs & fence symmetry), and `GFM-S01` (shell expansion & subshell scanner).
* Add test suites in `tests/test_table_rules.py`, `tests/test_code_rules.py`, `tests/test_diagram_rules.py`, and `tests/test_shell_rules.py`.

### Phase 3: Reverse-Offset Fixer Engine, Dry-Run `--diff`, Suppression & CLI Comment

* Implement `fixer.py` with reverse-offset sorting and idempotency verification.
* Add `--diff` flag using `difflib.unified_diff` for non-destructive dry-run previews.
* Implement inline comment suppression parsing (`<!-- gfm-math-lint-disable -->`).
* Implement `comment.py` subcommand safely piping markdown to `gh pr comment --body-file -` with `shell=False`.
* Implement `tests/test_github_api_oracle.py` using `gh api /markdown` as a continuous regression oracle.

### Phase 4: Packaging & Pre-Commit Hook Integration

* Configure `pyproject.toml` with `setuptools`/`hatchling` and entry points for `gfm-math-lint`.
* Create `.pre-commit-hooks.yaml` in the root of `gfm-math-lint`.
* Configure standalone CI via GitHub Actions.

### Phase 5: Copier Template Integration

* Integrate `gfm-math-lint` and `lychee` into `python-project-template/.pre-commit-config.yaml`.
* Update `template/AGENTS.md` and `template/docs/contributing.md` with explicit GFM math & shell rules.

---

## 6. Pre-Commit & Copier Template Integration Guide

Add the following pre-commit hook definition to `template/.pre-commit-config.yaml`:

```yaml
repos:
  # 1. MathJax & GFM Formatting Enforcement
  - repo: https://github.com/jacobhammond/gfm-math-lint
    rev: v0.1.0
    hooks:
      - id: gfm-math-lint
        name: gfm-math-lint (GFM math & Markdown rule validator)
        entry: gfm-math-lint check
        language: python
        types: [markdown]
        args: [--fix]
      - id: gfm-shell-lint
        name: gfm-shell-lint (Unsafe GFM CLI script checker)
        entry: gfm-math-lint check-shell
        language: python
        types_or: [shell, yaml]

  # 2. Link Verification via Lychee
  - repo: https://github.com/lycheeververse/lychee-action
    rev: v0.14.0
    hooks:
      - id: lychee
        name: lychee (Link and URI checker)
        args: [--remap, "file:///.* ", --exclude-path, "docs/archive"]
        types: [markdown]

```

---

## 7. AI Agent Guidelines (`template/AGENTS.md`)

Add the following section to `template/AGENTS.md` under `### Documentation Standards`:

`````markdown
### Documentation & GFM Math Standards

When writing technical documentation, READMEs, or pull request comments:
1. **Display Math Blocks**: Always use standalone `$$\n...\n$$` blocks isolated on their own lines with blank line padding above and below. Never use `` ```math `` code fences, and never include internal blank lines within display math.
2. **Inline Math Delimiters**: Ensure single dollar signs hug the mathematical expression tightly (`$x+y$`). Never leave space inside delimiters (`$ x + y $`).
3. **Underscores in Math Text**: Double-escape underscores inside `\text{...}` or `\mathrm{...}` spans (`\text{ave\\_shift}`) or use backtick math (``$`\text{ave_shift}`$``).
4. **Curly Braces & Operators**: Use `\lbrace` and `\rbrace` instead of `\{` and `\}` in `\left` / `\right` blocks. Use `\lt` instead of `<` before letters. Use `^{\ast}` instead of `^*` to prevent emphasis tag collisions.
5. **Macro Restrictions**: Never use `\operatorname{...}` or top-level `\begin{align}` environments. Use `\text{...}` and `\begin{aligned}` respectively.
6. **GFM Table Pipes**: Escape raw pipe characters inside table cells as `&#124;` or `\|`, including within inline code spans (e.g., `` `\|` ``).
7. **Code Block Nesting**: When writing code blocks that embed inner fences, ensure the outer code fence uses strictly more backticks than any enclosed fence ($N_{outer} > N_{inner}$).
8. **Inline Code Backticks**: When referencing backtick tokens or GitHub math syntax inline, use double-backtick delimiters with whitespace padding (`` ``$`\text{...}`$`` `` and `` `` ```math `` ``).
9. **Mermaid Identifiers**: Use alphanumeric IDs for subgraphs and multi-word node labels (`subgraph MA ["Module Alpha"]`).
10. **CLI Comment Posting**: Never pass math strings directly to `gh pr comment -b "..."`. Always write to a temp file or use quoted HEREDOCs (`cat << 'EOF'`) to prevent shell parameter expansion or `$(...)` subshell execution from erasing equations.
11. **Rule Suppression**: When intentionally authoring invalid markdown or anti-patterns for demonstration purposes, wrap the snippet in `<!-- gfm-math-lint-disable <RULE> -->` comments.
`````

---

## 8. Success Criteria & Metrics

1. **Zero Math Breaking Errors**: 100% elimination of `Missing $ inserted`, `Missing open brace`, and `No such environment` errors on GitHub web rendering across downstream repositories.
2. **100% Auto-Fix Rate & Idempotency**: Rules `GFM-M01` through `GFM-M10`, `GFM-T01`, and `GFM-C01`/`GFM-C02` auto-fix deterministically without human intervention, with 100% verification of $\text{fix}(\text{fix}(\text{doc})) \equiv \text{fix}(\text{doc})$.
3. **Zero False Positives in Code**: Zone tokenizer guarantees 0% false positive rate for math and table rules inside programming code fences (```` ```python ````, ```` ```bash ````, etc.).
4. **Zero Shell Expansion Equation Loss**: 100% detection of unsafe `gh pr comment -b` calls in shell scripts and CI workflows.
5. **Seamless Adoption**: Automated deployment to downstream repositories via PyPi, pip, uv, pyproject includes, or other standard and easy way to include this standalone tool as both a project dependency in a downstream and a easily runnable plugin/executable/hook to run on a repo's documentation. 
