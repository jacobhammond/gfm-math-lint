# Contributing to gfm-math-lint

Contributions are welcome and greatly appreciated! This project enforces strict code quality, zero runtime dependencies, and high-fidelity Markdown parsing standards.

---

## Development Setup

Install [uv](https://github.com/astral-sh/uv), clone the repository, and set up your virtual environment:

```bash
git clone https://github.com/jacobhammond/gfm-math-lint.git
cd gfm-math-lint
uv sync
```

### Pre-Commit Setup

Install the git hook scripts to automatically run checks on commit:

```bash
uv run pre-commit install
```

To run all hooks manually across all files:

```bash
uv run --no-sync pre-commit run --all-files
```

---

## Quality Gates & Verification

Before submitting code, ensure that all quality gates pass:

1. **Run Tests with Coverage**:
   ```bash
   uv run pytest
   ```

2. **Run Ruff Linting & Formatting**:
   ```bash
   uv run ruff check .
   uv run ruff format --check .
   ```

3. **Run Strict Type Checking**:
   ```bash
   uv run mypy src tests --strict
   ```

4. **Run Self-Checks on Repository Files**:
   ```bash
   uv run gfm-math-lint check README.md CHANGELOG.md CONTRIBUTING.md docs/ .github/
   uv run gfm-math-lint check-shell .github/
   ```

5. **Verify with GitHub Markdown API Oracle (Optional)**:
   ```bash
   uv run gfm-math-lint verify --html preview.html docs/specification.md
   # Or launch in web browser for visual inspection:
   uv run gfm-math-lint verify --browser docs/specification.md
   ```

---

## Architectural & Coding Standards

1. **Zero Runtime Dependencies**: The `gfm-math-lint` runtime code under `src/` must remain pure Python 3.10+ standard library. Do not add external dependencies to `pyproject.toml` dependencies.
2. **Reverse-Offset Edit Algebra**: All automated fixes must be performed via reverse-offset algebra (sorted descending by line number and column offset) to guarantee edit idempotency: $\text{fix}(\text{fix}(c)) \equiv \text{fix}(c)$.
3. **Preserve Escape Sequences & Fixtures**: Never mutate or normalize raw escape sequences in test fixtures or rule patterns. Always verify that docstrings and error messages remain strictly project-agnostic.
4. **8-Zone Semantic Isolation**: Rules must inspect only their designated semantic zones (e.g., math rules only examine `INLINE_MATH` or `DISPLAY_MATH`, table rules examine `TABLE`, code rules examine `FENCED_CODE`). Never inspect raw line strings without zone qualification.
5. **Entity Handling & Preview Fidelity**: The HTML preview generator must maintain KaTeX compatibility by normalizing double-escaped entities (`&amp;gt;` $\rightarrow$ `>`) and disabling duplicate MathML clipboard output (`output: "html"`).

---

## Pull Request Guidelines

1. Ensure all tests and lint checks pass cleanly.
2. Write unit tests for any newly introduced rules, flags, or edge cases.
3. Update `CHANGELOG.md` following [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) format.
4. Describe your changes clearly in the pull request description using `.github/pull_request_template.md`.
