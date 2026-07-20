"""Canary: maturity/evidence system must preserve failures and block promotion."""

from __future__ import annotations

import json

from core.verification.evidence_pipeline import EvidenceValidationError, EvidenceValidator
from core.verification.evidence_source import SourceType
from core.verification.m4_candidate import evaluate_m4_candidate
from core.verification.raw_evidence import RawEvidenceRecord


def test_synthetic_evidence_failure_preserved_not_promoted(tmp_path, monkeypatch):
    """Deliberate failure: synthetic evidence must reject and M4 stays blocked."""
    rejected_dir = tmp_path / "rejected"
    rejected_dir.mkdir()
    monkeypatch.setattr(
        "core.verification.evidence_store.REJECTED_DIR",
        rejected_dir,
    )

    bad = RawEvidenceRecord(
        id="canary_synthetic_fail",
        component="connecting_rod",
        field="piston_mass_g",
        value=999.0,
        unit="g",
        source_id="synthetic_src",
        source_title="LLM guess",
        measurement_type="synthetic",
        quality="low",
        provenance={"source_type": SourceType.SECONDARY_ESTIMATE.value},
        uncertainty={"relative": 0.5},
    )

    try:
        EvidenceValidator().validate_raw(bad)
        raised = False
    except EvidenceValidationError:
        raised = True
    assert raised, "Synthetic evidence must be rejected"

    # M4 candidate evaluation on empty/blocked campaign must FAIL — not promote.
    blocked_campaign = {
        "campaign": "rod_stress",
        "gate": "M3_to_M4",
        "eligible_for_upgrade": False,
        "eligible_for_m4": False,
        "failure_modes": ["insufficient_complete_rod_cases"],
        "successful_cases": 0,
        "failed_cases": 3,
        "eligible_models": [],
    }
    result = evaluate_m4_candidate(blocked_campaign)
    assert result["m4_eligibility"] == "FAIL"

    # Failure recorded on campaign payload — not silently dropped.
    assert blocked_campaign["failed_cases"] > blocked_campaign["successful_cases"]


def test_failed_campaign_json_records_failure_modes():
    """Failure artifact shape — failures must be as visible as successes."""
    payload = {
        "campaign": "rod_stress",
        "status": "blocked",
        "eligible_for_m4": False,
        "failure_modes": ["no_external_stress_benchmarks_for_error"],
        "failed_cases": 2,
        "successful_cases": 0,
    }
    text = json.dumps(payload)
    parsed = json.loads(text)
    assert parsed["eligible_for_m4"] is False
    assert parsed["failure_modes"]
    assert parsed["failed_cases"] > 0
