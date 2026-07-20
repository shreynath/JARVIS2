"""Phases 8.6–8.8 — rod, BMEP, and material evidence campaigns."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from core.verification.bmep_campaign import (
    build_bmep_campaign_report,
    build_bmep_maturity_packet,
    write_bmep_campaign_reports,
)
from core.verification.campaign_gate import evaluate_m3_to_m4_campaign_gate
from core.verification.datasets.bmep import FAMILIES, load_all_bmep_families
from core.verification.datasets.rod_validation.loader import load_rod_cases, rod_dataset_inventory
from core.verification.material_validation import (
    build_auditable_material_decision,
    build_material_campaign_report,
    load_material_cases,
)
from core.verification.model_maturity import ModelMaturity
from core.verification.model_registry import MODEL_REGISTRY
from core.verification.rod_campaign import (
    build_rod_maturity_packet,
    build_rod_validation_report,
    write_rod_campaign_reports,
)
from core.verification.rod_verifier import (
    fatigue_safety_factor,
    inertia_force_n,
    peak_piston_acceleration_m_s2,
    run_rod_verification,
)
from core.reasoning.pipeline import SemanticKernelPipeline
from llm.ollama_client import DeterministicProvider

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = {
    "PhysicsEngine",
    "MaterialAssigner",
    "ConstraintEvaluator",
    "EngineeringEvaluator",
}
BASELINE = "Design a 9000 RPM naturally aspirated V12 producing 800 horsepower."


def _forbidden(path: Path) -> list[str]:
    tree = ast.parse(path.read_text())
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if any(
                x in mod
                for x in (
                    "physics_engine",
                    "material_assigner",
                    "evaluation.engineering",
                    "constraint_evaluator",
                )
            ):
                hits.append(mod)
            for a in node.names:
                if a.name in FORBIDDEN:
                    hits.append(a.name)
    return hits


# --- 8.6 Rod ----------------------------------------------------------------


def test_rod_dataset_has_at_least_10_cases():
    assert len(load_rod_cases()) >= 10


def test_rod_masses_remain_null():
    for case in load_rod_cases():
        assert case.piston_mass_g is None
        assert case.rod_mass_g is None
        assert case.rod_length_mm is None


def test_rod_inventory_reports_zero_absolute_mass():
    inv = rod_dataset_inventory()
    assert inv["with_absolute_mass"] == 0
    assert inv["with_geometry"] >= 10


def test_rod_verifier_has_no_physics_engine_import():
    path = ROOT / "core" / "verification" / "rod_verifier.py"
    assert not _forbidden(path)


def test_inertia_force_equals_m_times_accel():
    stroke = 0.084
    rpm = 9000.0
    mass = 0.4
    a = peak_piston_acceleration_m_s2(stroke, rpm)
    f = inertia_force_n(mass, stroke, rpm)
    assert abs(f - mass * a) < 1e-6


def test_fatigue_safety_factor_identity():
    assert abs(fatigue_safety_factor(500.0, 250.0) - 2.0) < 1e-9


def test_rod_verification_marks_absolute_mass_unavailable():
    report = run_rod_verification()
    assert report["absolute_mass_cases"] == 0
    assert all(not r["absolute_mass_available"] for r in report["results"])


def test_rod_m4_not_eligible():
    packet = build_rod_maturity_packet()
    assert packet["eligible_for_upgrade"] is False
    assert packet["eligible_models"] == []
    assert all(not p["eligible_for_m4"] for p in packet["packets"])


def test_rod_gate_m3_to_m4_fails_without_masses():
    gate = evaluate_m3_to_m4_campaign_gate(
        model_id="calc_rod_stress_requirement",
        evidence_cases=0,
        mean_error_fraction=None,
        uncertainty_quantified=False,
        failure_modes=["missing_published_piston_and_rod_mass"],
        independent_verifier=True,
    )
    assert gate["eligible_for_upgrade"] is False


def test_write_rod_reports(tmp_path: Path):
    paths = write_rod_campaign_reports(tmp_path)
    assert paths["validation"].exists()
    assert paths["failures"].exists()
    assert paths["maturity"].exists()


def test_rod_models_remain_m3_or_m2_no_silent_m4():
    assert MODEL_REGISTRY["calc_rod_loading"].maturity is ModelMaturity.M3
    assert MODEL_REGISTRY["connecting_rod_model"].maturity is ModelMaturity.M3
    assert MODEL_REGISTRY["reciprocating_mass_model"].maturity is ModelMaturity.M2
    assert MODEL_REGISTRY["calc_rod_loading"].maturity is not ModelMaturity.M4


# --- 8.7 BMEP ---------------------------------------------------------------


def test_bmep_families_never_pooled_keys():
    families = load_all_bmep_families()
    assert set(families) == set(FAMILIES)


def test_bmep_family_minimum_inventory():
    families = load_all_bmep_families()
    assert len(families["naturally_aspirated"]) >= 10
    assert len(families["turbocharged"]) >= 10
    assert len(families["diesel"]) >= 5
    assert len(families["aircraft"]) >= 5
    assert len(families["motorcycle"]) >= 5


def test_bmep_null_torque_stays_incomplete():
    families = load_all_bmep_families()
    aircraft = families["aircraft"]
    assert any(r.torque_nm is None for r in aircraft)


def test_bmep_report_has_baseline_design_answer():
    report = build_bmep_campaign_report()
    ans = report["baseline_design_answer"]
    assert ans["input"]
    assert ans["required_displacement_l"] > 0
    assert "BMEP" in ans["reason"] or "bmep" in ans["reason"].lower()
    assert ans["limitation"]


def test_bmep_families_have_separate_error_blocks():
    report = build_bmep_campaign_report()
    for fam in FAMILIES:
        assert fam in report["families"]
        assert "displacement_error" in report["families"][fam]


def test_bmep_m4_not_eligible():
    packet = build_bmep_maturity_packet()
    assert packet["eligible_for_upgrade"] is False


def test_write_bmep_reports(tmp_path: Path):
    paths = write_bmep_campaign_reports(tmp_path)
    assert paths["validation"].exists()


def test_engine_cycle_still_m2_after_bmep_campaign():
    assert MODEL_REGISTRY["engine_cycle_model"].maturity is ModelMaturity.M2
    assert MODEL_REGISTRY["bmep_assumption_bands"].maturity is ModelMaturity.M2


# --- 8.8 Materials ----------------------------------------------------------


def test_material_cases_loaded():
    assert len(load_material_cases()) >= 10


def test_material_null_strengths_allowed():
    cases = load_material_cases()
    assert any(c.yield_strength_mpa is None for c in cases)


def test_auditable_material_decision_rejects_by_density():
    decision = build_auditable_material_decision(
        component="connecting_rod",
        required_yield_mpa=650.0,
        required_fatigue_mpa=300.0,
        required_temp_c=150.0,
        density_priority=True,
        candidate_keys=["forged_steel_4340", "ti_6al4v"],
        comparable_engines=12,
    )
    assert decision["selected"] == "Titanium 6Al-4V"
    assert any("4340" in r["name"] for r in decision["rejected"])
    assert decision["requirement"]["fatigue_mpa"] == 300.0


def test_material_campaign_not_m4():
    report = build_material_campaign_report()
    assert "NOT M4" in report["models"][0]["upgrade_recommendation"]


def test_material_decision_not_catalog_habit():
    decision = build_auditable_material_decision(
        component="connecting_rod",
        required_yield_mpa=650.0,
        required_fatigue_mpa=300.0,
        required_temp_c=150.0,
        density_priority=True,
        candidate_keys=["forged_steel_4340", "ti_6al4v"],
        comparable_engines=5,
    )
    blob = json.dumps(decision).lower()
    assert "requirement" in blob
    assert "rejected" in blob
    assert "because rods use" not in blob


# --- Shared regression / histogram ----------------------------------------


def test_baseline_unchanged():
    result = SemanticKernelPipeline(provider=DeterministicProvider()).run(BASELINE)
    assert abs(result.physics_analysis.by_id("calc_torque").result - 633.0) < 0.5
    mps = result.physics_analysis.by_id("calc_mean_piston_speed")
    assert mps.passes is False
    assert abs(max(mps.value_range) - 26.68) < 0.05
    assert result.validation_report.hard_violations == 1


def test_histogram_unchanged_no_m4():
    counts = {m.name: 0 for m in ModelMaturity}
    for d in MODEL_REGISTRY.values():
        counts[d.maturity.name] += 1
    assert counts["M4"] == 0
    assert counts["M5"] == 0
    assert counts == {"M0": 3, "M1": 1, "M2": 9, "M3": 10, "M4": 0, "M5": 0}


def test_m3_to_m4_passes_only_with_full_predictive_evidence():
    gate = evaluate_m3_to_m4_campaign_gate(
        model_id="calc_rod_stress_requirement",
        evidence_cases=12,
        mean_error_fraction=0.08,
        uncertainty_quantified=True,
        failure_modes=[],
        independent_verifier=True,
    )
    assert gate["eligible_for_upgrade"] is True


def test_rod_campaign_report_shape():
    report = build_rod_validation_report()
    assert report["phase"] == "8.6"
    assert report["models"]
