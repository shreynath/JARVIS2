"""Phase 6 — maturity inflation prevention (M3→M4 without evidence fails)."""

from __future__ import annotations

import pytest

from core.verification.model_impact import ImpactLevel
from core.verification.model_maturity import (
    MaturityUpgradeEvidence,
    MaturityValidationError,
    ModelDescriptor,
    ModelMaturity,
    assert_upgrade_allowed,
    evaluate_m3_to_m4_upgrade,
    validate_descriptor,
)
from core.verification.model_registry import MODEL_REGISTRY


def test_rod_stress_remains_m3():
    assert MODEL_REGISTRY["calc_rod_stress_requirement"].maturity is ModelMaturity.M3
    assert MODEL_REGISTRY["calc_rod_stress_requirement"].benchmarked is False


def test_m3_to_m4_without_benchmarks_fails():
    evidence = MaturityUpgradeEvidence(
        external_validation_cases=2,
        mean_error_documented=False,
        uncertainty_documented=False,
        independent_verifier_exists=True,
        unresolved_major_failure_modes=("no absolute rod stress dataset",),
    )
    result = evaluate_m3_to_m4_upgrade(evidence)
    assert result["allowed"] is False
    with pytest.raises(MaturityValidationError, match="M3→M4 blocked"):
        assert_upgrade_allowed(
            from_maturity=ModelMaturity.M3,
            to_maturity=ModelMaturity.M4,
            evidence=evidence,
        )


def test_m4_descriptor_still_requires_benchmark_flags():
    with pytest.raises(MaturityValidationError):
        validate_descriptor(
            ModelDescriptor(
                id="fake_rod_m4",
                maturity=ModelMaturity.M4,
                owner="test",
                independently_verified=True,
                benchmarked=False,
                impact="HIGH",
                impact_level=ImpactLevel.HIGH,
                upgrade_priority="HIGH",
            )
        )


def test_m3_to_m4_with_full_evidence_allowed_but_not_auto_applied():
    evidence = MaturityUpgradeEvidence(
        external_validation_cases=10,
        mean_error_documented=True,
        uncertainty_documented=True,
        independent_verifier_exists=True,
        unresolved_major_failure_modes=(),
    )
    assert evaluate_m3_to_m4_upgrade(evidence)["allowed"] is True
    assert_upgrade_allowed(
        from_maturity=ModelMaturity.M3,
        to_maturity=ModelMaturity.M4,
        evidence=evidence,
    )
    # Registry must still be unchanged — upgrades are explicit, not automatic.
    assert MODEL_REGISTRY["calc_rod_loading"].maturity is ModelMaturity.M3
