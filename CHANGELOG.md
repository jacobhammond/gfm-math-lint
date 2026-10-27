# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Stdin Input (`-`) Support in `verify`**: Added ability to verify piped markdown streams via standard input (`cat doc.md | gfm-math-lint verify -` or `git show HEAD:README.md | gfm-math-lint verify -`).
- **Raw HTML Streaming (`--stdout` / `--raw`)**: Added `--stdout` flag (with alias `--raw`) to stream rendered HTML directly to stdout while cleanly routing diagnostic logs and audit reports to stderr.
- **Buffered Block Container Traversal**: `GFMHTMLValidator` buffers text data across inline tag boundaries inside block containers (`<p>`, `<li>`, `<td>`, `<blockquote>`) to catch unrendered math delimiters split across formatting tags like `<em>` and `<strong>`.
- **MathML Pseudo-Code Stacking Detection**: Added heuristic scanner inside `<math-renderer>` elements to detect programming function composition placed in math delimiters, emitting `pseudo-code-stacking` verification warnings for formulas that cause vertical character stacking in environments without KaTeX CSS.

### Security
- Support HTML5 comment end bang state (`--!>`) across tokenizer and diagram rules, remediating CodeQL alerts #1 and #2 (`py/bad-tag-filter`).
## [0.1.1] - 2026-09-30

### Fixed
- Fixed release asset upload in CI publishing workflow by explicitly targeting the repository.

## [0.1.0] - 2026-09-30

- Initial release.

[0.1.1]: https://github.com/jacobhammond/gfm-math-lint/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/jacobhammond/gfm-math-lint/releases/tag/v0.1.0
