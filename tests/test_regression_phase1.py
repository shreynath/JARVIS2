"""Phase 1 regression guards — defects from prior and current directives.

Each assertion maps to a real defect that was found and fixed. Temporarily
reverting a fix should make the corresponding test fail.
"""

from __future__ import annotations

from core.ir.constraint import ConstraintEvaluation, ConstraintSeverity
from core.reasoning.pipeline import SemanticKernelPipeline
from llm.ollama_client import DeterministicProvider
from validation.constraint_evaluator import ConstraintEvaluator
from validation.schema_validator import ValidationReport


PROMPT_9000_800 = "Design a 9000 RPM naturally aspirated V12 producing 800 horsepower."


def _run(prompt: str = PROMPT_9000_800):
    return SemanticKernelPipeline(provider=DeterministicProvider()).run(prompt)


def test_horsepower_extraction_internally_consistent():
    """Defect 1 (prior): horsepower extracted inconsistently across artifacts."""
    result = _run()
    assert result.requirement_spec.resolved_parameters["target_horsepower"] == 800
    hp_decision = next(d for d in result.requirement_spec.required_decisions if d.id == "target_horsepower")
    assert hp_decision.resolved_value == "800"
    hp_req = next(r for r in result.requirement_spec.requirements if r.metric == "horsepower")
    assert hp_req.target_value == 800


def test_physics_layer_computes_partial_results_with_piston_speed():
    """Defect 2 (prior): physics layer must compute real dependency chain."""
    result = _run()
    calcs = result.physics_analysis.calculations
    assert len(calcs) > 0
    mps = result.physics_analysis.by_id("calc_mean_piston_speed")
    assert mps is not None
    assert mps.result is not None
    assert mps.value_range is not None
    assert mps.dependency_ids == ["calc_stroke"]
    assert result.physics_analysis.by_id("calc_rod_stress_requirement") is not None


def test_material_selection_threshold_satisfying_not_margin_maximizing():
    """Defect 3 (prior): non-mass-sensitive parts pick cheapest qualifier, not max margin."""
    result = _run()
    crank = result.graph.components["crankshaft"]
    assert crank.material_spec is not None
    assert crank.material_spec.selection_metrics.get("mass_sensitive") is False
    assert crank.material != "Titanium 6Al-4V"
    # Cheapest qualifying shaft candidate under current catalog.
    assert "Steel" in crank.material or "steel" in crank.material.lower() or "Nitrided" in crank.material


def test_validator_aggregates_all_constraint_evaluation_sources():
    """Fix 1: failed physics calc hard_limit must count as hard violation."""
    result = _run()
    assert result.validation_report is not None
    assert result.validation_report.hard_violations > 0
    assert result.validation_report.status == "fail"
    mps = result.physics_analysis.by_id("calc_mean_piston_speed")
    assert mps is not None and mps.passes is False
    assert any(
        e.id == "eval_calc_mean_piston_speed" and not e.passes
        for e in result.validation_report.constraint_evaluations
    )


def test_synthetic_constraint_evaluation_needs_no_special_case():
    """Fix 1 architecture: inject any hard_limit/fails evaluation → hard_violations increases."""
    report = ValidationReport()
    ConstraintEvaluator().apply_to_report(
        report,
        [
            ConstraintEvaluation(
                id="eval_synthetic_regression",
                severity=ConstraintSeverity.HARD_LIMIT,
                value=1,
                limit=0,
                passes=False,
                source="synthetic_test",
                description="Synthetic regression hard-limit failure",
            )
        ],
    )
    assert report.hard_violations == 1
    assert report.status == "fail"


def test_requirements_and_constraint_graph_stay_synchronized():
    """Original sync defect: graph assemblies must carry compiled requirements."""
    result = _run()
    root = result.graph.assemblies[result.graph.root_id]
    assert root.requirements != []
    rpm_req = next(r for r in root.requirements if r.metric == "max_rpm")
    assert rpm_req.target_value == 9000.0
    # Constraint graph mirrors the requirement.
    assert any(
        node.data.get("type") == "max_rpm" and node.data.get("value") == 9000.0
        for node in result.constraint_graph.nodes.values()
        if node.node_type.value == "constraint"
    )


def test_camshaft_thermal_edge_is_mechanical_not_combustion():
    """Fix 2a: camshaft thermal causality is friction/mechanical-load."""
    result = _run()
    thermal_ids = [
        e.source_id
        for e in result.constraint_graph.edges
        if e.edge_type.value == "constraint_applies_to"
        and e.target_id == "camshaft"
        and e.source_id.startswith("constraint_thermal_")
    ]
    assert thermal_ids
    trace = next(
        e
        for e in result.constraint_graph.edges
        if e.edge_type.value == "traces_to" and e.target_id == thermal_ids[0]
    )
    assert "friction/mechanical-load" in trace.description
    assert "combustion/exhaust gas exposure" not in trace.description


