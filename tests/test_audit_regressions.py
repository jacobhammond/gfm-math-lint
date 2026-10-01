"""Regression tests for pre-publication audit findings (C4-C6, H4, H6, H7, M2, M5, M11, L5)."""

from __future__ import annotations

from pathlib import Path

import pytest

from gfm_math_lint.cli import collect_markdown_files
from gfm_math_lint.config import load_config
from gfm_math_lint.linter import Linter, _escape_workflow_data, _escape_workflow_property
from gfm_math_lint.rules.diagram_rules import RuleD01
from gfm_math_lint.rules.image_rules import RuleI01
from gfm_math_lint.rules.math_rules import RuleM08
from gfm_math_lint.tokenizer import scan_document_zones


class TestC4ZoneEscapingRegressions:
    """Verify that auto-fix never corrupts code blocks in blockquotes, lists, or indented blocks."""

    def test_blockquote_code_fence_not_corrupted(self) -> None:
        """C4: Code inside blockquote fences must not have math/currency fixes applied."""
        content = '> ```bash\n> echo "$a_b and $c_d"\n> ```\n'
        linter = Linter()
        result = linter.lint_string(content, fix=True)
        assert result.fixed_content == content

    def test_list_nested_fence_not_corrupted(self) -> None:
        """C4: Code fences nested inside list items must not be parsed as prose."""
        content = "1. Step one\n   ```python\n   # $5 and $10 cost\n   print('hello')\n   ```\n"
        linter = Linter()
        result = linter.lint_string(content, fix=True)
        assert result.fixed_content == content

    def test_indented_code_block_not_corrupted(self) -> None:
        """C4: 4-space indented CommonMark code blocks must not have math fixes applied."""
        content = 'Here is some text:\n\n    print("$x_1$ $y_2$")\n    # $10 and $20\n\nFollowing prose.\n'
        linter = Linter()
        result = linter.lint_string(content, fix=True)
        assert result.fixed_content == content

    def test_unclosed_display_math_does_not_corrupt_subsequent_document(self) -> None:
        """C4: An unclosed $$ must not delete following blank lines or rewrite HTML."""
        content = (
            "$$\n"
            "\\phi = 1\n\n"
            "Paragraph after unclosed display math.\n\n"
            '<a href="https://example.com">link</a>\n\n'
            "Another paragraph with $5 and $10.\n"
        )
        linter = Linter()
        result = linter.lint_string(content, fix=True)
        # Blank lines and HTML tags must remain completely intact
        assert "\n\nParagraph after unclosed display math.\n\n" in result.fixed_content
        assert '<a href="https://example.com">link</a>' in result.fixed_content


class TestC5ImageRuleRegressions:
    """Verify that image rule GFM-I01 does not rename files to nonexistent .avif."""

    def test_image_rule_does_not_auto_fix(self) -> None:
        """C5: GFM-I01 must be report-only warning without auto-fix edit."""
        content = "Here is an image: ![Diagram](img/arch.png)\n"
        rule = RuleI01()
        lines = content.splitlines(keepends=True)
        zones = scan_document_zones(lines)
        violations = rule.check(lines, zones)
        assert len(violations) == 1
        assert violations[0].severity == "warning"
        assert violations[0].edit is None

    def test_image_rule_ignores_svg_and_inline_code(self) -> None:
        """C5: SVG vector images and image syntax inside inline code are ignored."""
        content = "Vector logo: ![Logo](assets/logo.svg)\nInside code: `![x](y.png)`\n"
        rule = RuleI01()
        lines = content.splitlines(keepends=True)
        zones = scan_document_zones(lines)
        violations = rule.check(lines, zones)
        assert len(violations) == 0


class TestC6DirectoryPruning:
    """Verify that file collection prunes hidden and vendored directories."""

    def test_collect_markdown_files_prunes_default_excludes(self, tmp_path: Path) -> None:
        """C6: .venv, node_modules, and .git directories are never traversed."""
        (tmp_path / "valid.md").write_text("# Valid\n", encoding="utf-8")
        venv_dir = tmp_path / ".venv" / "lib"
        venv_dir.mkdir(parents=True)
        (venv_dir / "dep.md").write_text("# Dep\n", encoding="utf-8")

        node_dir = tmp_path / "node_modules" / "pkg"
        node_dir.mkdir(parents=True)
        (node_dir / "pkg.md").write_text("# Pkg\n", encoding="utf-8")

        files, missing = collect_markdown_files([str(tmp_path)], root_dir=tmp_path)
        assert missing == []
        file_names = [f.name for f in files]
        assert "valid.md" in file_names
        assert "dep.md" not in file_names
        assert "pkg.md" not in file_names


class TestH4LineEndingPreservation:
    """Verify CRLF preservation across lint and fix cycles."""

    def test_crlf_roundtrip_preserved(self, tmp_path: Path) -> None:
        """H4: A CRLF file must retain CRLF after fixing violations."""
        file_path = tmp_path / "crlf_doc.md"
        # File with CRLF line endings and a fixable violation ($ x $ -> $x$)
        file_path.write_bytes(b"# Title\r\n\r\nHere is math $ x $ in CRLF.\r\n")

        linter = Linter()
        result = linter.lint_file(file_path, fix=True)

        assert b"\r\n" in result.fixed_content.encode("utf-8")
        assert b"\r\r\n" not in result.fixed_content.encode("utf-8")
        # Verify the file on disk also preserved CRLF
        disk_bytes = file_path.read_bytes()
        assert b"\r\n" in disk_bytes
        assert b"\n" not in disk_bytes.replace(b"\r\n", b"")


