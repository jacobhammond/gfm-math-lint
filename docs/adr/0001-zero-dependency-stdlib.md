# ADR 0001: Zero External Runtime Dependencies

## Status
Accepted

## Date
2026-09-30

## Context
Linters and pre-commit hooks are installed into diverse environments, ranging from minimal CI runner containers to locked-down corporate developer workstations. External runtime dependencies introduce installation latency, potential dependency conflicts with user project environments (dependency hell), supply chain security attack surfaces, and ongoing maintenance burdens.

## Decision
`gfm-math-lint` shall have **zero third-party runtime dependencies**. All parsing, linting, fixing, CLI handling, HTTP interaction, and configuration parsing must use the Python standard library (`sys`, `os`, `re`, `argparse`, `pathlib`, `tomllib`, `urllib`, `difflib`, `shutil`). Third-party packages (e.g. `pytest`, `ruff`, `mypy`, `twine`) are restricted exclusively to development and testing dependencies.

## Consequences
### Positive
- Sub-second installation via `pip install gfm-math-lint` or `uv tool install gfm-math-lint`.
- Immunity to runtime dependency vulnerabilities and supply chain compromises.
- Instant startup time suitable for tight pre-commit hooks.
- Zero risk of conflicting with user environment package pins.

### Negative
- Configuration parsing for Python < 3.11 requires handling standard library evolution, though requiring `python >= 3.11` ensures native `tomllib` availability.
