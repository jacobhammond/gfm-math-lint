# `gfm-math-lint` GitHub Action

Composite GitHub Action for running **gfm-math-lint** in CI workflows: lint Markdown math/tables/diagrams (`check`), auto-fix (`fix`), run privacy-first differential verification (`verify`), scan workflow scripts (`check-shell`), or calibrate against GitHub's `/markdown` API (`probe`).

## Inputs

| Input | Default | Description |
| :--- | :--- | :--- |
| `mode` | `"check"` | CLI subcommand: `check`, `fix`, `verify`, `probe`, or `check-shell`. |
| `paths` | `"."` | Space-separated files or directories to inspect (ignored in `probe` mode). |
| `target` | `"dual"` | Rendering engine profile (`dual`, `github`, or `vscode`) for `check` / `fix`. |
| `format` | `"github"` | Diagnostic output format (`github`, `text`, or `json`). `probe` mode supports `text` and `json`. |
| `config` | `""` | Optional path to a `pyproject.toml` configuration file. |
| `version` | `"1.0.0"` | PyPI version (default `"1.0.0"`), `"latest"` for unpinned PyPI, or `"local"` to install from action repo source. |
| `python-version` | `"3.11"` | Python version provisioned via `uv`. |
| `remote-verify` | `"false"` | Pass `--remote` to `verify` (transmits markdown to GitHub `/markdown` API). |
| `offline-probe` | `"false"` | Pass `--offline` to `probe`. |
| `strict-katex` | `"false"` | Pass `--strict-katex` to `verify`. |
| `no-katex` | `"false"` | Pass `--no-katex` to `verify`. |
| `json-output` | `""` | Optional file path to save a structured JSON diagnostic report. |
| `post-comment` | `"false"` | Post a PR summary comment via `gfm-math-lint comment` when violations occur (requires `pull-requests: write`). |
| `github-token` | `${{ github.token }}` | Token passed to `probe`, `verify --remote`, or `post-comment`. |

## Outputs

| Output | Description |
| :--- | :--- |
| `exit-code` | Exit code returned by `gfm-math-lint` (`0` = clean, `1` = violations/anomalies, `2` = error). |
| `report-path` | Path to the written JSON report when `json-output` is set. |

## Usage Examples

### 1. Lint Markdown & Workflows on Pull Requests

```yaml
name: docs-lint
on: [pull_request]

permissions:
  contents: read

jobs:
  gfm-lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Lint Markdown math & diagrams
        uses: jacobhammond/gfm-math-lint/actions/gfm-math-lint-action@v1.0.0
        with:
          mode: check
          paths: "README.md docs/"
          target: dual
          format: github
          version: "1.0.0"

      - name: Scan workflows for unsafe gh shell expansion
        uses: jacobhammond/gfm-math-lint/actions/gfm-math-lint-action@v1.0.0
        with:
          mode: check-shell
          paths: ".github/workflows/"
          version: "1.0.0"
```

### 2. Offline Differential Verification + JSON Artifact

```yaml
      - name: Verify Markdown math spans offline
        uses: jacobhammond/gfm-math-lint/actions/gfm-math-lint-action@v1.0.0
        with:
          mode: verify
          paths: "docs/"
          json-output: "build/gfm-verify-report.json"
          version: "1.0.0"
```

### 3. Weekly Synthetic GitHub `/markdown` Probe Calibration

```yaml
name: gfm-probe
on:
  schedule:
    - cron: "0 6 * * 1"
  workflow_dispatch:

permissions:
  contents: read

jobs:
  probe:
    runs-on: ubuntu-latest
    steps:
      - name: Calibrate emulator against live GitHub /markdown API
        uses: jacobhammond/gfm-math-lint/actions/gfm-math-lint-action@v1.0.0
        with:
          mode: probe
          version: "1.0.0"
```

### 4. Post PR Summary Comment on Violations

```yaml
permissions:
  contents: read
  pull-requests: write

jobs:
  pr-lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: jacobhammond/gfm-math-lint/actions/gfm-math-lint-action@v1.0.0
        with:
          mode: check
          paths: "docs/"
          post-comment: "true"
          version: "1.0.0"
```
