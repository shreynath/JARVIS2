"""Phase 10.0 — campaign integrity / anti-cheating tests."""

from __future__ import annotations

import ast
import copy
import json
from pathlib import Path

import pytest

from core.verification.campaign_executor import CampaignExecutor, reject_synthetic_evidence
from core.verification.campaigns.rod_campaign import run_rod_stress_campaign
from core.verification.maturity_registry import check_m4_requirements
from core.verification.model_maturity import ModelMaturity
from core.verification.model_registry import MODEL_REGISTRY
from core.verification.raw_evidence import RawEvidenceRecord
from core.verification.evidence_source import SourceType

FORBIDDEN = {"PhysicsEngine", "MaterialAssigner", "ConstraintEvaluator", "EngineeringEvaluator"}
INDEPENDENT = (
    Path(__file__).resolve().parents[1]
    / "core"
    / "verification"
    / "independent_campaign_validator.py"
)
EXPECTED = {"M0": 3, "M1": 1, "M2": 9, "M3": 10, "M4": 0, "M5": 0}


def _histogram() -> dict[str, int]:
    return {m.name: sum(1 for d in MODEL_REGISTRY.values() if d.maturity is m) for m in ModelMaturity}


def _forbidden_imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text())
    hits: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for bad in (
                "physics_engine",
                "material_assigner",
                "constraint_evaluator",
                "engineering_evaluator",
            ):
                if bad in mod:
                    hits.append(mod)
            for a in node.names:
                if a.name in FORBIDDEN:
                    hits.append(a.name)
        if isinstance(node, ast.Import):
            for a in node.names:
                if any(x in a.name for x in ("physics_engine", "material_assigner")):
                    hits.append(a.name)
    return hits


@pytest.fixture(autouse=True)
def _isolate_store(tmp_path, monkeypatch):
    for name in ("pending", "approved", "rejected"):
        (tmp_path / name).mkdir()
    monkeypatch.setattr("core.verification.evidence_store.PENDING_DIR", tmp_path / "pending")
    monkeypatch.setattr("core.verification.evidence_store.APPROVED_DIR", tmp_path / "approved")
    monkeypatch.setattr("core.verification.evidence_store.REJECTED_DIR", tmp_path / "rejected")
    monkeypatch.setattr("core.verification.evidence_store.STORE_ROOT", tmp_path)
    yield


def test_synthetic_evidence_rejected(tmp_path):
    """Test 1 — synthetic evidence yields zero accepted cases."""
    synth = RawEvidenceRecord(
        id="syn_1",
        component="connecting_rod",
        field="piston_mass_g",
        value=450.0,
        unit="g",
        source_id="fake",
        source_title="synthetic",
        measurement_type="synthetic",
        quality="low",
        provenance={"source_type": SourceType.SECONDARY_ESTIMATE.value},
        uncertainty={"relative": 0.5},
    )
    accepted, rejected = reject_synthetic_evidence([synth])
    assert len(accepted) == 0
    assert "syn_1" in rejected

    cases = {
        "engine_name": "Fake",
        "engine_id": "fake",
        "rpm": 9000,
        "stroke_mm": 80,
        "bore_mm": 90,
        "rod_length_mm": 140,
        "piston_mass_g": 400,
        "rod_mass_g": 500,
        "reported_component_data": {},
        "source": "synthetic generated dataset",
        "confidence": "synthetic",
    }
    (tmp_path / "fake.json").write_text(json.dumps(cases))
    result = run_rod_stress_campaign(dataset_path=tmp_path)
    assert result.accepted_cases == 0


def test_evidence_does_not_change_physics(tmp_path):
    """Test 2 — evidence campaigns must not alter physics outputs."""
    from core.verification.independent_campaign_validator import IndependentCampaignValidator

    v = IndependentCampaignValidator()
    before = {
        "torque": v.torque_nm(800, 9000),
        "mps": v.mean_piston_speed_m_s(0.08, 9000),
        "bmep": v.bmep_bar(633.0, 6.0),
    }
    CampaignExecutor().run_all(tmp_path)
    after = {
        "torque": v.torque_nm(800, 9000),
        "mps": v.mean_piston_speed_m_s(0.08, 9000),
        "bmep": v.bmep_bar(633.0, 6.0),
    }
    assert before == after


def test_campaign_failure_does_not_reduce_maturity():
    """Test 3 — failed campaign leaves maturity histogram unchanged."""
    before = _histogram()
    result = CampaignExecutor().run_campaign("rod_stress")
    assert result.eligible_for_m4 is False
    after = _histogram()
    assert before == after == EXPECTED


def test_passing_campaign_does_not_automatically_promote():
    """Test 4 — even an eligible-looking result must not mutate registry."""
    before = copy.deepcopy({k: d.maturity for k, d in MODEL_REGISTRY.items()})
    # Fabricate a would-be-passing check payload — still no auto promote
    fake = {
        "accepted_cases": 12,
        "mean_error": 0.05,
        "max_error": 0.1,
        "uncertainty": "low",
        "independent_verifier": True,
        "failure_modes": [],
        "eligible_for_m4": True,
        "eligible_for_upgrade": True,
    }
    check = check_m4_requirements("calc_rod_stress_requirement", fake)
    # Eligibility may be true for the check, but registry must be untouched
    after = {k: d.maturity for k, d in MODEL_REGISTRY.items()}
    assert before == after
    assert _histogram()["M4"] == 0
    # Promote script is the only writer — we do not call it here
    assert check["policy"].startswith("Eligibility only")


def test_independent_validator_cannot_import_production_models():
    """Test 5 — AST gate on independent_campaign_validator.py."""
    hits = _forbidden_imports(INDEPENDENT)
    assert hits == [], f"Forbidden imports: {hits}"

    # Also gate campaign executor + phase10 campaign modules
    root = Path(__file__).resolve().parents[1] / "core" / "verification"
    for rel in (
        "campaign_executor.py",
        "campaigns/rod_campaign.py",
        "campaigns/bmep_campaign.py",
        "campaigns/material_campaign.py",
    ):
        hits = _forbidden_imports(root / rel)
        assert hits == [], f"{rel}: {hits}"


def test_m4_histogram_locked_after_phase10(tmp_path):
    CampaignExecutor().run_all(tmp_path)
    assert _histogram() == EXPECTED


def test_check_m4_requirements_rejects_insufficient():
    check = check_m4_requirements(
        "rod_stress",
        {
            "accepted_cases": 2,
            "mean_error": None,
            "max_error": None,
            "uncertainty": "unknown",
            "independent_verifier": False,
            "failure_modes": ["missing_masses"],
            "eligible_for_m4": False,
        },
    )
    assert check["eligible"] is False
    assert "missing" in check["reason"] or check["missing"]


def test_campaign_executor_writes_results(tmp_path):
    results = CampaignExecutor().run_all(tmp_path)
    assert (tmp_path / "rod_campaign_result.json").exists()
    assert (tmp_path / "bmep_campaign_result.json").exists()
    assert (tmp_path / "material_campaign_result.json").exists()
    assert results["rod_stress"].eligible_for_m4 is False
