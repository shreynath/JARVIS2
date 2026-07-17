"""Example: generate a vehicle engine specification."""

from core.reasoning.pipeline import SemanticKernelPipeline
from llm.ollama_client import DeterministicProvider


def run_example() -> None:
    provider = DeterministicProvider()
    pipeline = SemanticKernelPipeline(provider=provider)

    result = pipeline.run("Create a vehicle engine specification")
    output_dir = pipeline.write_outputs(result)

    print(f"Generated design graph with {len(result.graph.components)} components")
    print(f"Output: {output_dir}/")
    print(f"Validation passed: {result.validation_report.passed if result.validation_report else False}")


if __name__ == "__main__":
    run_example()
