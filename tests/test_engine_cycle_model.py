"""Phase 7 — engine cycle / BMEP provenance and validation."""

from __future__ import annotations

from core.engineering.engine_cycle_model import EngineCycleModel, NA_BMEP_BAR, BOOSTED_BMEP_BAR
from core.verification.bmep_validation import (
    bmep_bar_from_torque_displacement,
    build_bmep_validation,
)
from core.verification.model_registry import MODEL_REGISTRY
from core.verification.model_maturity import ModelMaturity


def test_bmep_values_have_provenance_source():
    est = EngineCycleModel().estimate(
        aspiration="Naturally aspirated", horsepower=800, rpm=9000
    )
    assert est.bmep is not None
    assert est.bmep.source == "empirical"
    assert est.bmep.reference
    assert est.thermal_efficiency is not None
    assert est.thermal_efficiency.source == "empirical"
    assert est.mechanical_efficiency is not None
    assert est.mechanical_efficiency.source == "assumed"
    assert "bmep" in est.to_dict()
    payload = est.bmep.to_dict()
    assert "source" in payload and payload["value"] == NA_BMEP_BAR


def test_no_naked_bmep_without_source_in_payload():
    est = EngineCycleModel().estimate(aspiration="turbocharged")
    d = est.to_dict()
    assert d["bmep"]["source"] in {"known", "assumed", "empirical", "derived"}
    assert d["bmep"]["value"] == BOOSTED_BMEP_BAR


def test_bmep_pa_endpoints_match_legacy_constants():
    # Preserve Phase 1–6 baseline displacement band.
    assert EngineCycleModel().bmep_range_pa("Naturally aspirated") == (1.2e6, 1.6e6)
    assert EngineCycleModel().bmep_range_pa("turbocharged") == (1.6e6, 2.5e6)


def test_bmep_validation_does_not_mutate_model_bands():
    before = EngineCycleModel().bmep_range_pa("Naturally aspirated")
    report = build_bmep_validation()
    after = EngineCycleModel().bmep_range_pa("Naturally aspirated")
    assert before == after
    assert "families" in report
    assert set(report["families"]) >= {"na", "turbo", "diesel", "aircraft"}
    # Families must not be mixed into one pooled error.
    assert report["families"]["na"] is not report["families"]["turbo"]


def test_bmep_families_separated():
    report = build_bmep_validation()
    for family in ("na", "turbo", "diesel", "aircraft"):
        assert "samples" in report["families"][family]
        assert "mean_error" in report["families"][family]


def test_bmep_from_published_torque_identity():
    # Spot-check: τ=480 Nm, V=4.805 L → BMEP ~ 12.55 bar (LFA-ish)
    bar = bmep_bar_from_torque_displacement(480.0, 4.805)
    assert 11.0 < bar < 14.0


def test_engine_cycle_registry_entry():
    assert MODEL_REGISTRY["engine_cycle_model"].maturity is ModelMaturity.M2
    assert MODEL_REGISTRY["bmep_assumption_bands"].maturity is ModelMaturity.M2
