"""Tests for validation layer."""

from core.ir.component import ComponentNode
from core.ir.design_graph import EngineeringDesignGraph, EngineeringIntent
from validation.consistency import ConsistencyChecker
from validation.physics_rules import PhysicsRulesEngine
from validation.schema_validator import SchemaValidator


def _graph_with_missing_ref() -> EngineeringDesignGraph:
    graph = EngineeringDesignGraph(
        name="bad",
        type="test",
        intent=EngineeringIntent(object_type="test", design_goal="test"),
        root_id="root",
    )
    graph.add_component(ComponentNode(
        id="root", name="Root", function="Root", children=["missing_child"],
    ))
    return graph


def _graph_valid() -> EngineeringDesignGraph:
    graph = EngineeringDesignGraph(
        name="engine",
        type="internal_combustion_engine",
        intent=EngineeringIntent(
            object_type="internal_combustion_engine",
            design_goal="test engine",
        ),
        root_id="root",
    )
    graph.add_component(ComponentNode(
        id="root", name="Engine", function="Root", children=["block"],
    ))
    graph.add_component(ComponentNode(
        id="block",
        name="Block",
        function="Structural housing for combustion cylinders",
        material="Aluminum alloy",
        parent_id="root",
        is_leaf=True,
    ))
    return graph


def test_schema_validator_passes_valid_graph():
    report = SchemaValidator().validate(_graph_valid())
    assert report.passed


def test_consistency_detects_missing_ref():
    report = ConsistencyChecker().validate(_graph_with_missing_ref())
    assert not report.passed
    assert any("undefined child" in i.message for i in report.issues)


def test_physics_detects_bad_material():
    graph = _graph_valid()
    graph.components["block"].material = "Carbon fiber"
    report = PhysicsRulesEngine().validate(graph)
    assert not report.passed
    assert any("carbon fiber" in i.message.lower() for i in report.issues)


def test_physics_warns_missing_material():
    graph = _graph_valid()
    graph.components["block"].material = None
    report = PhysicsRulesEngine().validate(graph)
    assert any("no material" in i.message for i in report.issues)
