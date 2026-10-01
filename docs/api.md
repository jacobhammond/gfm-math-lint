# Python API Reference

`gfm-math-lint` provides a clean, fully typed Python API for programmatic integration into CI/CD scripts, documentation builders, custom git hooks, and test harnesses.

---

## Installation

```bash
pip install gfm-math-lint
```

---

## 1. Core Classes & Methods

### `gfm_math_lint.Linter`

The main orchestrator for inspecting and fixing markdown content.

```python
from gfm_math_lint import Linter, LintConfig

# Initialize with default configuration
linter = Linter()

# Or initialize with explicit configuration
config = LintConfig(ignore=["GFM-I01"])
linter = Linter(config=config)
```

#### Methods:

##### `lint_string(content: str, file_path: str = "<stdin>", fix: bool = False) -> LintResult`
Lints a string of Markdown text in memory.
- **`content`**: Raw Markdown string.
- **`file_path`**: Display path used in violation reports and per-file rule ignores.
- **`fix`**: If `True`, computes automated fixes for fixable violations.
- **Returns**: A `LintResult` object.

##### `lint_file(path: str | Path, fix: bool = False) -> LintResult`
Reads and lints a file from disk.
- **`path`**: Filesystem path to the Markdown file.
- **`fix`**: If `True`, computes automated fixes (does not write back to disk unless explicitly saved).
- **Returns**: A `LintResult` object.

---

### `gfm_math_lint.LintResult`

Data container holding violations and transformed content.

#### Attributes:
- **`file_path`** (`str`): File path associated with the lint pass.
- **`original_content`** (`str`): Original Markdown input.
- **`fixed_content`** (`str`): Markdown string with all fixes applied (identical to `original_content` if `fix=False` or no fixes were applicable).
- **`violations`** (`list[Violation]`): List of detected violations.
- **`has_violations`** (`bool`): `True` if one or more violations were detected.
- **`has_fixes`** (`bool`): `True` if any fixes were computed and `fixed_content != original_content`.

#### Methods:
- **`diff() -> str`**: Returns a standard unified diff comparing `original_content` against `fixed_content`.

---

### `gfm_math_lint.Violation`

Represents an individual rule violation.

#### Attributes:
- **`rule_id`** (`str`): Unique identifier (e.g. `"GFM-M03"`).
- **`rule_name`** (`str`): Human-readable rule name (e.g. `"text-mode-underscore-escape"`).
- **`message`** (`str`): Explanation of the issue and remediation.
- **`line`** (`int`): 1-indexed line number where violation begins.
- **`col`** (`int`): 1-indexed column number where violation begins.
- **`end_line`** (`int`): 1-indexed line number where violation ends.
- **`end_col`** (`int`): 1-indexed column number where violation ends.
- **`severity`** (`Severity`): `Severity.ERROR` or `Severity.WARNING`.
- **`fix`** (`tuple | None`): Replacement tuple `(start_line, start_col, end_line, end_col, replacement_text)` if automated fix is available.

---

### `gfm_math_lint.config.LintConfig`

Configuration container parsed from `pyproject.toml` or custom configuration files.

```python
from gfm_math_lint.config import load_config

# Automatically loads from pyproject.toml in current or parent directories
config = load_config()

# Or load from an explicit path
config = load_config(Path("custom_config.toml"))
```

#### Attributes:
- **`exclude`** (`list[str]`): List of file globs to exclude (e.g. `["docs/archive/*"]`).
- **`ignore`** (`list[str]`): List of globally ignored rule IDs.
- **`per_file_ignores`** (`dict[str, list[str]]`): Mapping of file globs to rule IDs.

---

## 2. Verification API (`gfm_math_lint.verifier`)

Audits Markdown against the live GitHub REST API or generates KaTeX browser previews.

```python
from pathlib import Path
from gfm_math_lint.verifier import verify_markdown, verify_file, build_preview_html

# Verify markdown against GitHub API
issues = verify_markdown("# Doc\n\n$x < y$")
for issue in issues:
    print(f"[{issue.category}] {issue.message}")

# Generate standalone KaTeX preview HTML
html_content = build_preview_html("# My Formula\n\n$$\\frac{1}{2}$$")
```

#### Functions:
- **`verify_file(file_path: Path, token: str | None = None) -> list[VerificationIssue]`**:
  Renders a file via GitHub's API and inspects for KaTeX errors, table column mismatches, and tag collisions.
- **`verify_markdown(content: str, token: str | None = None) -> list[VerificationIssue]`**:
  Renders raw Markdown content via GitHub's API.
- **`build_preview_html(markdown_content: str, title: str = "GFM Math Preview", token: str | None = None) -> str`**:
  Renders Markdown to a standalone HTML string with KaTeX styling and entity normalization.

---

## 3. Practical Recipes

### Recipe 1: Pytest Test Harness
Validate that all repository Markdown files comply with GFM math rules in your automated test suite:

```python
from pathlib import Path
import pytest
from gfm_math_lint import Linter

@pytest.mark.parametrize("md_file", list(Path("docs").glob("**/*.md")))
def test_documentation_math_syntax(md_file: Path) -> None:
    linter = Linter()
    result = linter.lint_file(md_file, fix=False)
    
    if result.has_violations:
        violations_summary = "\n".join(
            f"  Line {v.line}:{v.col} [{v.rule_id}] {v.message}"
            for v in result.violations
        )
        pytest.fail(f"Found {len(result.violations)} syntax violation(s) in {md_file}:\n{violations_summary}")
```

### Recipe 2: Automated In-Place Batch Fixer
Programmatically fix Markdown files across a project and report diffs:

```python
from pathlib import Path
from gfm_math_lint import Linter

linter = Linter()
docs_dir = Path("docs")

for md_file in docs_dir.glob("**/*.md"):
    result = linter.lint_file(md_file, fix=True)
    if result.has_fixes:
        print(f"Applying fixes to {md_file}:\n{result.diff()}")
        md_file.write_text(result.fixed_content, encoding="utf-8")
```

### Recipe 3: MkDocs / Sphinx Pre-Build Hook
Integrate a strict lint check into your documentation build pipeline before generating static HTML:

```python
import sys
from pathlib import Path
from gfm_math_lint import Linter

def validate_docs():
    linter = Linter()
    has_errors = False
    
    for path in Path("docs").rglob("*.md"):
        result = linter.lint_file(path)
        for v in result.violations:
            print(f"{path}:{v.line}:{v.col}: [{v.rule_id}] {v.message}", file=sys.stderr)
            has_errors = True
            
    if has_errors:
        sys.exit(1)

if __name__ == "__main__":
    validate_docs()
```
