# GFM Math & Diagram Safe Subset Cheat Sheet

A one-page author reference for writing equations and Mermaid diagrams that render identically across **GitHub Web (`cmark-gfm` + MathJax)** and **local IDE previewers (VS Code / Antigravity / KaTeX)** without silent CommonMark corruption.

---

## Letter-Named Macros

GitHub runs CommonMark §2.4 backslash-punctuation stripping inside `$...$` and `$$...$$` *before* MathJax sees the text. Use **letter-named macros** instead of punctuation escapes:

| Avoid (Stripped / Breaks) | Safe Subset (Dual-Engine) | Rule |
| :--- | :--- | :--- |
| `\,` `\;` `\:` `\!` | `\thinspace` `\thickspace` `\medspace` `\negthinspace` | `GFM-M05` |
| `\{` `\}` `\|` | `\lbrace` `\rbrace` `\Vert` | `GFM-M05` |
| `$x < y$` | `$x \lt y$` | `GFM-M06` |
| `$A^*$` | `$A^\ast$` | `GFM-M07` |
| `\operatorname{fix}` | `\mathop{\mathrm{fix}}` | `GFM-M08` |
| `\begin{align} ... \end{align}` | `\begin{aligned} ... \end{aligned}` (inside `$$...$$`) | `GFM-M09` |
| `$86.5\%$` or `$86.5%$` | `` $`86.5\%`$ `` (GFM backtick math) or move `%` outside math | `GFM-M15` |
| `$8.5\ \text{µs}$`, `$90°$`, `$a²$`, `$a–b$` | `$8.5\ \mu\text{s}$`, `$90^\circ$`, `$a^2$`, `$a-b$` | `GFM-M15`, `GFM-M18` |

---

## Display Math Structure

- **Column 0 `$$` with blank-line isolation (`GFM-M02`):** Place `$$` at column 0 with a blank line above and below. Never indent `$$` inside lists or blockquotes.
- **List-nested equations (`GFM-M01`):** Inside list items or blockquotes, use an indented ```` ```math ```` code fence rather than indented `$$`.
- **EOL-only `\\` (`GFM-M16`):** Only `\\` at the **end of a line** survives inside `$$...$$`. Mid-line `\\` (e.g., `\begin{bmatrix} a \\ b \end{bmatrix}`) collapses to `\`! Put each matrix/aligned row on its own line ending in `\\`.
- **No CommonMark block openers (`GFM-M17`):** Never start an interior line of `$$...$$` with `+ `, `- `, `* `, `> `, `#`, `1. `, or `===`/`---`. Move binary operators to the end of the previous line or prefix with `{}` (`{}+ Z`).
- **Dollar delimiters (`GFM-M11`):** Use `$...$` and `$$...$$` instead of `\(...\)` or `\[...\]`.

---

## Inline Math and Tables

- **No inner whitespace (`GFM-M04`):** Write `$x$`, never `$ x $`.
- **Clean boundaries (`GFM-M13`):** Leave whitespace or punctuation outside `$...$` (`base $e$`, `$15^\circ$ C`, `$A\text{–}B$`). Never glue `$` to hyphens or alphanumerics (`base-$e$`).
- **Underscores (`GFM-M12`):** Intra-word subscripts (`$a_1 + b_2$`) are always safe. Flanking subscripts (`$P_{\text{primary}}$ and $P_{\text{secondary}}$`) collide with CommonMark emphasis—prefer GFM backtick math (``$`P_{\text{primary}}`$``) or space-padded subscripts (`$P _ {\text{primary}}$`, emitted by `--target vscode`) for strict KaTeX + GitHub portability (`\_`, the default `--target dual`/`github` fix, is unescaped by GitHub per `P2` but fails in local KaTeX).
- **Code identifiers belong in backticks (`GFM-M03`, `GFM-M14`):** Write `` `sensor_out` `` and `` `fix(fix(c)) == fix(c)` `` outside math instead of `\text{sensor_out}`.
- **Tables (`GFM-T01`):** Never use raw `|` or HTML `&#124;` inside table math. Use `\lvert x \rvert`, `\lVert x \rVert`, or `\vert`.
- **Currency (`GFM-M10`):** Escape literal currency signs (`\$10 to \$20`).

---

## Mermaid Diagrams

- **Line breaks (`GFM-D03`):** Use `<br>`, never literal `\n` inside node labels.
- **Quoted labels (`GFM-D01`, `GFM-D04`):** Quote labels containing spaces or `() {} |`: `A["Channel 1 (dB)"]`.
- **No internal `|` in `-->|...|` (`GFM-D04`):** Write `A -- "U = |a|²" --> B` instead of `A -->|"U = |a|²"| B`.
- **No LaTeX math (`GFM-D05`):** Use Unicode (`ΔT`, `α`, `²`) instead of `$...$`.
- **Dense feedback loops:** Prefer `flowchart LR` with dashed secondary edges (`-.->`) and inspect rendered PNGs via `gfm-math-lint verify --preview-dir build/previews`.

