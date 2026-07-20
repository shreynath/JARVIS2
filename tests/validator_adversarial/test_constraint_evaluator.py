"""Adversarial rejection tests — ConstraintEvaluator (≥3 broken fixtures)."""

from validation.constraint_evaluator import ConstraintEvaluator
from validation.schema_validator import ValidationReport

from adversarial_fixtures import (
    graph_carbon_fiber_combustion,
    graph_excessive_piston_speed,
    graph_glass_crankshaft,
    graph_wood_engine,
    graph_yield_strength_violation,
    minimal_graph,
)


def _eval_and_apply(graph, physics=None):
    evaluator = ConstraintEvaluator()
    evaluations = evaluator.collect(graph, physics)
    report = ValidationReport()
    evaluator.apply_to_report(report, evaluations)
    return report, evaluations


def test_rejects_carbon_fiber_in_combustion_context():
    report, evals = _eval_and_apply(graph_carbon_fiber_combustion())
    assert not report.passed
    assert any(e.passes is False and e.source == "material_suitability" for e in evals)


def test_rejects_wood_in_engine_block():
    report, evals = _eval_and_apply(graph_wood_engine())
    assert not report.passed
    assert any("wood" in (e.description or "").lower() or "timber" in (e.description or "").lower() for e in evals)


def test_rejects_glass_crankshaft():
    report, evals = _eval_and_apply(graph_glass_crankshaft())
    assert not report.passed
    assert any(e.source == "material_suitability" and not e.passes for e in evals)


def test_rejects_yield_strength_below_requirement():
    graph, physics = graph_yield_strength_violation()
    report, _ = _eval_and_apply(graph, physics)
    assert not report.passed
    assert report.hard_violations >= 1


def test_rejects_excessive_mean_piston_speed():
    graph, physics = graph_excessive_piston_speed()
    report, evals = _eval_and_apply(graph, physics)
    assert not report.passed
    assert any(e.id == "eval_calc_mean_piston_speed" and not e.passes for e in evals)


def test_accepts_valid_minimal_graph_without_physics():
    report, evals = _eval_and_apply(minimal_graph())
    failed_hard = [e for e in evals if not e.passes and str(e.severity) == "hard_limit"]
    assert not failed_hard
    assert report.passed
