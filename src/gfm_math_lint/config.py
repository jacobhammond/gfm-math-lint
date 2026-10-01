"""Configuration loader for gfm-math-lint from pyproject.toml."""

from __future__ import annotations

import fnmatch
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class LintConfig:
    """Configuration options for gfm-math-lint."""

    exclude: list[str] = field(default_factory=list)
    ignore: list[str] = field(default_factory=list)
    per_file_ignores: dict[str, list[str]] = field(default_factory=dict)
    config_dir: Path | None = None

    def __post_init__(self) -> None:
        self._ignore_upper: set[str] = {r.upper() for r in self.ignore}
        self._per_file_upper: dict[str, set[str]] = {
            pat: {r.upper() for r in rules} for pat, rules in self.per_file_ignores.items()
        }

    def is_file_excluded(self, file_path: str | Path, root_dir: Path | None = None) -> bool:
        """Check if a file matches any exclude glob patterns relative to config directory."""
        base_dir = self.config_dir or root_dir or Path.cwd()
        p = Path(file_path).resolve()
        try:
            rel_path = str(p.relative_to(base_dir.resolve()))
        except ValueError:
            rel_path = str(p)
        norm_path = rel_path.replace("\\", "/")
        norm_name = p.name

        for pattern in self.exclude:
            norm_pattern = pattern.replace("\\", "/")
            if fnmatch.fnmatch(norm_path, norm_pattern) or fnmatch.fnmatch(norm_name, norm_pattern):
                return True
            # Also check matching without leading ./
            if fnmatch.fnmatch(norm_path.lstrip("./"), norm_pattern.lstrip("./")):
                return True
        return False

    def is_rule_ignored(self, rule_id: str, file_path: str | Path, root_dir: Path | None = None) -> bool:
        """Check if a rule is globally ignored or ignored for this specific file."""
        rule_upper = rule_id.upper()
        if rule_upper in self._ignore_upper:
            return True

        base_dir = self.config_dir or root_dir or Path.cwd()
        p = Path(file_path).resolve()
        try:
            rel_path = str(p.relative_to(base_dir.resolve()))
        except ValueError:
            rel_path = str(p)
        norm_path = rel_path.replace("\\", "/")
        norm_name = p.name

        for pattern, rules in self._per_file_upper.items():
            norm_pattern = pattern.replace("\\", "/")
            if (
                fnmatch.fnmatch(norm_path, norm_pattern)
                or fnmatch.fnmatch(norm_name, norm_pattern)
                or fnmatch.fnmatch(norm_path.lstrip("./"), norm_pattern.lstrip("./"))
            ) and rule_upper in rules:
                return True

        return False


def load_config(pyproject_path: Path | None = None, is_explicit: bool = False) -> LintConfig:
    """Load configuration from pyproject.toml."""
    if pyproject_path is None:
        curr = Path.cwd()
        for parent in (curr, *curr.parents):
            candidate = parent / "pyproject.toml"
            if candidate.is_file():
                pyproject_path = candidate
                break

    if pyproject_path is None or not pyproject_path.is_file():
        if is_explicit and pyproject_path is not None:
            raise FileNotFoundError(f"Configuration file not found: {pyproject_path}")
        return LintConfig()

    try:
        content = pyproject_path.read_text(encoding="utf-8")
        parsed = tomllib.loads(content)
    except (OSError, tomllib.TOMLDecodeError) as e:
        if is_explicit:
            raise ValueError(f"Failed to read/parse {pyproject_path}: {e}") from e
        sys.stderr.write(f"Warning: Failed to parse {pyproject_path}: {e}\n")
        return LintConfig()

    tool_section = parsed.get("tool", {}).get("gfm-math-lint", {})
    if not isinstance(tool_section, dict):
        if is_explicit:
            raise ValueError(f"[tool.gfm-math-lint] in {pyproject_path} must be a table")
        return LintConfig()

    exclude = tool_section.get("exclude", [])
    ignore = tool_section.get("ignore", [])
    per_file = tool_section.get("per-file-ignores", {})

    if not isinstance(exclude, list):
        if is_explicit:
            raise ValueError(f"'exclude' in {pyproject_path} must be a list of strings")
        exclude = []
    if not isinstance(ignore, list):
        if is_explicit:
            raise ValueError(f"'ignore' in {pyproject_path} must be a list of strings")
        ignore = []
    if not isinstance(per_file, dict):
        if is_explicit:
            raise ValueError(f"'per-file-ignores' in {pyproject_path} must be a table")
        per_file = {}

    return LintConfig(
        exclude=[str(x) for x in exclude],
        ignore=[str(x) for x in ignore],
        per_file_ignores={str(k): [str(x) for x in v] for k, v in per_file.items() if isinstance(v, list)},
        config_dir=pyproject_path.parent.resolve(),
    )
