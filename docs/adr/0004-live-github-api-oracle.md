# ADR 0004: Live GitHub API Rendering Oracle for Visual Verification

## Status
Accepted

## Date
2026-09-30

## Context
Static analysis alone cannot detect every browser rendering anomaly, KaTeX compilation error, or subtle CSS/DOM interaction on GitHub. Unit tests asserting string transformations do not guarantee that the transformed Markdown actually renders cleanly when processed by GitHub's `cmark-gfm` and client-side MathJax/KaTeX engines.

## Decision
Provide a built-in verification oracle (`gfm-math-lint verify` and `gfm_math_lint.verifier`):
1. **GitHub REST API Oracle:** Submits documents to GitHub's `/markdown` endpoint (via local `gh` CLI if authenticated, or direct HTTPS request via `urllib.request`).
2. **HTML DOM Inspection:** Analyzes the rendered HTML for KaTeX errors (`katex-error`), fractured table grids, and unintended HTML tag collisions.
3. **Standalone Browser Preview:** Embeds KaTeX with automated HTML entity normalization (`&amp;gt;` → `>`) and duplicate MathML clipboard suppression (`output: "html"`).

## Consequences
### Positive
- End-to-end ground truth verification directly against GitHub's live rendering infrastructure.
- Instant visual feedback for authors via `--browser`.
- Robust test oracle for regression testing.

### Negative
- Live GitHub API verification requires network access and is rate-limited if unauthenticated (mitigated by using `gh` authentication or `$GITHUB_TOKEN`). Tests requiring network are marked with `@pytest.mark.network` and deselected by default during offline builds.
