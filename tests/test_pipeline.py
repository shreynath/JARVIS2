"""Tests for full semantic kernel pipeline."""

import json
from pathlib import Path

from core.reasoning.pipeline import SemanticKernelPipeline
from llm.ollama_client import DeterministicProvider


def test_pipeline_end_to_end(tmp_path: Path):
    pipeline = SemanticKernelPipeline(provider=DeterministicProvider())
    result = pipeline.run("Create a vehicle engine specification")

    assert result.intent.object_type == "internal_combustion_engine"
    assert len(result.graph.components) > 1
    assert len(result.graph.assumptions) > 0
    assert result.validation_report is not None


def test_pipeline_writes_outputs(tmp_path: Path):
    pipeline = SemanticKernelPipeline(provider=DeterministicProvider())
    result = pipeline.run("Create a vehicle engine specification")
    output_dir = pipeline.write_outputs(result, tmp_path)

    assert (output_dir / "engine_design_graph.json").exists()
    assert (output_dir / "assumptions.json").exists()
    assert (output_dir / "validation_report.json").exists()

    graph_data = json.loads((output_dir / "engine_design_graph.json").read_text())
    assert graph_data["type"] == "internal_combustion_engine"
    assert len(graph_data["components"]) > 0


def test_pipeline_no_undefined_references():
    pipeline = SemanticKernelPipeline(provider=DeterministicProvider())
    result = pipeline.run("Create a vehicle engine specification")

    all_ids = result.graph.all_node_ids()
    for comp in result.graph.components.values():
        for child_id in comp.children:
            assert child_id in all_ids
