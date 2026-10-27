"""The Conformance Crucible: Standalone 4-Stage Benchmark Pipeline for gfm-math-lint.

Validates documents against:
- Stage 1: Detection Completeness (100% known defects flagged)
- Stage 2: Idempotent Auto-Fix (Pass 1 fixes; Residual == 0; Pass 2 diff == 0)
- Stage 3: KaTeX Local Oracle (100% math ASTs compile without ParseError)
- Stage 4: GitHub API Live Oracle (0 literal $$, 0 tag pollution in math, 0 Mermaid \\n)

Opaque Benchmark Evaluation:
Outputs structural descriptions without dumping raw fixture text into agent context.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from conformance.extractor import extract_math_blocks
from conformance.oracles.github_oracle import render_gfm_offline_or_online, verify_rendered_gfm
from conformance.oracles.katex_oracle import KaTeXParseError, is_katex_available, run_local_katex_verification
from gfm_math_lint.linter import Linter

try:
    import yaml  # type: ignore[import-untyped]
except ImportError:
    import json as _json

    class _YamlFallback:
        @staticmethod
        def safe_load(stream: Any) -> Any:
            return _json.load(stream)

    yaml = _YamlFallback()


@dataclass
class StageFailure:
    """Record of a failure during a benchmark stage."""

    scenario_id: str
    stage: int
    stage_name: str
    rule_id: str
    structural_description: str
    failure_detail: str

    def to_opaque_summary(self) -> str:
        """Format an opaque one-line failure without dumping raw markdown fixture text."""
        rule_prefix = f" - {self.rule_id}" if self.rule_id else ""
        return (
            f"[FAIL] {self.scenario_id} Stage {self.stage} ({self.stage_name}){rule_prefix}: "
            f"{self.structural_description} -> {self.failure_detail}"
        )


@dataclass
class ScenarioResult:
    """Outcome of testing a single document scenario across all 4 stages."""

    scenario_id: str
    path: str
    category: str
    description: str
    stage_1_detection: bool = True
    stage_2_convergence: bool = True
    stage_3_katex: bool = True
    stage_4_github: bool = True
    failures: list[StageFailure] = field(default_factory=list)

    @property
    def passed_all(self) -> bool:
        return self.stage_1_detection and self.stage_2_convergence and self.stage_3_katex and self.stage_4_github


@dataclass
class CrucibleScorecard:
    """Overall benchmark results and gating scorecard."""

    total_scenarios: int = 0
    stage_1_passed: int = 0
    stage_2_passed: int = 0
    stage_3_passed: int = 0
    stage_4_passed: int = 0
    all_stages_passed: int = 0
    failures: list[StageFailure] = field(default_factory=list)

    @property
    def detection_rate(self) -> float:
        return (self.stage_1_passed / self.total_scenarios * 100.0) if self.total_scenarios else 0.0

    @property
    def convergence_rate(self) -> float:
        return (self.stage_2_passed / self.total_scenarios * 100.0) if self.total_scenarios else 0.0

    @property
    def katex_rate(self) -> float:
        return (self.stage_3_passed / self.total_scenarios * 100.0) if self.total_scenarios else 0.0

    @property
    def github_rate(self) -> float:
        return (self.stage_4_passed / self.total_scenarios * 100.0) if self.total_scenarios else 0.0

    @property
    def final_score(self) -> float:
        return (self.all_stages_passed / self.total_scenarios * 100.0) if self.total_scenarios else 0.0

    @property
    def gating_pass(self) -> bool:
        return self.total_scenarios > 0 and self.all_stages_passed == self.total_scenarios

    def format_text(self) -> str:
        status_text = "[GATING PASS]" if self.gating_pass else "[GATING FAIL]"
        lines = [
            "================ Conformance Crucible Scorecard ================",
            f"Scenarios Tested: {self.total_scenarios}",
            f"Detection Rate:   {self.stage_1_passed}/{self.total_scenarios} ({self.detection_rate:.1f}%)",
            f"Fix Convergence:  {self.stage_2_passed}/{self.total_scenarios} ({self.convergence_rate:.1f}%)",
            f"KaTeX AST Passes: {self.stage_3_passed}/{self.total_scenarios} ({self.katex_rate:.1f}%)",
            f"GitHub API HTML:  {self.stage_4_passed}/{self.total_scenarios} ({self.github_rate:.1f}%)",
            f"Final Score:      {self.final_score:.1f}% {status_text}",
            "================================================================",
        ]
        if self.failures:
            lines.append("\nOpaque Failure Audit (Raw fixture content shielded):")
            for f in self.failures:
                lines.append(f.to_opaque_summary())
        return "\n".join(lines)

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "total_scenarios": self.total_scenarios,
            "stage_1_detection": {
                "passed": self.stage_1_passed,
                "total": self.total_scenarios,
                "rate": round(self.detection_rate, 2),
            },
            "stage_2_convergence": {
                "passed": self.stage_2_passed,
                "total": self.total_scenarios,
                "rate": round(self.convergence_rate, 2),
            },
            "stage_3_katex": {
                "passed": self.stage_3_passed,
                "total": self.total_scenarios,
                "rate": round(self.katex_rate, 2),
            },
            "stage_4_github": {
                "passed": self.stage_4_passed,
                "total": self.total_scenarios,
                "rate": round(self.github_rate, 2),
            },
            "all_stages_passed": self.all_stages_passed,
            "final_score": round(self.final_score, 2),
            "gating_pass": self.gating_pass,
            "failures": [asdict(f) for f in self.failures],
        }


class ConformanceRunner:
    """Executes the 4-Stage Crucible benchmark against a manifest of scenarios."""

    def __init__(
        self,
        corpus_dir: Path,
        manifest_path: Path,
        offline: bool = False,
        verbose: bool = False,
    ) -> None:
        self.corpus_dir = corpus_dir
        self.manifest_path = manifest_path
        self.offline = offline
        self.verbose = verbose
        self.linter = Linter()
        self.katex_available = is_katex_available()

    def load_manifest(self) -> list[dict[str, Any]]:
        """Load and return scenario entries from the manifest."""
        if not self.manifest_path.exists():
            raise FileNotFoundError(f"Manifest not found at {self.manifest_path}")

        with self.manifest_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not isinstance(data, dict) or "scenarios" not in data:
            raise ValueError(f"Invalid manifest format in {self.manifest_path}")

        scenarios: list[dict[str, Any]] = data["scenarios"]
        return scenarios

    def evaluate_scenario(
        self,
        scenario: dict[str, Any],
        active_stages: set[int],
    ) -> ScenarioResult:
        """Run a single scenario through active crucible stages."""
        s_id = str(scenario.get("id", "unknown"))
        rel_path = str(scenario.get("path", ""))
        desc = str(scenario.get("description", ""))
        category = str(scenario.get("category", "synthetic"))
        expected_rules: list[str] = scenario.get("expected_rules", [])

        file_path = self.corpus_dir / rel_path
        res = ScenarioResult(
            scenario_id=s_id,
            path=rel_path,
            category=category,
            description=desc,
        )

        if not file_path.exists():
            res.stage_1_detection = False
            res.stage_2_convergence = False
            res.stage_3_katex = False
            res.stage_4_github = False
            res.failures.append(
                StageFailure(
                    scenario_id=s_id,
                    stage=0,
                    stage_name="File Access",
                    rule_id="",
                    structural_description=desc,
                    failure_detail=f"Fixture file missing: {rel_path}",
                )
            )
            return res

        content = file_path.read_text(encoding="utf-8")

        # -------------------------------------------------------------
        # Stage 1: Detection Completeness
        # -------------------------------------------------------------
        detected_rule_ids: set[str] = set()
        if 1 in active_stages:
            lint_check = self.linter.lint_string(content, file_path=str(file_path), fix=False)
            detected_rule_ids = {v.rule_id for v in lint_check.violations}

            if expected_rules:
                # Check that expected rules were detected
                missing_rules = [r for r in expected_rules if r not in detected_rule_ids]
                if missing_rules:
                    res.stage_1_detection = False
                    res.failures.append(
                        StageFailure(
                            scenario_id=s_id,
                            stage=1,
                            stage_name="Detection Completeness",
                            rule_id=",".join(missing_rules),
                            structural_description=desc,
                            failure_detail=f"Expected rules not detected: {missing_rules}",
                        )
                    )
            else:
                # Expect clean (0 violations)
                if lint_check.violations:
                    res.stage_1_detection = False
                    unexpected = [v.rule_id for v in lint_check.violations]
                    res.failures.append(
                        StageFailure(
                            scenario_id=s_id,
                            stage=1,
                            stage_name="Detection Completeness",
                            rule_id=",".join(unexpected),
                            structural_description=desc,
                            failure_detail=f"Unexpected false-positive violations: {unexpected}",
                        )
                    )

        # -------------------------------------------------------------
        # Stage 2: Idempotent Auto-Fix
        # -------------------------------------------------------------
        # Pass 1: Apply fix
        lint_fix_1 = self.linter.lint_string(content, file_path=str(file_path), fix=True)
        fixed_content_1 = lint_fix_1.fixed_content

        if 2 in active_stages:
            # Residual Check: check for leftover violations
            lint_residual = self.linter.lint_string(fixed_content_1, file_path=str(file_path), fix=False)
            if lint_residual.violations:
                res.stage_2_convergence = False
                res.failures.append(
                    StageFailure(
                        scenario_id=s_id,
                        stage=2,
                        stage_name="Fix Convergence",
                        rule_id=",".join({v.rule_id for v in lint_residual.violations}),
                        structural_description=desc,
                        failure_detail=f"Unresolved residual violations remain: {len(lint_residual.violations)}",
                    )
                )

            # Pass 2: Strictly idempotent second pass
            lint_fix_2 = self.linter.lint_string(fixed_content_1, file_path=str(file_path), fix=True)
            if lint_fix_2.fixed_content != fixed_content_1 or lint_fix_2.diff != "":
                res.stage_2_convergence = False
                res.failures.append(
                    StageFailure(
                        scenario_id=s_id,
                        stage=2,
                        stage_name="Fix Convergence",
                        rule_id="",
                        structural_description=desc,
                        failure_detail="Fix is not strictly idempotent; second pass produced non-empty diff",
                    )
                )

        # -------------------------------------------------------------
        # Stage 3: KaTeX Local Oracle
        # -------------------------------------------------------------
        if 3 in active_stages:
            math_blocks = extract_math_blocks(fixed_content_1)
            if self.katex_available and math_blocks:
                katex_errors = run_local_katex_verification(math_blocks)
                if katex_errors:
                    res.stage_3_katex = False
                    first_err: KaTeXParseError = katex_errors[0]
                    res.failures.append(
                        StageFailure(
                            scenario_id=s_id,
                            stage=3,
                            stage_name="KaTeX Local Oracle",
                            rule_id="",
                            structural_description=desc,
                            failure_detail=f"KaTeX ParseError: {first_err.error_message}",
                        )
                    )

        # -------------------------------------------------------------
        # Stage 4: GitHub API Live Oracle
        # -------------------------------------------------------------
        if 4 in active_stages:
            rendered_html = render_gfm_offline_or_online(fixed_content_1, offline=self.offline)
            anomalies = verify_rendered_gfm(rendered_html, file_path=str(file_path))
            if anomalies:
                res.stage_4_github = False
                res.failures.append(
                    StageFailure(
                        scenario_id=s_id,
                        stage=4,
                        stage_name="GitHub API HTML",
                        rule_id="",
                        structural_description=desc,
                        failure_detail=f"HTML Rendering Anomalies: {anomalies[0]}",
                    )
                )

        return res

    def run(
        self,
        stages: set[int] | None = None,
        category: str = "all",
        scenario_id: str | None = None,
    ) -> CrucibleScorecard:
        """Execute the conformance runner across selected scenarios."""
        active_stages = stages if stages is not None else {1, 2, 3, 4}
        all_scenarios = self.load_manifest()

        filtered: list[dict[str, Any]] = []
        for sc in all_scenarios:
            if scenario_id and sc.get("id") != scenario_id:
                continue
            if category != "all" and sc.get("category") != category:
                continue
            filtered.append(sc)

        scorecard = CrucibleScorecard(total_scenarios=len(filtered))

        for sc in filtered:
            res = self.evaluate_scenario(sc, active_stages)
            if res.stage_1_detection:
                scorecard.stage_1_passed += 1
            if res.stage_2_convergence:
                scorecard.stage_2_passed += 1
            if res.stage_3_katex:
                scorecard.stage_3_passed += 1
            if res.stage_4_github:
                scorecard.stage_4_passed += 1
            if res.passed_all:
                scorecard.all_stages_passed += 1

            if res.failures:
                scorecard.failures.extend(res.failures)

            if self.verbose:
                status = "PASS" if res.passed_all else "FAIL"
                print(f"[{status}] {res.scenario_id}: {res.description}")

        return scorecard


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="python -m conformance.runner",
        description="The Conformance Crucible: 4-Stage Gating Benchmark Pipeline.",
    )
    parser.add_argument(
        "--corpus-dir",
        type=Path,
        default=Path("conformance/corpus"),
        help="Root path to the conformance corpus.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("conformance/corpus/manifest.yaml"),
        help="Path to manifest.yaml.",
    )
    parser.add_argument(
        "--stage",
        type=str,
        default="all",
        help="Stages to execute: 1, 2, 3, 4, or all (comma-separated, e.g. '1,2').",
    )
    parser.add_argument(
        "--category",
        type=str,
        default="all",
        choices=["all", "synthetic", "wild", "regressions"],
        help="Filter scenarios by category.",
    )
    parser.add_argument(
        "--id",
        type=str,
        default=None,
        help="Run a specific scenario by ID (e.g. syn_001, reg_01).",
    )
    parser.add_argument(
        "--format",
        type=str,
        default="text",
        choices=["text", "json"],
        help="Output format: text (scorecard) or json.",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Force offline mode (skip live GitHub API network calls in Stage 4).",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with non-zero status if any scenario fails gating.",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print per-scenario status lines.",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help="Optional file path to write scorecard output.",
    )

    args = parser.parse_args()

    # Determine active stages
    if args.stage.lower() == "all":
        active_stages = {1, 2, 3, 4}
    else:
        try:
            active_stages = {int(s.strip()) for s in args.stage.split(",") if s.strip()}
        except ValueError:
            print(f"Error: Invalid --stage specification '{args.stage}'. Use 1, 2, 3, 4, or all.", file=sys.stderr)
            return 2

    runner = ConformanceRunner(
        corpus_dir=args.corpus_dir,
        manifest_path=args.manifest,
        offline=args.offline,
        verbose=args.verbose,
    )

    scorecard = runner.run(
        stages=active_stages,
        category=args.category,
        scenario_id=args.id,
    )

    output_str = json.dumps(scorecard.to_json_dict(), indent=2) if args.format == "json" else scorecard.format_text()

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output_str, encoding="utf-8")

    print(output_str)

    if args.strict and not scorecard.gating_pass:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
