# Session 2 Retrospective (`dual-doc-conversion-2026-11`): Dual Equation-Heavy Document Conversion

> **Focus:** Converting Two Equation-Heavy Engineering Documents to GitHub Math & Mermaid  
> **Scope:** Document A (Committed Model Reference, ~800 lines $\to$ 196 math spans) & Document B (Private Design Report, ~1,150 lines $\to$ 470 math spans)

In a second field session using `gfm-math-lint v0.1.2`, an agent converted two large engineering documents from plain-text code blocks and ASCII box diagrams to GitHub math (`$...$`, `$$...$$`) and Mermaid diagrams.

## Verification Loop Progression (Document A)

| Step | Local Linter + KaTeX Result | GitHub `/markdown` Span Comparison | Defect Exposed by Span Comparison |
| :--- | :--- | :--- | :--- |
| **0. Original Document** | `gfm-math-lint check`: **0 errors (False Green)** | — | All equations & ASCII box diagrams sat inside unlabelled code fences; invisible to linter (**Finding F1** $\to$ `GFM-C03`). |
| **1. First Conversion** | `fix` applied (~60 `M12` hits); KaTeX strict: 0 errors; `mmdc`: OK | **192 of 196** spans recognized | Mid-line `\\` in a one-line `bmatrix` collapsed to `\` (**Finding F2** $\to$ `GFM-M16`); two `$$` blocks inside list items rendered as raw text (**Finding F3** $\to$ `GFM-M02`). |
| **2. Fixed F2, F3** | All local checks green | **194 of 196** spans recognized | A `$$` block whose second line began with `+ ` was broken into a Markdown `<ul><li>` bulleted list (**Finding F4** $\to$ `GFM-M17`). |
| **3. Fixed F4** | All local checks green | **195 of 196** spans recognized | `base-$e$`: opening `$` glued to a hyphen was rejected as a math delimiter (**Finding F5** $\to$ `GFM-M13`). |
| **4. Fixed F5** | All local checks green | **196 of 196 spans recognized**, text identical, 0 HTML tags inside math | Clean convergence across all 196 spans. |

## Empirical GitHub `/markdown` Probe Ground Truth (`P1`–`P11`)

Roughly **40 tool calls** were spent building a synthetic GitHub `/markdown` behavior probe (`P1`–`P11`, now built into `gfm-math-lint probe`) and an intended-vs-received math span comparator (`gfm_math_lint.emulator`). Furthermore, **Document B** could not be sent to `api.github.com/markdown` because it was private—proving that `gfm-math-lint verify` must default to an accurate **local emulator** rather than transmitting user documents over the network by default.

See the [Safe Subset Cheat Sheet](../safe-subset-cheatsheet.md#github-probe-ground-truth) for the live-confirmed `P1`–`P11` probe table and the [Privacy Model](../safe-subset-cheatsheet.md#privacy-model).
