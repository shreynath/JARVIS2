"""Tests for IR design graph."""

import json

from core.ir.component import ComponentNode
from core.ir.constraint import Assumption, ConstraintSpec
from core.ir.design_graph import EngineeringDesignGraph, EngineeringIntent


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
