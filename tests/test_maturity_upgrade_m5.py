"""Phase 6 — M4/M5 upgrade evidence and anti-inflation extras."""

from __future__ import annotations

import pytest

from core.verification.model_maturity import (
    MaturityUpgradeEvidence,
    MaturityValidationError,
    ModelMaturity,
    assert_upgrade_allowed,
    evaluate_m4_to_m5_upgrade,
)


def test_m4_to_m5_blocked_without_production_evidence():
    evidence = MaturityUpgradeEvidence(
        production_validated=False,
        physical_testing=False,
        field_correlation=False,
    )
    result = evaluate_m4_to_m5_upgrade(evidence)
    assert result["allowed"] is False
    with pytest.raises(MaturityValidationError, match="M4→M5 blocked"):
        assert_upgrade_allowed(
            from_maturity=ModelMaturity.M4,
            to_maturity=ModelMaturity.M5,
            evidence=evidence,
        )


def test_m4_to_m5_allowed_with_full_evidence():
    evidence = MaturityUpgradeEvidence(
        production_validated=True,
        physical_testing=True,
        field_correlation=True,
    )
    assert evaluate_m4_to_m5_upgrade(evidence)["allowed"] is True
    assert_upgrade_allowed(
        from_maturity=ModelMaturity.M4,
        to_maturity=ModelMaturity.M5,
        evidence=evidence,
    )


def test_same_or_lower_maturity_upgrade_noop():
    evidence = MaturityUpgradeEvidence()
    assert_upgrade_allowed(
        from_maturity=ModelMaturity.M3,
        to_maturity=ModelMaturity.M3,
        evidence=evidence,
    )
    assert_upgrade_allowed(
        from_maturity=ModelMaturity.M3,
        to_maturity=ModelMaturity.M2,
        evidence=evidence,
    )
