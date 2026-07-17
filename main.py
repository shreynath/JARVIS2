"""JARVIS 2.0 — Engineering Semantic Kernel CLI."""

from __future__ import annotations

import sys

from core.reasoning.pipeline import SemanticKernelPipeline


def main() -> None:
    print("JARVIS 2.0 — Engineering Semantic Kernel")
    print("Phase 1: Natural language → validated engineering design graph")
    print()

    if len(sys.argv) > 1:
        user_input = " ".join(sys.argv[1:])
    else:
        user_input = input("> ").strip()

    if not user_input:
        print("No input provided.")
        sys.exit(1)

    pipeline = SemanticKernelPipeline()
    result = pipeline.run(user_input)
    output_dir = pipeline.write_outputs(result)

    print(f"\nIntent: {result.intent.design_goal}")
    print(f"Object type: {result.intent.object_type}")
    print(f"Components: {len(result.graph.components)}")
    print(f"Assumptions: {len(result.graph.assumptions)}")
    print(f"Critic issues: {len(result.critic_issues)}")
    if result.validation_report:
        status = "PASSED" if result.validation_report.passed else "FAILED"
        print(f"Validation: {status} ({len(result.validation_report.issues)} issues)")
    print(f"\nOutput written to {output_dir}/")


if __name__ == "__main__":
    main()
