"""Tests for IR design graph."""

import json

from core.ir.component import ComponentNode
from core.ir.constraint import Assumption, ConstraintSpec
from core.ir.design_graph import EngineeringDesignGraph, EngineeringIntent
from core.reasoning.pipeline import SemanticKernelPipeline
from llm.ollama_client import DeterministicProvider


def _sample_intent() -> EngineeringIntent:
    return EngineeringIntent(
        object_type="internal_combustion_engine",
        design_goal="vehicle engine specification",
        unknowns=["displacement"],
        required_domains=["thermodynamics"],
        raw_input="Create a vehicle engine specification",
    )


def test_engineering_intent_round_trip():
    intent = _sample_intent()
    data = intent.model_dump()
    restored = EngineeringIntent.model_validate(data)
    assert restored.object_type == intent.object_type
    assert restored.design_goal == intent.design_goal


def test_design_graph_add_component():
    graph = EngineeringDesignGraph(
        name="test engine",
        type="internal_combustion_engine",
        intent=_sample_intent(),
        root_id="root",
    )
    root = ComponentNode(
        id="root",
        name="Engine",
        function="Root assembly",
        children=["block"],
    )
    block = ComponentNode(
        id="block",
        name="Engine Block",
        function="Structural housing",
        material="Aluminum alloy",
        parent_id="root",
        is_leaf=True,
    )
    graph.add_component(root)
    graph.add_component(block)

    assert len(graph.components) == 2
    assert "block" in graph.components["root"].children


def test_design_graph_to_spec_dict():
    graph = EngineeringDesignGraph(
        name="test",
        type="internal_combustion_engine",
        intent=_sample_intent(),
        root_id="root",
    )
    graph.add_component(ComponentNode(
        id="root",
        name="Engine",
        function="Root",
        children=["block"],
    ))
    graph.add_component(ComponentNode(
        id="block",
        name="Block",
        function="Housing",
        material="Aluminum alloy",
        parent_id="root",
        is_leaf=True,
    ))

    spec = graph.to_spec_dict()
    serialized = json.dumps(spec)
    assert "internal_combustion_engine" in serialized
    assert "Aluminum alloy" in serialized


def test_constraint_spec():
    cs = ConstraintSpec(type="performance", description="High power", priority="high")
    assert cs.priority == "high"


def test_constraint_graph_contains_physics_and_material_constraints():
    result = SemanticKernelPipeline(provider=DeterministicProvider()).run(
        "Design a 9000 RPM naturally aspirated V12 engine producing 800 hp"
    )

    node_ids = set(result.constraint_graph.nodes)
    assert "constraint_physics_rod_stress" in node_ids
    assert any(node_id.startswith("constraint_thermal_") for node_id in node_ids)
    assert any(
        edge.source_id == "constraint_physics_rod_stress"
        and edge.target_id == "connecting_rods"
        for edge in result.constraint_graph.edges
    )


def test_thermal_constraint_edges_have_component_specific_causality():
    result = SemanticKernelPipeline(provider=DeterministicProvider()).run(
        "Design a 9000 RPM naturally aspirated V12 producing 800 horsepower."
    )

    def thermal_trace_description(component_id: str) -> str:
        thermal_constraint_ids = [
            edge.source_id
            for edge in result.constraint_graph.edges
            if edge.edge_type == "constraint_applies_to"
            and edge.target_id == component_id
            and edge.source_id.startswith("constraint_thermal_")
        ]
        assert thermal_constraint_ids
        trace = next(
            edge
            for edge in result.constraint_graph.edges
            if edge.edge_type == "traces_to" and edge.target_id == thermal_constraint_ids[0]
        )
        return trace.description

    radiator = thermal_trace_description("radiator")
    crankshaft = thermal_trace_description("crankshaft")
    valves = thermal_trace_description("valves")
    camshaft = thermal_trace_description("camshaft")
    oil_pan = thermal_trace_description("oil_pan")

    assert "combustion heat rejection" in radiator
    assert "friction/mechanical-load heating" in crankshaft
    assert "combustion/exhaust gas exposure" in valves
    assert "friction/mechanical-load heating" in camshaft
    assert "combustion/exhaust gas exposure" not in camshaft
    assert "local operating thermal environment" not in oil_pan
    assert "proximity heat" in oil_pan
    assert len({radiator, crankshaft, valves, camshaft, oil_pan}) == 5
