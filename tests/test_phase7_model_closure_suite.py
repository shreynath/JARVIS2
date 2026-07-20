"""Phase 7 expanded suite — provenance, isolation, families, closure DoD."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from core.engineering.engine_cycle_model import (
    BOOSTED_BMEP_BAR,
    NA_BMEP_BAR,
    EngineCycleEstimate,
    EngineCycleModel,
    ProvenancedValue,
)
from core.engineering.thermal_model import ThermalModel
from core.materials.requirements import MaterialRequirement, from_stress
from core.reasoning.pipeline import SemanticKernelPipeline
from core.verification.bmep_validation import (
    _classify_family,
    bmep_bar_from_torque_displacement,
    build_bmep_validation,
    write_bmep_validation,
)
from core.verification.model_closure import build_model_closure_report
from core.verification.model_maturity import ModelMaturity
from core.verification.model_registry import MODEL_REGISTRY
from core.verification.uncertainty import propagate_bmep_uncertainty, run_uncertainty_analysis
from llm.ollama_client import DeterministicProvider
from verification.impact_analysis import analyze_model_impact


BASELINE = "Design a 9000 RPM naturally aspirated V12 producing 800 horsepower."
VALID_SOURCES = {"known", "assumed", "empirical", "derived"}


# ---------------------------------------------------------------------------
# Provenance: no naked engineering outputs
# ---------------------------------------------------------------------------


def test_provenanced_value_requires_source_field():
    pv = ProvenancedValue(value=14.0, unit="bar", source="empirical", reference="test")
    d = pv.to_dict()
    assert set(d) >= {"value", "unit", "source"}
    assert d["source"] in VALID_SOURCES


def test_engine_cycle_all_fields_have_source_when_present():
    est = EngineCycleModel().estimate(
        aspiration="Naturally aspirated", horsepower=800, rpm=9000
    )
    for field in (
        "displacement_l",
        "bmep",
        "volumetric_efficiency",
        "thermal_efficiency",
        "mechanical_efficiency",
    ):
        node = getattr(est, field)
        assert node is not None, field
        assert node.source in VALID_SOURCES, field


def test_naked_bmep_constant_alone_is_insufficient_contract():
    """Contract: consumers must read ProvenancedValue, not a bare float."""
    est = EngineCycleModel().estimate(aspiration="Naturally aspirated")
    assert not isinstance(est.bmep, (int, float))
    assert isinstance(est.bmep, ProvenancedValue)


def test_derived_displacement_provenance():
    est = EngineCycleModel().estimate(
        aspiration="Naturally aspirated", horsepower=800, rpm=9000
    )
    assert est.displacement_l is not None
    assert est.displacement_l.source == "derived"
    assert isinstance(est.displacement_l.value, tuple)


def test_known_displacement_provenance():
    est = EngineCycleModel().estimate(
        aspiration="Naturally aspirated", displacement_l=4.0
    )
    assert est.displacement_l is not None
    assert est.displacement_l.source == "known"
    assert est.displacement_l.value == 4.0


def test_unknown_aspiration_does_not_emit_fake_bmep():
    est = EngineCycleModel().estimate(aspiration=None)
    assert est.bmep is None
    assert est.provenance.get("category") == "unknown"


def test_cycle_estimate_to_dict_serializable():
    est = EngineCycleModel().estimate(
        aspiration="turbocharged", horsepower=600, rpm=7000
    )
    raw = json.dumps(est.to_dict())
    loaded = json.loads(raw)
    assert loaded["bmep"]["source"] == "empirical"
    assert loaded["maturity"] == "M2"


# ---------------------------------------------------------------------------
# Material requirements
# ---------------------------------------------------------------------------


def test_material_requirement_empty_load_source_fails():
    req = MaterialRequirement(
        component="pistons",
        required_properties={"yield_strength": 200.0},
        load_source="",
        calculation_dependencies=["calc_heat_rejection"],
        status="computed",
    )
    with pytest.raises(ValueError, match="load_source"):
        req.assert_has_source()


def test_material_requirement_missing_yield_fails():
    req = MaterialRequirement(
        component="block",
        required_properties={"temperature_limit": 150.0},
        load_source="calc_x",
        calculation_dependencies=["calc_x"],
        status="computed",
    )
    with pytest.raises(ValueError, match="yield"):
        req.assert_has_source()


def test_unknown_status_skips_assert():
    req = MaterialRequirement(
        component="x",
        required_properties={},
        load_source="",
        calculation_dependencies=[],
        status="UNKNOWN",
    )
    req.assert_has_source()  # must not raise


def test_from_stress_embeds_dependencies_in_dict():
    req = from_stress(
        component="connecting_rods",
        stress_mpa=400.0,
        temperature_c=120.0,
        yield_factor=1.25,
        fatigue_factor=0.65,
        dependencies=["calc_rod_loading", "calc_rod_stress_requirement"],
        load_source="calc_rod_stress_requirement",
    )
    d = req.to_dict()
    assert d["calculation_dependencies"] == [
        "calc_rod_loading",
        "calc_rod_stress_requirement",
    ]
    assert d["load_source"] == "calc_rod_stress_requirement"


def test_pipeline_titanium_or_steel_has_why_not_catalog_habit():
    result = SemanticKernelPipeline(provider=DeterministicProvider()).run(BASELINE)
    rods = result.graph.components["connecting_rods"]
    packet = rods.material_spec.selection_metrics["requirement_evidence"]
    reason = packet["reason_for_selection"].lower()
    assert "because" in reason or "requires" in reason
    assert "catalog habit" not in reason
    assert packet["computed_from"]


# ---------------------------------------------------------------------------
# BMEP validation isolation + family separation
# ---------------------------------------------------------------------------


def test_bmep_validation_report_policy_no_autotune():
    report = build_bmep_validation()
    assert "never" in report["policy"].lower() or "only" in report["policy"].lower()
    assert "auto" in report["policy"].lower() or "tune" in report["policy"].lower()


def test_bmep_bands_unchanged_after_validation_deepcopy():
    model = EngineCycleModel()
    snap = copy.deepcopy(model.bmep_range_pa("Naturally aspirated"))
    _ = build_bmep_validation()
    assert model.bmep_range_pa("Naturally aspirated") == snap
    assert snap == (1.2e6, 1.6e6)


def test_family_classifier_na_turbo_diesel_aircraft():
    assert _classify_family({"aspiration": "Naturally aspirated", "name": "x"}) == "na"
    assert _classify_family({"aspiration": "turbocharged", "name": "x"}) == "turbo"
    assert _classify_family({"aspiration": "diesel", "name": "x"}) == "diesel"
    assert _classify_family({"aspiration": "na", "name": "Lycoming IO-360"}) == "aircraft"


def test_families_never_pooled_in_report():
    report = build_bmep_validation()
    # Each family has its own mean_error key; no top-level combined mean across families.
    assert "mean_error" not in report or report.get("mean_error") is None
    for fam in ("na", "turbo", "diesel", "aircraft"):
        assert "mean_error" in report["families"][fam]


def test_write_bmep_validation_json_schema(tmp_path: Path):
    path = write_bmep_validation(tmp_path)
    data = json.loads(path.read_text())
    assert data["phase"] == "7.0"
    assert data["na_band_bar"] == list(NA_BMEP_BAR) or data["na_band_bar"] == NA_BMEP_BAR
    assert set(data["families"]) == {"na", "turbo", "diesel", "aircraft"}


def test_bmep_formula_monotonic_in_torque():
    a = bmep_bar_from_torque_displacement(400.0, 4.0)
    b = bmep_bar_from_torque_displacement(500.0, 4.0)
    assert b > a


def test_bmep_formula_inverse_in_displacement():
    a = bmep_bar_from_torque_displacement(400.0, 3.0)
    b = bmep_bar_from_torque_displacement(400.0, 4.0)
    assert a > b


# ---------------------------------------------------------------------------
# Thermal separation
# ---------------------------------------------------------------------------


def test_thermal_heat_is_calculated_temp_is_empirical():
    r = ThermalModel().analyze(horsepower=800.0)
    assert r.heat_rejection_kw.kind == "calculated"
    assert r.combustion_side_temperature_c.kind == "empirical"


def test_thermal_outputs_carry_maturity_and_validation_status():
    r = ThermalModel().analyze(horsepower=500.0)
    for q in (r.heat_rejection_kw, r.combustion_side_temperature_c):
        assert q.maturity in {"M0", "M1", "M2", "M3", "M4", "M5"}
        assert q.validation_status
        assert q.confidence


def test_thermal_temp_respects_upper_heat_binding():
    r = ThermalModel().analyze(horsepower=800.0, cooling_heat_kw_for_temp=800.0)
    # Historical map: 180 + min(120, Q/8) → 180 + 100 = 280
    assert r.combustion_side_temperature_c.value == 280.0


def test_thermal_does_not_claim_production_validated():
    r = ThermalModel().analyze(horsepower=800.0)
    assert r.combustion_side_temperature_c.validation_status != "PRODUCTION_VALIDATED"
    assert r.combustion_side_temperature_c.maturity != "M5"


# ---------------------------------------------------------------------------
# Uncertainty propagation
# ---------------------------------------------------------------------------


def test_uncertainty_distributions_have_stats():
    report = propagate_bmep_uncertainty(n_samples=300, seed=11)
    for key in ("stroke_mm", "mean_piston_speed_m_s", "rod_stress_proxy_mpa"):
        dist = report["distributions"][key]
        assert dist["n"] == 300
        assert dist["p95"] >= dist["p05"]
        assert dist["max"] >= dist["min"]


def test_uncertainty_no_candidate_selection_keys():
    report = propagate_bmep_uncertainty(n_samples=50, seed=4)
    blob = json.dumps(report)
    assert "best_candidate" not in blob
    assert "optimize" not in blob.lower() or "no optimization" in report["policy"].lower()


def test_higher_bmep_band_shifts_displacement_lower():
    # Sample midpoints: higher BMEP → smaller displacement for fixed power/RPM.
    na = EngineCycleModel().estimate(
        aspiration="Naturally aspirated", horsepower=800, rpm=9000
    )
    turbo = EngineCycleModel().estimate(
        aspiration="turbocharged", horsepower=800, rpm=9000
    )
    assert na.displacement_l is not None and turbo.displacement_l is not None
    na_mid = sum(na.displacement_l.value) / 2  # type: ignore[arg-type]
    turbo_mid = sum(turbo.displacement_l.value) / 2  # type: ignore[arg-type]
    assert turbo_mid < na_mid


def test_run_uncertainty_analysis_facade_keys():
    out = run_uncertainty_analysis(n_samples=100, seed=5)
    assert "bmep_propagation" in out
    assert "legacy_monte_carlo" in out


# ---------------------------------------------------------------------------
# Impact + closure
# ---------------------------------------------------------------------------


def test_impact_formula_documented():
    report = analyze_model_impact({})
    assert "sensitivity" in report["scoring"]
    assert "uncertainty" in report["scoring"]
    assert "dependency_count" in report["scoring"]


def test_engine_cycle_high_impact_priority():
    report = analyze_model_impact({})
    cycle = report["models"]["engine_cycle_model"]
    assert cycle["priority"] in {"high", "very_high", "medium"}
    assert cycle["closure_impact_score"] > report["models"]["eq_oil_flow"]["closure_impact_score"]


def test_closure_answers_why_displacement_and_material():
    report = build_model_closure_report()
    assert "why_this_displacement" in report["answers"]
    assert "why_this_material" in report["answers"]
    assert report["dominant_uncertainties"]


def test_closure_lists_bmep_as_dominant():
    report = build_model_closure_report()
    ids = {d["model"] for d in report["dominant_uncertainties"]}
    assert "engine_cycle_model" in ids or "bmep_assumption_bands" in ids


def test_thermal_registry_m3_not_inflated():
    assert MODEL_REGISTRY["thermal_model"].maturity is ModelMaturity.M3
    assert MODEL_REGISTRY["thermal_model"].benchmarked is False


def test_engine_cycle_registry_not_m4():
    assert MODEL_REGISTRY["engine_cycle_model"].maturity is ModelMaturity.M2
    assert MODEL_REGISTRY["engine_cycle_model"].benchmarked is False


# ---------------------------------------------------------------------------
# Baseline regressions + attachments
# ---------------------------------------------------------------------------


def test_baseline_attachments_include_mass_rod_geometry_cycle_thermal():
    result = SemanticKernelPipeline(provider=DeterministicProvider()).run(BASELINE)
    keys = set(result.physics_analysis.engineering_attachments)
    assert {"engine_cycle", "thermal"} <= keys


def test_baseline_torque_unchanged_phase7():
    result = SemanticKernelPipeline(provider=DeterministicProvider()).run(BASELINE)
    assert abs(result.physics_analysis.by_id("calc_torque").result - 633.0) < 0.5


def test_baseline_mps_hard_fail_unchanged():
    result = SemanticKernelPipeline(provider=DeterministicProvider()).run(BASELINE)
    mps = result.physics_analysis.by_id("calc_mean_piston_speed")
    assert mps.passes is False
    assert abs(max(mps.value_range) - 26.68) < 0.05


def test_na_bmep_band_matches_legacy_pa():
    assert EngineCycleModel().bmep_range_pa("Naturally aspirated") == (1.2e6, 1.6e6)
    assert NA_BMEP_BAR == (12.0, 16.0)
    assert BOOSTED_BMEP_BAR == (16.0, 25.0)


def test_engine_cycle_estimate_dataclass_contract():
    est = EngineCycleEstimate(confidence="low", maturity="M2")
    assert est.bmep is None
    assert isinstance(est.to_dict()["assumptions"], list)
