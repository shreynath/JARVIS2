"""Anti-inflation maturity validation gates."""

from __future__ import annotations

import pytest

from core.verification.maturity_report import (
    model_maturity_summary,
    model_upgrade_priorities,
)
from core.verification.model_maturity import (
    MaturityValidationError,
    ModelDescriptor,
    ModelMaturity,
    validate_descriptor,
)
from core.verification.model_impact import ImpactLevel
from core.verification.model_registry import MODEL_REGISTRY


def test_impossible_maturity_evidence_combinations_fail():
    illegal = [
        ModelDescriptor(
            id="m4_no_iv",
            maturity=ModelMaturity.M4,
            owner="t",
            benchmarked=True,
            independently_verified=False,
            impact="HIGH",
            impact_level=ImpactLevel.HIGH,
            upgrade_priority="HIGH",
        ),
        ModelDescriptor(
            id="m4_no_bench",
            maturity=ModelMaturity.M4,
            owner="t",
            benchmarked=False,
            independently_verified=True,
            impact="HIGH",
            impact_level=ImpactLevel.HIGH,
            upgrade_priority="HIGH",
        ),
        ModelDescriptor(
            id="m5_no_bench",
            maturity=ModelMaturity.M5,
            owner="t",
            benchmarked=False,
            independently_verified=True,
            production_validated=True,
            impact="HIGH",
            impact_level=ImpactLevel.HIGH,
            upgrade_priority="HIGH",
        ),
        ModelDescriptor(
            id="m5_no_prod",
            maturity=ModelMaturity.M5,
            owner="t",
            benchmarked=True,
            independently_verified=True,
            production_validated=False,
            impact="HIGH",
            impact_level=ImpactLevel.HIGH,
            upgrade_priority="HIGH",
        ),
    ]
    for desc in illegal:
        with pytest.raises(MaturityValidationError):
            validate_descriptor(desc)


def test_registry_entries_satisfy_anti_inflation_rules():
    for desc in MODEL_REGISTRY.values():
        validate_descriptor(desc)
        if desc.maturity is ModelMaturity.M4:
            assert desc.benchmarked and desc.independently_verified
        if desc.maturity is ModelMaturity.M5:
            assert desc.production_validated and desc.benchmarked


def test_summary_counts_match_registry():
    summary = model_maturity_summary()
    assert sum(summary["counts"].values()) == len(MODEL_REGISTRY)
    assert summary["counts"]["M5"] == 0
    assert summary["model_count"] == len(MODEL_REGISTRY)


def test_upgrade_priorities_sorted_by_impact_times_deficit():
    report = model_upgrade_priorities()
    priorities = report["priorities"]
    assert priorities
    scores = [p["priority_score"] for p in priorities]
    assert scores == sorted(scores, reverse=True)
    by_id = {p["model"]: p for p in priorities}
    assert "calc_rod_loading" in by_id
    assert by_id["calc_rod_loading"]["priority"] in {"HIGH", "VERY_HIGH"}
    assert "calc_combustion_side_temperature" in by_id
    assert by_id["calc_combustion_side_temperature"]["priority"] == "HIGH"