---

## Code Fences and Shell

- **Fence nesting (`GFM-C01`, `GFM-D02`):** Outer fences containing inner fences must use strictly more backticks (e.g., ```` ````markdown ````) and matching closing fences.
- **Backticks inside inline code (`GFM-C02`):** Wrap literal backticks in double backticks with space padding: `` `` `code` `` ``.
- **Unlabelled math/diagram fences (`GFM-C03`):** Convert plain-text equation fences to `$$...$$` and 2D ASCII box-drawing topology diagrams to ```` ```mermaid ````.
- **Safe `gh` CLI scripts (`GFM-S01`):** Never pass double-quoted `-b "$BODY"` to `gh`. Always stream via `--body-file -` or single-quoted heredoc (`<< 'EOF'`).

---

## GitHub Probe Ground Truth

The built-in `P1`–`P11` synthetic probe corpus calibrates `gfm_math_lint.emulator` against GitHub's live `POST /markdown` (`mode=gfm`) endpoint.

- **Last Confirmed Live (`gfm-math-lint probe`):** `2026-11-25` (**11/11 passed**)
- **Run live calibration:** `gfm-math-lint probe` (single API request, synthetic corpus only)
- **Run offline self-check:** `gfm-math-lint probe --offline`

| Probe ID | Markdown Source | Context | Received inside `<math-renderer>` | Verdict & Rule |
| :--- | :--- | :--- | :--- | :--- |
| `P1` | `$a_1 + b_2$ and $c_3$` | Inline | `a_1 + b_2`, `c_3` | Intra-word `_` is safe (`GFM-M12`) |
| `P2` | `$a\_1 + b_2$ and $c_3$` | Inline | `a_1 + b_2`, `c_3` | GitHub unescapes `\_` to `_`; crashes KaTeX (`GFM-M12`) |
| `P3` | `$x\,y \{z\} \lvert w \rvert \ast$` | Inline | `x,y {z} \lvert w \rvert \ast` | `\,` and `\{` stripped; letter macros survive (`GFM-M05`) |
| `P4` | `$\lvert a \rvert^2 + b_k$` | Table | `\lvert a \rvert^2 + b_k` | `\lvert`/`\rvert` safe in tables (`GFM-T01`) |
| `P5` | `\\` at EOL in `aligned` | Display (`$$`) | `\\` preserved | EOL `\\` survives (`GFM-M16`) |
| `P6` | `\{d\} \, e` | Display (`$$`) | `{d} , e` | Punctuation escapes stripped in `$$` (`GFM-M05`) |
| `P7` | `\begin{bmatrix} a \\ b \end{bmatrix}` | Display (`$$`) | `a \ b` | Mid-line `\\` collapses to `\` (`GFM-M16`) |
| `P8` | Indented `$$` inside list item | Display (`$$`) | `()` (not math) | Indented `$$` fails to compile (`GFM-M02`) |
| `P9` | `$$` with `+ Z` / `- 2R` lines | Display (`$$`) | `()` (shattered) | Block markers interrupt `$$` (`GFM-M17`) |
| `P10` | `the base-$e$ error` | Inline | `()` (not math) | Glued opening `$` rejected (`GFM-M13`) |
| `P11` | ```` ```math ```` with `\{i\} \, x` | Code fence | `\{i\} \, x` | Fence bypasses inline unescaping (`GFM-M01`) |

---

## Privacy Model

`gfm-math-lint` is **offline-first** so proprietary engineering specifications and private drafts never leave your machine by accident:

| Command / Flag | Network Access? | Data Transmitted |
| :--- | :---: | :--- |
| `gfm-math-lint check` / `fix` / `check-shell` | **Never** | None (100% local) |
| `gfm-math-lint verify` (default) | **Never** | None (uses local `emulator.py`, `latex.py`, optional local Node KaTeX & `mmdc`) |
| `gfm-math-lint verify --remote` | **Explicit opt-in** | Sends target Markdown document to `api.github.com/markdown` |
| `gfm-math-lint probe` | **Yes** (`--offline` skips) | Sends **only** built-in synthetic `P1`–`P11` snippets (never user files) |
| `gfm-math-lint comment` / `post` | **Yes** | Sends `--file` / stdin content to the specified GitHub PR/issue via `gh` or REST API |