def test_lubrication_thermal_edges_not_generic_placeholder():
    """Fix 2b: lubrication components must not use generic thermal placeholder."""
    result = _run()
    for component_id in ("oil_pan", "oil_pickup_tube", "main_oil_gallery"):
        thermal_ids = [
            e.source_id
            for e in result.constraint_graph.edges
            if e.edge_type.value == "constraint_applies_to"
            and e.target_id == component_id
            and e.source_id.startswith("constraint_thermal_")
        ]
        assert thermal_ids, f"missing thermal constraint for {component_id}"
        trace = next(
            e
            for e in result.constraint_graph.edges
            if e.edge_type.value == "traces_to" and e.target_id == thermal_ids[0]
        )
        assert "local operating thermal environment" not in trace.description
        assert "traces to" in trace.description


def test_derived_values_referenced_by_calculation_id():
    """Fix 7/8b: operating conditions are derived from calculation IDs, not independent copies."""
    result = _run()
    refs = result.physics_analysis.operating_condition_refs
    assert refs["mean_piston_speed_m_s"] == "calc_mean_piston_speed"
    assert refs["rod_stress_requirement_mpa"] == "calc_rod_stress_requirement"
    mps = result.physics_analysis.by_id("calc_mean_piston_speed")
    assert mps is not None
    assert result.physics_analysis.resolve_operating("mean_piston_speed_m_s") == mps.result
    # Derived view must equal resolve_operating for every bound key.
    for key in refs:
        assert result.physics_analysis.operating_conditions[key] == result.physics_analysis.resolve_operating(key)
    dumped = result.physics_analysis.model_dump()
    assert dumped["operating_conditions"]["mean_piston_speed_m_s"] == mps.result
    rods = result.graph.components["connecting_rods"]
    assert rods.material_spec.selection_metrics["source"] == "calc_rod_stress_requirement"


def test_physics_constraints_trace_to_specific_calculations():
    """Fix 8a: physics-derived constraints trace to their source calc, not generically to req_1."""
    result = _run()
    expected = {
        "constraint_physics_rod_stress": "constraint_calc_rod_stress_requirement",
        "constraint_physics_temperature_pistons": "constraint_calc_combustion_side_temperature",
        "constraint_physics_temperature_cylinder_head": "constraint_calc_combustion_side_temperature",
    }
    for constraint_id, calc_node in expected.items():
        traces = [
            e
            for e in result.constraint_graph.edges
            if e.edge_type.value == "traces_to" and e.target_id == constraint_id
        ]
        assert traces, f"no traces_to edge for {constraint_id}"
        assert any(e.source_id == calc_node for e in traces), (
            f"{constraint_id} should trace from {calc_node}, got {[e.source_id for e in traces]}"
        )
        assert all("derived downstream of req_" not in e.description or calc_node.split("constraint_")[-1] in e.description for e in traces)

    # Combustion-exposed thermal edges use combustion_side_temperature, not heat_rejection.
    piston_thermal = [
        e.source_id
        for e in result.constraint_graph.edges
        if e.edge_type.value == "constraint_applies_to"
        and e.target_id == "pistons"
        and e.source_id.startswith("constraint_thermal_")
    ]
    assert piston_thermal
    piston_traces = [
        e
        for e in result.constraint_graph.edges
        if e.edge_type.value == "traces_to" and e.target_id == piston_thermal[0]
    ]
    assert any(e.source_id == "constraint_calc_combustion_side_temperature" for e in piston_traces)
    assert all("calc_combustion_side_temperature" in e.description or "combustion" in e.description for e in piston_traces)


def test_unrecognized_terms_and_conflicts_surface_explicitly():
    """Fix 4: Category A/C premises are not silently resolved."""
    pipeline = SemanticKernelPipeline(provider=DeterministicProvider())

    a = pipeline.run(
        "Design a naturally aspirated 9000 RPM 800 horsepower V12 using unobtainium "
        "connecting rods running on lava-cooled cylinders."
    )
    terms = {t["term"] for t in a.requirement_spec.unrecognized_terms}
    assert "unobtainium" in terms
    assert "lava-cooled" in terms
    rods = a.graph.components["connecting_rods"]
    assert rods.material is None
    assert rods.material_spec is None

    b = pipeline.run("Design a naturally aspirated V12 producing 800 horsepower at 500000 RPM.")
    assert b.requirement_spec.implausible_parameters == []
    assert b.physics_analysis.by_id("calc_mean_piston_speed") is not None
    assert b.physics_analysis.by_id("calc_mean_piston_speed").result is not None
    assert b.physics_analysis.by_id("calc_rod_stress_requirement").result is not None
    # Extreme RPM must fail from derived thresholds / materials, not an RPM ceiling.
    assert b.validation_report.status == "fail"
    assert b.validation_report.hard_violations > 0
    assert not any(
        e.id.startswith("eval_implausible_max_rpm")
        for e in b.validation_report.constraint_evaluations
    )

    c1 = pipeline.run("Design a naturally aspirated turbocharged V12 producing 800 horsepower.")
    assert any("Naturally aspirated" in c["inputs"] and "Turbocharged" in c["inputs"] for c in c1.requirement_spec.conflicts)
    assert "aspiration" not in c1.requirement_spec.resolved_parameters

    c2 = pipeline.run("Design a diesel-fueled engine with spark ignition producing 800 horsepower.")
    assert any("Diesel" in c["inputs"] and "spark" in c["inputs"] for c in c2.requirement_spec.conflicts)
