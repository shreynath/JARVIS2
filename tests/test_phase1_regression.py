"""Phase 1 closure regression suite — every previously fixed defect.

Each test maps to a real past defect. Authenticity requires observing
fail-then-pass (break/restore) for every test in this file.
"""

from __future__ import annotations

from core.ir.constraint import ConstraintEvaluation, ConstraintSeverity
from core.ir.constraint_graph import ConstraintGraph
from core.reasoning.physics_engine import PhysicsAnalysis
from core.reasoning.pipeline import SemanticKernelPipeline
from llm.ollama_client import DeterministicProvider
from validation.constraint_evaluator import ConstraintEvaluator
from validation.schema_validator import ValidationReport


PROMPT_9000_800 = "Design a 9000 RPM naturally aspirated V12 producing 800 horsepower."


def _run(prompt: str = PROMPT_9000_800):
    return SemanticKernelPipeline(provider=DeterministicProvider()).run(prompt)


def incoming_dep_sources(constraint_graph: ConstraintGraph, calc_id: str) -> set[str]:
    target = f"constraint_{calc_id}"
    sources: set[str] = set()
    for edge in constraint_graph.edges:
        if edge.edge_type.value != "traces_to" or edge.target_id != target:
            continue
        src = edge.source_id
        if src.startswith("constraint_"):
            remainder = src[len("constraint_") :]
            if remainder.startswith("calc_"):
                sources.add(remainder)
    return sources


# ---------------------------------------------------------------------------
# 1. Requirement propagation (was assemblies[].requirements == [])
# ---------------------------------------------------------------------------


def test_requirements_propagate_into_design_graph_assemblies():
    result = _run()
    assert result.requirement_spec.requirements, "compiled requirements empty"
    root = result.graph.assemblies[result.graph.root_id]
    assert root.requirements != [], "design graph assemblies still have requirements=[]"
    spec_ids = {r.id for r in result.requirement_spec.requirements}
    graph_ids = {r.id for r in root.requirements}
    assert spec_ids == graph_ids
    rpm = next(r for r in root.requirements if r.metric == "max_rpm")
    assert rpm.target_value == 9000.0


# ---------------------------------------------------------------------------
# 2. Physics chain completeness
# ---------------------------------------------------------------------------


REQUIRED_CALCS = (
    "calc_torque",
    "calc_displacement",
    "calc_stroke",
    "calc_mean_piston_speed",
    "calc_piston_acceleration",
    "calc_rod_loading",
    "calc_rod_stress_requirement",
    "calc_heat_rejection",
    "calc_combustion_side_temperature",
)


def test_physics_chain_completeness():
    result = _run()
    ids = {c.id for c in result.physics_analysis.calculations}
    missing = [cid for cid in REQUIRED_CALCS if cid not in ids]
    assert not missing, f"missing calculations: {missing}"

    # Dependency chain links are real
    assert result.physics_analysis.by_id("calc_mean_piston_speed").dependency_ids == ["calc_stroke"]
    assert set(result.physics_analysis.by_id("calc_rod_loading").dependency_ids) == {
        "calc_piston_acceleration",
        "calc_displacement",
    }
    assert result.physics_analysis.by_id("calc_rod_stress_requirement").dependency_ids == [
        "calc_rod_loading"
    ]
    assert result.physics_analysis.by_id("calc_combustion_side_temperature").dependency_ids == [
        "calc_heat_rejection"
    ]
    for cid in REQUIRED_CALCS:
        calc = result.physics_analysis.by_id(cid)
        assert calc is not None
        assert calc.confidence, f"{cid} missing confidence"
        assert calc.value_range is not None or calc.result is not None, f"{cid} missing result/range"


# ---------------------------------------------------------------------------
# 3. Material selection logic (threshold + cost/density, not max margin)
# ---------------------------------------------------------------------------


def test_material_selection_threshold_and_mass_sensitivity():
    result = _run()
    crank = result.graph.components["crankshaft"]
    rods = result.graph.components["connecting_rods"]

    assert crank.material_spec is not None
    assert rods.material_spec is not None

    # Crankshaft is not mass-sensitive → cheapest qualifying candidate (steel), not titanium.
    assert crank.material_spec.selection_metrics.get("mass_sensitive") is False
    assert crank.material != "Titanium 6Al-4V"
    assert "Steel" in crank.material or "steel" in crank.material.lower() or "Nitrided" in crank.material

    # Connecting rods are mass-sensitive at this operating point → titanium wins on density.
    assert rods.material_spec.selection_metrics.get("mass_sensitive") is True
    assert rods.material == "Titanium 6Al-4V"

    # Verify ranking order matches the stated rule for rods (density first among qualifiers).
    rankings = rods.material_spec.candidate_rankings
    assert rankings
    assert rankings[0]["name"] == "Titanium 6Al-4V"
    assert rankings[0]["hard_constraints_met"] is True


# ---------------------------------------------------------------------------
# 4. Validator correctness — hard failures must FAIL, never hidden PASS
# ---------------------------------------------------------------------------


def test_validator_fails_on_piston_speed_hard_limit():
    result = _run()
    assert result.validation_report is not None
    mps = result.physics_analysis.by_id("calc_mean_piston_speed")
    assert mps is not None and mps.passes is False
    assert result.validation_report.hard_violations > 0
    assert result.validation_report.status == "fail"
    assert any(
        e.id == "eval_calc_mean_piston_speed" and not e.passes
        for e in result.validation_report.constraint_evaluations
    )


def test_validator_accepts_synthetic_hard_limit_without_special_case():
    report = ValidationReport()
    ConstraintEvaluator().apply_to_report(
        report,
        [
            ConstraintEvaluation(
                id="eval_synthetic_phase1_regression",
                severity=ConstraintSeverity.HARD_LIMIT,
                value=99,
                limit=1,
                passes=False,
                source="synthetic_test",
                description="Synthetic hard-limit failure for regression authenticity",
            )
        ],
    )
    assert report.hard_violations == 1
    assert report.status == "fail"


# ---------------------------------------------------------------------------
# 5. Constraint graph integrity — dependency_ids == incoming calc edges
# ---------------------------------------------------------------------------


def test_constraint_graph_dependency_ids_match_edges():
    result = _run()
    physics_analysis: PhysicsAnalysis = result.physics_analysis
    for calc in physics_analysis.calculations:
        declared = set(calc.dependency_ids)
        actual = incoming_dep_sources(result.constraint_graph, calc.id)
        assert declared == actual, f"{calc.id}: declared {declared} != graph {actual}"

    rod = physics_analysis.by_id("calc_rod_loading")
    assert rod is not None
    assert incoming_dep_sources(result.constraint_graph, "calc_rod_loading") == {
        "calc_piston_acceleration",
        "calc_displacement",
    }
