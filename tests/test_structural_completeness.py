"""Phase E — structural material completeness gate."""

from __future__ import annotations

import pytest

from core.evaluation.evaluation_status import EvaluationStatus
from core.ir.component import ComponentNode
from core.ir.design_graph import EngineeringDesignGraph, EngineeringIntent
from core.materials.structural_completeness import (
    structural_materials_complete,
    unassigned_structural_components,
)
from core.reasoning.bridge_physics_engine import analyze_bridge
from core.reasoning.pipeline import SemanticKernelPipeline
from core.reasoning.requirement_compiler import RequirementCompiler
from llm.ollama_client import DeterministicProvider


def _graph_with_component(component_id: str, *, material: str | None) -> EngineeringDesignGraph:
    graph = EngineeringDesignGraph(
        name="structural_test",
        type="steel_truss_bridge",
        intent=EngineeringIntent(object_type="steel_truss_bridge", design_goal="test"),
        root_id="root",
    )
    graph.add_component(
        ComponentNode(
            id=component_id,
            name=component_id,
            function="structural member",
            material=material,
            is_leaf=True,
        )
    )
    return graph


def test_unassigned_structural_components_detects_missing_material():
    graph = _graph_with_component("top_chord", material=None)
    missing = unassigned_structural_components(graph)
    assert "top_chord" in missing
    assert not structural_materials_complete(graph)


def test_structural_materials_complete_when_assigned():
    graph = _graph_with_component("top_chord", material="ASTM A572 Structural Steel")
    assert structural_materials_complete(graph)
    assert unassigned_structural_components(graph) == []


def test_chair_pipeline_incomplete_when_structural_materials_unassigned():
    pipeline = SemanticKernelPipeline(provider=DeterministicProvider())
    result = pipeline.run("design a wooden dining chair")
    missing = unassigned_structural_components(result.graph)
    if not missing:
        pytest.skip("decomposition did not emit registered structural component ids")
    assert result.evaluation_status != EvaluationStatus.COMPLETE
    assert result.validation_report is not None
    assert not result.validation_report.evaluation_complete


def test_bridge_truss_members_assigned_when_physics_computed():
    compiler = RequirementCompiler()
    intent = EngineeringIntent(
        object_type="steel_truss_bridge",
        design_goal="40 m truss",
        raw_input="design a steel truss bridge spanning 40 meters",
    )
    spec = compiler.compile(intent)
    physics = analyze_bridge(spec)

    graph = EngineeringDesignGraph(
        name="bridge",
        type="steel_truss_bridge",
        intent=intent,
        root_id="root",
    )
    for comp_id in ("top_chord", "bottom_chord", "web_diagonals"):
        graph.add_component(
            ComponentNode(
                id=comp_id,
                name=comp_id,
                function="truss member",
                is_leaf=True,
            )
        )

    from core.reasoning.material_assigner import MaterialAssigner

    graph = MaterialAssigner().assign(graph, spec, physics)
    assert graph.components["top_chord"].material is not None
    assert structural_materials_complete(graph)


def test_span_m_extracted_for_bridge_prompt():
    compiler = RequirementCompiler()
    intent = EngineeringIntent(
        object_type="steel_truss_bridge",
        design_goal="span bridge",
        raw_input="design a steel truss bridge spanning 40 meters",
    )
    spec = compiler.compile(intent)
    assert spec.resolved_parameters.get("span_m") == 40.0