class TestH6ConfigAndMissingPathHandling:
    """Verify strict error handling for configuration and paths."""

    def test_missing_explicit_config_raises_file_not_found(self, tmp_path: Path) -> None:
        """H6: Specifying a non-existent config path must raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_config(tmp_path / "non_existent.toml", is_explicit=True)

    def test_malformed_toml_config_raises_value_error(self, tmp_path: Path) -> None:
        """H6: Malformed TOML syntax in config must raise ValueError."""
        bad_config = tmp_path / "bad.toml"
        bad_config.write_text("[tool.gfm-math-lint\nincomplete syntax", encoding="utf-8")
        with pytest.raises(ValueError):
            load_config(bad_config, is_explicit=True)


class TestH7SuppressionDirectivesInCodeBlocks:
    """Verify that suppression comments inside code blocks do not affect linting."""

    def test_suppression_comment_in_fenced_code_is_ignored(self) -> None:
        """H7: <!-- gfm-math-lint-disable --> inside code blocks must not suppress prose."""
        content = (
            "Here is documentation showing how to suppress rules:\n\n"
            "```markdown\n"
            "<!-- gfm-math-lint-disable -->\n"
            "```\n\n"
            "This prose line contains an error: $ x $\n"
        )
        linter = Linter()
        result = linter.lint_string(content, fix=False)
        rule_ids = [v.rule_id for v in result.violations]
        assert "GFM-M04" in rule_ids

    def test_blanket_disable_then_enable_specific_rule(self) -> None:
        """H7: Blanket disable followed by enable for a specific rule works as expected."""
        content = (
            "<!-- gfm-math-lint-disable -->\n"
            "Suppressed math $ x $\n"
            "<!-- gfm-math-lint-enable GFM-M04 -->\n"
            "Active math $ y $\n"
        )
        linter = Linter()
        result = linter.lint_string(content, fix=False)
        assert len(result.violations) == 1
        assert result.violations[0].line == 4
        assert result.violations[0].rule_id == "GFM-M04"


class TestM2WorkflowEscaping:
    """Verify GitHub Actions workflow command escaping."""

    def test_workflow_data_and_property_escaping(self) -> None:
        """M2: Workflow properties and data must escape %, \\r, \\n, :, ,."""
        raw_prop = "file:name,with:special%chars\n"
        escaped_prop = _escape_workflow_property(raw_prop)
        assert ":" not in escaped_prop
        assert "," not in escaped_prop
        assert "\n" not in escaped_prop
        assert "%25" in escaped_prop

        raw_data = "line 1\nline 2 with % and \r"
        escaped_data = _escape_workflow_data(raw_data)
        assert "\n" not in escaped_data
        assert "\r" not in escaped_data
        assert "%0A" in escaped_data
        assert "%0D" in escaped_data
        assert "%25" in escaped_data


class TestM5OperatorMacroConversion:
    """Verify GFM-M08 preserves operator limits."""

    def test_operatorname_star_preserves_limits(self) -> None:
        """M5: \\operatorname*{arg\\,max} converts to \\mathop{\\mathrm{arg\\,max}}\\limits."""
        content = "$$\\operatorname*{arg\\,max}_{x \\in S} f(x)$$\n"
        rule = RuleM08()
        lines = content.splitlines(keepends=True)
        zones = scan_document_zones(lines)
        violations = rule.check(lines, zones)
        assert len(violations) == 1
        assert violations[0].edit is not None
        assert "\\mathop{\\mathrm{arg\\,max}}\\limits" in violations[0].edit.replacement

    def test_operatorname_converts_to_mathop_mathrm(self) -> None:
        """M5: \\operatorname{diag} converts to \\mathop{\\mathrm{diag}}."""
        content = "$$\\operatorname{diag}(A)$$\n"
        rule = RuleM08()
        lines = content.splitlines(keepends=True)
        zones = scan_document_zones(lines)
        violations = rule.check(lines, zones)
        assert len(violations) == 1
        assert violations[0].edit is not None
        assert "\\mathop{\\mathrm{diag}}" in violations[0].edit.replacement


class TestM11MermaidEdgeLabelsAndSubgraphs:
    """Verify Mermaid rule D01 allows standard edge-label syntax and subgraphs."""

    def test_mermaid_edge_label_syntax_accepted(self) -> None:
        """M11: Mermaid edge labels like A -- yes --> B are valid."""
        content = (
            "```mermaid\n"
            "flowchart TD\n"
            "    A -- yes --> B\n"
            "    B -->|confirm| C\n"
            "    subgraph Frontend Service\n"
            "        D --> E\n"
            "    end\n"
            "```\n"
        )
        rule = RuleD01()
        lines = content.splitlines(keepends=True)
        zones = scan_document_zones(lines)
        violations = rule.check(lines, zones)
        assert len(violations) == 0


class TestL5IdempotencyProperty:
    """Verify the core mathematical property: fix(fix(c)) == fix(c)."""

    @pytest.mark.parametrize(
        "sample",
        [
            "```math\nx + y = z\n```\n",
            "$$\n\\phi = \\frac{1}{2}\n$$\n",
            "Here is text $ x $ and $ y $ with $10 and $20.\n",
            "$$\n\\text{ave_shift} = 10\n$$\n",
            "$$\\operatorname*{max}_x f(x)$$\n",
            "| col 1 | col 2 |\n| :--- | :--- |\n| $||x|| < 1$ | `x` |\n",
            '> ```bash\n> echo "$a_b"\n> ```\n',
        ],
    )
    def test_idempotency_on_sample(self, sample: str) -> None:
        """L5: Running fix once vs twice must produce strictly identical results."""
        linter = Linter()
        pass1 = linter.lint_string(sample, fix=True).fixed_content
        pass2 = linter.lint_string(pass1, fix=True).fixed_content
        assert pass1 == pass2
