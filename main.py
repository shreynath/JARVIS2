"""JARVIS 2.0 — Engineering Semantic Kernel CLI."""

from __future__ import annotations

import sys

from core.reasoning.pipeline import PipelineError, SemanticKernelPipeline
from llm.env_loader import load_dotenv


def main() -> None:
    load_dotenv()

    if len(sys.argv) > 1:
        user_input = " ".join(sys.argv[1:])
    else:
        user_input = input("> ").strip()

    if not user_input:
        print("No input provided.")
        sys.exit(1)

    pipeline = SemanticKernelPipeline()

    # Degradation warning MUST appear before any design output (remediation A2).
    if pipeline.degraded and pipeline.warning:
        print(pipeline.warning)
        print()

    print("JARVIS 2.0 — Engineering Semantic Kernel")
    print("Phase 1: Natural language → validated engineering design graph")
    print(f"Provider: {pipeline.provider_used}  degraded={pipeline.degraded}")
    print()

    try:
        result = pipeline.run(user_input)
    except PipelineError as exc:
        print(f"Error [{exc.code}]: {exc.message}")
        sys.exit(2)

    output_dir = pipeline.write_outputs(result)

    if result.degraded and result.warning:
        # Re-state after run so it remains visible next to the summary.
        print(result.warning)

    print(f"\nIntent: {result.intent.design_goal}")
    print(f"Object type: {result.intent.object_type}")
    print(f"Provider: {result.provider_used}")
    print(f"Degraded: {result.degraded}")
    print(f"EvaluationStatus: {result.evaluation_status.value.upper()}")
    if result.blocking_issues:
        print(f"Blocking issues: {len(result.blocking_issues)}")
        for issue in result.blocking_issues:
            print(f"  - [{issue.code}] {issue.message}")
    print(f"Physics: {'None' if result.physics_analysis is None else 'computed'}")
    materials_assigned = sum(1 for c in result.graph.components.values() if c.material)
    print(
        f"Materials: {'None' if result.evaluation_status.value == 'incomplete' and result.physics_analysis is None else materials_assigned}"
    )
    print(f"Components: {len(result.graph.components)}")
    print(f"Assumptions: {len(result.graph.assumptions)}")
    print(f"Critic issues: {len(result.critic_issues)}")
    if result.validation_report:
        print(
            "Validation: "
            f"{result.validation_report.status.upper()} "
            f"(hard violations: {result.validation_report.hard_violations}, "
            f"warnings: {result.validation_report.warnings}, "
            f"missing decisions: {result.validation_report.missing_decisions}, "
            f"unverified assumptions: {result.validation_report.unverified_assumptions}, "
            f"unvalidated hard limits: {result.validation_report.unvalidated_hard_limits})"
        )
    print(f"\nOutput written to {output_dir}/")


if __name__ == "__main__":
    main()
