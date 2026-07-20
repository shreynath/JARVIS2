"""Phase 9.5 — campaign readiness, evidence review, and template validation tests."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from core.verification.campaign_readiness import (
    CampaignNotReadyError,
    assert_campaign_ready,
    campaign_not_ready,
    check_campaign_ready,
    generated_dataset_invalid,
    m4_histogram_locked,
    validate_csv_submission,
)
from core.verification.dataset_templates import (
    BMEP_REQUIRED_COLUMNS,
    BMEP_TEMPLATE,
    MATERIAL_TEMPLATE,
    ROD_REQUIRED_COLUMNS,
    ROD_TEMPLATE,
    template_headers,
)
from core.verification.evidence_completeness import (
    score_bmep_case,
    score_material_case,
    score_rod_case,
)
from core.verification.evidence_review import (
    ReviewState,
    approve_record,
    reject_record,
    review_record,
)
from core.verification.evidence_source import SourceType
from core.verification.evidence_store import (
    APPROVED_DIR,
    PENDING_DIR,
    REJECTED_DIR,
    load_approved,
    load_pending,
    load_rejected,
    save_pending,
)
from core.verification.m4_candidate import evaluate_m4_candidate
from core.verification.model_maturity import ModelMaturity
from core.verification.raw_evidence import RawEvidenceRecord
from core.verification.data_acquisition_priority import compute_acquisition_priorities

EXPECTED_HISTOGRAM = {"M0": 3, "M1": 1, "M2": 9, "M3": 10, "M4": 0, "M5": 0}


def _valid_record(**overrides) -> RawEvidenceRecord:
    base = dict(
        id="test_rec_001",
        component="connecting_rod",
        field="piston_mass_g",
        value=450.0,
        unit="g",
        source_id="src_honda_f20c",
        source_title="Honda OEM documentation",
        measurement_type="direct",
        quality="high",
        provenance={
            "source_type": SourceType.OEM_DOCUMENTATION.value,
            "measurement_method": "teardown_scale",
        },
        uncertainty={"relative": 0.02},
        engine="Honda F20C",
        engine_id="honda_f20c",
    )
    base.update(overrides)
    return RawEvidenceRecord(**base)


@pytest.fixture(autouse=True)
def _isolate_evidence_store(tmp_path, monkeypatch):
    pending = tmp_path / "pending"
    approved = tmp_path / "approved"
    rejected = tmp_path / "rejected"
    for d in (pending, approved, rejected):
        d.mkdir()
    monkeypatch.setattr("core.verification.evidence_store.PENDING_DIR", pending)
    monkeypatch.setattr("core.verification.evidence_store.APPROVED_DIR", approved)
    monkeypatch.setattr("core.verification.evidence_store.REJECTED_DIR", rejected)
    monkeypatch.setattr("core.verification.evidence_store.STORE_ROOT", tmp_path)
    yield


# --- Templates --------------------------------------------------------------


def test_official_templates_exist():
    assert ROD_TEMPLATE.exists()
    assert BMEP_TEMPLATE.exists()
    assert MATERIAL_TEMPLATE.exists()


def test_rod_template_headers():
    headers = template_headers(ROD_TEMPLATE)
    for col in ROD_REQUIRED_COLUMNS:
        assert col in headers


def test_bmep_template_headers():
    headers = template_headers(BMEP_TEMPLATE)
    for col in BMEP_REQUIRED_COLUMNS:
        assert col in headers


def test_material_template_headers():
    headers = template_headers(MATERIAL_TEMPLATE)
    assert "component" in headers
    assert "source_id" in headers


# --- Completeness -----------------------------------------------------------


def test_rod_completeness_partial():
    row = {
        "engine_name": "Honda F20C",
        "rpm": 8600,
        "stroke_mm": 84,
        "bore_mm": 86,
        "rod_length_mm": 142,
        "piston_mass_g": 450,
        "rod_mass_g": None,
        "rod_material": "4340",
        "source_id": "oem_f20c",
        "measurement_method": "teardown",
        "uncertainty": "±2%",
    }
    score = score_rod_case(row, case_id="F20C_rod_001")
    assert score["completeness"] < 1.0
    assert "rod_mass_g" in score["missing"]
    assert score["eligible_for_campaign"] is False


def test_rod_completeness_complete():
    row = {
        "engine_name": "Honda F20C",
        "rpm": 8600,
        "stroke_mm": 84,
        "bore_mm": 86,
        "rod_length_mm": 142,
        "piston_mass_g": 450,
        "rod_mass_g": 580,
        "rod_material": "4340",
        "source_id": "oem_f20c",
        "measurement_method": "teardown",
        "uncertainty": "±2%",
    }
    score = score_rod_case(row, case_id="F20C_rod_001")
    assert score["eligible_for_campaign"] is True
    assert score["completeness"] >= 0.99


def test_bmep_hp_without_rpm_incomplete():
    row = {
        "engine_name": "Test",
        "family": "naturally_aspirated",
        "rpm": None,
        "horsepower": 500,
        "torque_nm": 400,
        "displacement_l": 4.0,
        "source_id": "dyno_1",
        "measurement_method": "dyno",
        "uncertainty": "±3%",
    }
    score = score_bmep_case(row, case_id="test_1")
    assert score["eligible_for_campaign"] is False
    assert any("horsepower_requires_rpm" in m for m in score["missing"])


def test_bmep_torque_without_displacement_incomplete():
    row = {
        "engine_name": "Test",
        "family": "turbocharged",
        "rpm": 6000,
        "horsepower": 500,
        "torque_nm": 400,
        "displacement_l": None,
        "source_id": "dyno_1",
        "measurement_method": "dyno",
        "uncertainty": "±3%",
    }
    score = score_bmep_case(row, case_id="test_2")
    assert score["eligible_for_campaign"] is False


def test_material_completeness():
    row = {
        "component": "connecting_rod",
        "engine_name": "BMW S65",
        "material": "4340",
        "yield_strength_mpa": 930,
        "fatigue_strength_mpa": 620,
        "temperature_limit_c": 200,
        "source_id": "oem_bmw",
        "measurement_method": "datasheet",
        "uncertainty": "±5%",
    }
    score = score_material_case(row, case_id="bmw_rod_1")
    assert score["eligible_for_campaign"] is True


# --- Evidence review --------------------------------------------------------


def test_review_pending_missing_checklist():
    rec = _valid_record(uncertainty={})
    review = review_record(rec)
    assert review.state is ReviewState.PENDING
    assert "uncertainty_recorded" in review.missing
    assert review.can_enter_validation is False


def test_review_approved_requires_full_checklist():
    rec = _valid_record()
    save_pending(rec)
    review = approve_record(rec.id)
    assert review.state is ReviewState.APPROVED
    assert review.can_enter_validation is True
    assert len(load_approved()) == 1
    assert len(load_pending()) == 0


def test_review_reject_moves_to_rejected_store():
    rec = _valid_record()
    save_pending(rec)
    review = reject_record(rec.id, reason="duplicate source")
    assert review.state is ReviewState.REJECTED
    assert len(load_rejected()) == 1
    assert len(load_pending()) == 0


def test_approve_fails_without_source():
    rec = _valid_record(source_id="", source_title="")
    save_pending(rec)
    with pytest.raises(ValueError, match="Cannot approve"):
        approve_record(rec.id)


# --- Campaign readiness -----------------------------------------------------


def test_missing_rod_mass_campaign_not_ready():
    assert campaign_not_ready()


def test_rod_stress_readiness_reports_missing_mass():
    report = check_campaign_ready("rod_stress")
    assert report["ready"] is False
    assert report["completion"] < 1.0
    assert "rod_mass" in report["reason"].lower() or report["complete_cases"] < 10


def test_assert_campaign_ready_raises():
    with pytest.raises(CampaignNotReadyError):
        assert_campaign_ready("rod_stress")


def test_synthetic_dataset_invalid():
    synth = _valid_record(id="syn_1", measurement_type="synthetic")
    assert generated_dataset_invalid([synth]) is True


def test_direct_measurement_not_synthetic_invalid():
    direct = _valid_record(measurement_type="direct")
    assert generated_dataset_invalid([direct]) is False


def test_approved_evidence_campaign_ready_with_complete_cases(monkeypatch):
    from core.verification.datasets.rod_validation.case import RodValidationCase

    def _fake_cases():
        cases = []
        for i in range(10):
            cases.append(
                RodValidationCase(
                    engine_name=f"Engine {i}",
                    engine_id=f"eng_{i}",
                    rpm=8000.0,
                    stroke_mm=84.0,
                    bore_mm=86.0,
                    rod_length_mm=142.0,
                    piston_mass_g=450.0,
                    rod_mass_g=580.0,
                    reported_component_data={
                        "connecting_rods_material": "4340",
                        "measurement_method": "teardown",
                        "uncertainty": "±2%",
                    },
                    source="oem",
                    confidence="high",
                )
            )
        return cases

    monkeypatch.setattr(
        "core.verification.campaign_readiness.load_rod_cases",
        _fake_cases,
    )
    report = check_campaign_ready("rod_stress")
    assert report["ready"] is True
    assert report["complete_cases"] >= 10


def test_bmep_campaign_not_ready():
    report = check_campaign_ready("bmep")
    assert report["ready"] is False


def test_material_campaign_not_ready():
    report = check_campaign_ready("material")
    assert report["ready"] is False


def test_m4_histogram_locked():
    assert m4_histogram_locked() == EXPECTED_HISTOGRAM


def test_maturity_isolation_m4_zero():
    hist = m4_histogram_locked()
    assert hist["M4"] == 0
    assert hist["M5"] == 0


# --- CSV validation ---------------------------------------------------------


def test_csv_validation_rejects_hp_without_rpm(tmp_path):
    path = tmp_path / "bad_bmep.csv"
    path.write_text(
        "engine_name,family,manufacturer,rpm,horsepower,torque_nm,displacement_l,"
        "aspiration,fuel_type,peak_or_continuous,source_id,measurement_method,uncertainty,notes\n"
        "Test,na,Honda,,500,400,4.0,NA,gas,peak,dyno1,dyno,±3%,\n"
    )
    result = validate_csv_submission(path, "bmep")
    assert result["valid"] is False
    assert any("horsepower without rpm" in r["reason"] for r in result["invalid_rows"])


def test_csv_validation_requires_source_id(tmp_path):
    path = tmp_path / "bad_rod.csv"
    headers = ",".join(ROD_REQUIRED_COLUMNS)
    path.write_text(f"{headers}\nHonda,,,,,,,,,,,,,,,,,\n")
    result = validate_csv_submission(path, "rod")
    assert result["valid"] is False


def test_csv_validation_accepts_valid_row(tmp_path):
    path = tmp_path / "ok_bmep.csv"
    path.write_text(
        "engine_name,family,manufacturer,rpm,horsepower,torque_nm,displacement_l,"
        "aspiration,fuel_type,peak_or_continuous,source_id,measurement_method,uncertainty,notes\n"
        "Honda F20C,naturally_aspirated,Honda,8600,240,220,2.0,NA,gas,peak,oem1,dyno,±2%,\n"
    )
    result = validate_csv_submission(path, "bmep")
    assert result["valid"] is True


# --- M4 candidate simulation ------------------------------------------------


def test_m4_candidate_fails_on_blocked_campaign():
    payload = {
        "campaign": "high_rpm_dynamics",
        "eligible_for_upgrade": False,
        "blocked_models": [{"model": "calc_torque", "reason": "gate_incomplete"}],
        "gate": "M2_to_M3",
    }
    result = evaluate_m4_candidate(payload)
    assert result["m4_eligibility"] == "FAIL"
    assert result["histogram"]["M4"] == 0


def test_m4_candidate_reports_histogram():
    payload = {"campaign": "rod_validation", "eligible_for_upgrade": False, "gate": "M3_to_M4"}
    result = evaluate_m4_candidate(payload)
    assert result["histogram"] == EXPECTED_HISTOGRAM


# --- Acquisition priority ---------------------------------------------------


def test_acquisition_priorities_ranked():
    rows = compute_acquisition_priorities(top_n=5)
    assert len(rows) <= 5
    assert rows[0]["priority"] >= rows[-1]["priority"]
    assert "model" in rows[0]
    assert "reason" in rows[0]


def test_acquisition_priority_formula_fields():
    rows = compute_acquisition_priorities(top_n=3)
    for row in rows:
        assert row["impact"] > 0
        assert row["missing_evidence_ratio"] >= 0


# --- Dashboard script -------------------------------------------------------


def test_research_dashboard_renders():
    from scripts.research_dashboard import render_dashboard

    text = render_dashboard()
    assert "JARVIS Validation Research Status" in text
    assert "ROD STRESS" in text
    assert "BMEP" in text
    assert "MATERIALS" in text


# --- Evidence audit state ---------------------------------------------------


def test_evidence_state_in_audit():
    from core.verification.evidence_audit import build_evidence_state

    state = build_evidence_state()
    assert "validated_cases" in state
    assert "pending_cases" in state
    assert "rejected_cases" in state
    assert state["m4_ready_models"] == 0


def test_evidence_audit_phase_95():
    from core.verification.evidence_audit import build_evidence_audit

    audit = build_evidence_audit()
    assert audit["phase"] == "9.5"
    assert "evidence_state" in audit
