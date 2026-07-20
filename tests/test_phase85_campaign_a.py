"""Phase 8.5 — Campaign A high-RPM dynamics evidence + promotion gates."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from core.verification.campaign_gate import (
    CampaignResult,
    assert_not_m4_claim,
    evaluate_high_rpm_campaign_gate,
    evaluate_m2_to_m3_campaign_gate,
    write_campaign_result,
)
from core.verification.campaigns.high_rpm_dynamics.dataset import (
    NULLABLE_PUBLISHED_FIELDS,
    assert_no_invented_values,
    load_high_rpm_dataset,
)
from core.verification.campaigns.high_rpm_dynamics.evaluator import (
    evaluate_dataset,
    mean_piston_speed_m_s,
    peak_piston_acceleration_m_s2,
    torque_nm_from_hp_rpm,
)
from core.verification.campaigns.high_rpm_dynamics.report import (
    build_failure_packet,
    build_validation_report,
    write_high_rpm_reports,
)
from core.verification.model_maturity import ModelMaturity
from core.verification.model_registry import MODEL_REGISTRY
from core.reasoning.pipeline import SemanticKernelPipeline
from llm.ollama_client import DeterministicProvider

CAMPAIGN_PKG = (
    Path(__file__).resolve().parents[1]
    / "core"
    / "verification"
    / "campaigns"
    / "high_rpm_dynamics"
)
FORBIDDEN = {
    "PhysicsEngine",
    "MaterialAssigner",
    "ConstraintEvaluator",
    "EngineeringEvaluator",
}
BASELINE = "Design a 9000 RPM naturally aspirated V12 producing 800 horsepower."


def _forbidden_imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text())
    hits: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if any(
                    x in alias.name
                    for x in (
                        "physics_engine",
                        "material_assigner",
                        "engineering_evaluator",
                        "constraint_evaluator",
                    )
                ):
                    hits.append(alias.name)
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
                    hits.append(f"{mod}.{a.name}")
    return hits


# --- Dataset integrity ------------------------------------------------------


def test_campaign_loads_five_required_engines():
    engines = load_high_rpm_dataset()
    assert len(engines) == 5
    ids = {e["id"] for e in engines}
    assert ids == {
        "honda_f20c",
        "ferrari_f136",
        "ferrari_f140",
        "lexus_lfa_1lr_gue",
        "porsche_991_gt3_ma1",
    }


def test_missing_values_remain_null():
    engines = {e["id"]: e for e in load_high_rpm_dataset()}
    assert engines["honda_f20c"]["published"]["torque_nm"] is None
    assert engines["honda_f20c"]["published"]["mean_piston_speed_m_s"] is None
    assert engines["ferrari_f140"]["published"]["torque_nm"] is None
    assert engines["honda_f20c"]["published"]["peak_piston_acceleration_m_s2"] is None


def test_no_invented_nullable_fields():
    for engine in load_high_rpm_dataset():
        assert_no_invented_values(engine)
        pub = engine["published"]
        for field in NULLABLE_PUBLISHED_FIELDS:
            assert field in pub
            assert pub[field] is None or isinstance(pub[field], (int, float))


def test_references_have_sources():
    for engine in load_high_rpm_dataset():
        assert engine["verified_sources"]
        assert all(isinstance(s, str) and s.strip() for s in engine["verified_sources"])


def test_reference_json_files_exist():
    refs = CAMPAIGN_PKG / "references"
    for eid in (
        "honda_f20c",
        "ferrari_f136",
        "ferrari_f140",
        "lexus_lfa_1lr_gue",
        "porsche_991_gt3_ma1",
    ):
        assert (refs / f"{eid}.json").exists()


# --- Independence -----------------------------------------------------------


def test_campaign_evaluator_has_no_production_imports():
    for path in CAMPAIGN_PKG.rglob("*.py"):
        hits = _forbidden_imports(path)
        assert not hits, f"{path.name}: {hits}"


def test_campaign_gate_module_has_no_physics_engine_import():
    path = (
        Path(__file__).resolve().parents[1]
        / "core"
        / "verification"
        / "campaign_gate.py"
    )
    hits = _forbidden_imports(path)
    assert not hits


# --- Physics relationships --------------------------------------------------


def test_higher_rpm_lowers_torque_at_fixed_hp():
    assert torque_nm_from_hp_rpm(800, 9000) < torque_nm_from_hp_rpm(800, 8000)


def test_higher_rpm_raises_mps():
    assert mean_piston_speed_m_s(0.08, 9000) > mean_piston_speed_m_s(0.08, 8000)


def test_higher_rpm_raises_acceleration():
    assert peak_piston_acceleration_m_s2(0.08, 9000) > peak_piston_acceleration_m_s2(
        0.08, 8000
    )


def test_evaluation_relationship_checks_pass():
    report = evaluate_dataset(load_high_rpm_dataset())
    checks = report["physics_relationship_checks"]
    assert checks["higher_rpm_lowers_torque_at_fixed_hp"] is True
    assert checks["higher_rpm_raises_mps_at_fixed_stroke"] is True
    assert checks["higher_rpm_raises_accel_at_fixed_stroke"] is True


def test_f20c_mps_matches_derived_note():
    engines = {e["id"]: e for e in load_high_rpm_dataset()}
    pub = engines["honda_f20c"]["published"]
    mps = mean_piston_speed_m_s(pub["stroke_mm"] / 1000.0, pub["max_rpm"])
    assert abs(mps - 25.2) < 0.01


# --- Validation / failure reports -------------------------------------------


def test_validation_report_marks_kinematics_pass_displacement_fail():
    report = build_validation_report()
    by_id = {m["model"]: m for m in report["models"]}
    assert by_id["calc_torque"]["passed"] is True
    assert by_id["calc_mean_piston_speed"]["passed"] is True
    assert by_id["calc_piston_acceleration"]["passed"] is True
    assert by_id["displacement_estimation"]["passed"] is False
    assert by_id["calc_mean_piston_speed"]["samples"] == 5
    assert by_id["calc_mean_piston_speed"]["mean_error"] < 0.01


def test_failure_packet_records_bmep_displacement():
    packet = build_failure_packet()
    models = {f["model"] for f in packet["failures"]}
    assert "displacement_estimation" in models
    disp = next(f for f in packet["failures"] if f["model"] == "displacement_estimation")
    assert disp["cause"] == "BMEP assumption uncertainty"
    assert disp["model_change_justified"] is False


def test_write_high_rpm_reports(tmp_path: Path):
    paths = write_high_rpm_reports(tmp_path)
    assert paths["validation"].exists()
    assert paths["failures"].exists()
    data = json.loads(paths["validation"].read_text())
    assert data["phase"] == "8.5"


# --- Gates ------------------------------------------------------------------


def test_m2_to_m3_gate_passes_with_campaign_evidence():
    validation = build_validation_report()
    failures = build_failure_packet(validation)
    result = evaluate_high_rpm_campaign_gate(validation, failures)
    assert isinstance(result, CampaignResult)
    assert result.eligible_for_upgrade is True
    assert "calc_torque" in result.eligible_models
    assert "calc_mean_piston_speed" in result.eligible_models
    assert "calc_piston_acceleration" in result.eligible_models


def test_displacement_blocked_from_upgrade():
    validation = build_validation_report()
    result = evaluate_high_rpm_campaign_gate(validation, build_failure_packet(validation))
    assert "displacement_estimation" not in result.eligible_models
    assert any(b["model"] == "displacement_estimation" for b in result.blocked_models)


def test_m2_to_m4_claim_forbidden():
    with pytest.raises(ValueError, match="forbids"):
        assert_not_m4_claim(ModelMaturity.M2, ModelMaturity.M4)


def test_m3_to_m4_without_predictive_dataset_fails_checklist():
    # Sparse row: no predictive cases → not eligible.
    row = {
        "model": "calc_torque",
        "samples": 2,
        "mean_error": None,
        "uncertainty": "",
        "passed": False,
        "independent_verifier": False,
        "equations_documented": False,
        "known_limitations": [],
    }
    gate = evaluate_m2_to_m3_campaign_gate(model_id="calc_torque", validation_row=row)
    assert gate["eligible_for_upgrade"] is False


def test_write_campaign_result(tmp_path: Path):
    validation = build_validation_report()
    path = write_campaign_result(
        tmp_path, validation=validation, failure_packet=build_failure_packet(validation)
    )
    data = json.loads(path.read_text())
    assert data["eligible_for_upgrade"] is True
    assert set(data["eligible_models"]) >= {
        "calc_torque",
        "calc_mean_piston_speed",
        "calc_piston_acceleration",
    }


def test_campaign_result_does_not_mutate_registry_by_itself():
    # Gate evaluation alone never writes promotions.
    before = {
        mid: MODEL_REGISTRY[mid].maturity
        for mid in (
            "calc_torque",
            "calc_mean_piston_speed",
            "calc_piston_acceleration",
        )
    }
    evaluate_high_rpm_campaign_gate(build_validation_report())
    after = {
        mid: MODEL_REGISTRY[mid].maturity
        for mid in (
            "calc_torque",
            "calc_mean_piston_speed",
            "calc_piston_acceleration",
        )
    }
    assert before == after


# --- Regression -------------------------------------------------------------


def test_baseline_unchanged_phase85():
    result = SemanticKernelPipeline(provider=DeterministicProvider()).run(BASELINE)
    assert abs(result.physics_analysis.by_id("calc_torque").result - 633.0) < 0.5
    mps = result.physics_analysis.by_id("calc_mean_piston_speed")
    assert mps.passes is False
    assert abs(max(mps.value_range) - 26.68) < 0.05
    assert result.validation_report.hard_violations == 1


def test_mps_mean_error_under_one_percent():
    row = next(
        m for m in build_validation_report()["models"] if m["model"] == "calc_mean_piston_speed"
    )
    assert row["passed"] is True
    assert row["mean_error"] < 0.01
    assert row["max_error"] < 0.01


def test_torque_identity_error_tiny():
    row = next(m for m in build_validation_report()["models"] if m["model"] == "calc_torque")
    assert row["mean_error"] < 1e-6 or row["mean_error"] < 0.001


def test_promoted_kinematics_are_m3():
    assert MODEL_REGISTRY["calc_torque"].maturity is ModelMaturity.M3
    assert MODEL_REGISTRY["calc_mean_piston_speed"].maturity is ModelMaturity.M3
    assert MODEL_REGISTRY["calc_piston_acceleration"].maturity is ModelMaturity.M3


def test_histogram_after_campaign_a_promotions():
    counts = {m.name: 0 for m in ModelMaturity}
    for d in MODEL_REGISTRY.values():
        counts[d.maturity.name] += 1
    assert counts == {"M0": 3, "M1": 1, "M2": 9, "M3": 10, "M4": 0, "M5": 0}


def test_no_m4_from_campaign_a():
    assert MODEL_REGISTRY["calc_torque"].maturity is not ModelMaturity.M4
    assert MODEL_REGISTRY["calc_mean_piston_speed"].maturity is not ModelMaturity.M4
