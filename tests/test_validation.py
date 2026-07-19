"""Tests for validation layer."""

from core.ir.component import ComponentNode
from core.ir.constraint import Constraint, ConstraintSeverity
from core.ir.design_graph import EngineeringDesignGraph, EngineeringIntent
from core.ir.material import MaterialSpec
from validation.consistency import ConsistencyChecker
from validation.physics_rules import PhysicsRulesEngine
from validation.schema_validator import SchemaValidator, ValidationReport


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
    from validation.constraint_evaluator import ConstraintEvaluator

    graph = _graph_valid()
    graph.components["block"].material = "Carbon fiber"
    evaluations = ConstraintEvaluator().collect(graph, None)
    report = ValidationReport()
    ConstraintEvaluator().apply_to_report(report, evaluations)
    assert not report.passed
    assert any("carbon fiber" in i.message.lower() for i in report.issues)


def test_physics_warns_missing_material():
    graph = _graph_valid()
    graph.components["block"].material = None
    report = PhysicsRulesEngine().validate(graph)
    assert any("no material" in i.message for i in report.issues)


def test_hard_temperature_limit_violation_fails_validation():
    from validation.constraint_evaluator import ConstraintEvaluator

    graph = _graph_valid()
    block = graph.components["block"]
    block.material = "Aluminum 356-T6"
    block.material_spec = MaterialSpec(
        name="Aluminum 356-T6",
        density_kg_m3=2680,
        yield_strength_mpa=230,
        fatigue_strength_mpa=95,
        thermal_conductivity_w_mk=151,
        temperature_limit_c=200,
    )
    # Physics-derived requirement that exceeds material rating.
    from core.reasoning.physics_engine import PhysicsAnalysis

    physics = PhysicsAnalysis(
        constraints=[
            Constraint(
                id="constraint_required_temp",
                type="minimum_temperature_limit",
                description="Cylinder head must tolerate estimated operating temperature",
                component_id="block",
                value=250,
                unit="C",
                severity=ConstraintSeverity.HARD_LIMIT,
                source="physics_engine",
            )
        ]
    )

    evaluations = ConstraintEvaluator().collect(graph, physics)
    report = ValidationReport()
    ConstraintEvaluator().apply_to_report(report, evaluations)

    assert not report.passed
    assert report.status == "fail"
    assert report.hard_violations == 1
    assert any("250" in issue.message for issue in report.issues)
