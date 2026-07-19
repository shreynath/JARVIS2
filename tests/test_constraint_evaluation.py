"""Tests for ConstraintEvaluation aggregator architecture (Fix 1)."""

from __future__ import annotations

from core.ir.component import ComponentNode
from core.ir.constraint import Constraint, ConstraintEvaluation, ConstraintSeverity
from core.ir.design_graph import EngineeringDesignGraph, EngineeringIntent
from core.ir.material import MaterialSpec
from core.reasoning.physics_engine import KnowledgeState, PhysicsAnalysis, PhysicsCalculation
from core.reasoning.pipeline import SemanticKernelPipeline
from llm.ollama_client import DeterministicProvider
from validation.constraint_evaluator import ConstraintEvaluator
from validation.schema_validator import ValidationReport


def test_synthetic_hard_limit_evaluation_increments_hard_violations():
    """Prove validator architecture: any ConstraintEvaluation(hard_limit, passes=False)
    increments hard_violations with no subsystem-specific special case."""
    report = ValidationReport()
    evaluator = ConstraintEvaluator()
    synthetic = ConstraintEvaluation(
        id="eval_synthetic_test",
        severity=ConstraintSeverity.HARD_LIMIT,
        value=999.0,
        limit=100.0,
        passes=False,
        source="synthetic_test",
        component_id=None,
        dependency_ids=[],
        description="Synthetic hard-limit failure for architecture test",
    )
    evaluator.apply_to_report(report, [synthetic])

    assert report.hard_violations == 1
    assert report.status == "fail"
    assert not report.passed
    assert any("Synthetic hard-limit failure" in issue.message for issue in report.issues)


def test_failed_piston_speed_calculation_is_hard_violation():
    graph = EngineeringDesignGraph(
        name="engine",
        type="internal_combustion_engine",
        intent=EngineeringIntent(object_type="internal_combustion_engine", design_goal="test"),
        root_id="root",
    )
    graph.add_component(ComponentNode(id="root", name="Engine", function="Root"))
    physics = PhysicsAnalysis(
        calculations=[
            PhysicsCalculation(
                id="calc_mean_piston_speed",
                name="Mean piston speed",
                formula="Vp = 2 × stroke × RPM / 60",
                result=23.78,
                value_range=(20.89, 26.68),
                unit="m/s",
                assessment="Mean piston speed is extreme",
                passes=False,
                knowledge_state=KnowledgeState.DERIVED,
            )
        ]
    )
    evaluations = ConstraintEvaluator().collect(graph, physics)
    report = ValidationReport()
    ConstraintEvaluator().apply_to_report(report, evaluations)

    assert report.hard_violations >= 1
    assert report.status == "fail"
    mps_eval = next(e for e in evaluations if e.id == "eval_calc_mean_piston_speed")
    assert mps_eval.passes is False
    assert mps_eval.severity == ConstraintSeverity.HARD_LIMIT
    assert mps_eval.limit == 26.0


def test_material_temperature_shortfall_emits_evaluation():
    graph = EngineeringDesignGraph(
        name="engine",
        type="internal_combustion_engine",
        intent=EngineeringIntent(object_type="internal_combustion_engine", design_goal="test"),
        root_id="root",
    )
    block = ComponentNode(
        id="cylinder_head",
        name="Cylinder Head",
        function="Seals combustion chambers",
        material="Aluminum 356-T6",
        material_spec=MaterialSpec(
            name="Aluminum 356-T6",
            density_kg_m3=2680,
            yield_strength_mpa=230,
            fatigue_strength_mpa=95,
            thermal_conductivity_w_mk=151,
            temperature_limit_c=200,
        ),
    )
    graph.add_component(block)
    physics = PhysicsAnalysis(
        constraints=[
            Constraint(
                id="constraint_physics_temperature_cylinder_head",
                type="minimum_temperature_limit",
                description="temp",
                component_id="cylinder_head",
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

    assert report.hard_violations == 1
    assert any(e.component_id == "cylinder_head" and not e.passes for e in evaluations)


def test_pipeline_9000rpm_800hp_reports_hard_violation():
    pipeline = SemanticKernelPipeline(provider=DeterministicProvider())
    result = pipeline.run(
        "Design a 9000 RPM naturally aspirated V12 producing 800 horsepower."
    )
    assert result.validation_report is not None
    assert result.validation_report.hard_violations > 0
    assert result.validation_report.status == "fail"
    assert any(
        "piston speed" in issue.message.lower() or "calc_mean_piston_speed" in issue.message
        for issue in result.validation_report.issues
    )
    mps = result.physics_analysis.by_id("calc_mean_piston_speed")
    assert mps is not None
    assert mps.passes is False
