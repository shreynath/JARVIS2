"""Tests for full semantic kernel pipeline."""

import json
from pathlib import Path

from core.reasoning.pipeline import SemanticKernelPipeline
from llm.ollama_client import DeterministicProvider


def test_pipeline_end_to_end(tmp_path: Path):
    pipeline = SemanticKernelPipeline(provider=DeterministicProvider())
    result = pipeline.run("Create a vehicle engine specification")

    assert result.intent.object_type == "internal_combustion_engine"
    assert result.functional_analysis is not None
    assert len(result.functional_analysis.functions) > 0
    assert len(result.graph.assemblies) > 0
    assert len(result.graph.components) > 0
    assert len(result.graph.assumptions) > 0
    assert len(result.critic_issues) > 0
    assert result.validation_report is not None


def test_pipeline_writes_outputs(tmp_path: Path):
    pipeline = SemanticKernelPipeline(provider=DeterministicProvider())
    result = pipeline.run("Create a vehicle engine specification")
    output_dir = pipeline.write_outputs(result, tmp_path)

    assert (output_dir / "engine_design_graph.json").exists()
    assert (output_dir / "requirement_specification.json").exists()
    assert (output_dir / "physics_analysis.json").exists()
    assert (output_dir / "assumptions.json").exists()
    assert (output_dir / "validation_report.json").exists()
    assert (output_dir / "pipeline_status.json").exists()

    graph_data = json.loads((output_dir / "engine_design_graph.json").read_text())
    assert graph_data["type"] == "internal_combustion_engine"
    assert len(graph_data["components"]) > 0
    assert len(graph_data["assemblies"]) > 0
    assert "functional_analysis" in graph_data
    assert "requirement_specification" in graph_data
    assert "physics_analysis" in graph_data
    assert "constraint_graph" in graph_data
    assert graph_data["degraded"] is True
    assert graph_data["provider_used"] == "deterministic_fallback"

    status = json.loads((output_dir / "pipeline_status.json").read_text())
    assert status["degraded"] is True
    assert "warning" in status


def test_vague_prompt_initializes_requirements_and_constraint_graph():
    pipeline = SemanticKernelPipeline(provider=DeterministicProvider())
    result = pipeline.run("Create a vehicle engine specification")

    assert result.requirement_spec.requirements
    assert any(r.metric == "object_type" for r in result.requirement_spec.requirements)
    assert result.constraint_graph.nodes["req_object_type"].node_type == "requirement"
    root = result.graph.assemblies[result.graph.root_id]
    assert root.requirements
    assert result.validation_report is not None
    assert result.validation_report.missing_decisions > 0


def test_physics_assumptions_propagate_to_validation():
    pipeline = SemanticKernelPipeline(provider=DeterministicProvider())
    result = pipeline.run("Design a 9000 RPM naturally aspirated V12 engine producing 800 hp")

    assert any(c.assumptions for c in result.physics_analysis.calculations)
    assert result.validation_report is not None
    assert result.validation_report.unverified_assumptions > 0


def test_pipeline_no_undefined_references():
    pipeline = SemanticKernelPipeline(provider=DeterministicProvider())
    result = pipeline.run("Create a vehicle engine specification")

    all_ids = result.graph.all_node_ids()
    for assembly in result.graph.assemblies.values():
        for member_id in assembly.member_ids:
            assert member_id in all_ids
        for child_id in assembly.children:
            assert child_id in all_ids
