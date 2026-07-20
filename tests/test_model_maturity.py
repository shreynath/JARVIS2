"""Model maturity enum and descriptor basics."""

from __future__ import annotations

import pytest

from core.verification.model_maturity import (
    MATURITY_RANK,
    MaturityValidationError,
    ModelDescriptor,
    ModelMaturity,
    parse_maturity,
    validate_descriptor,
)
from core.verification.model_impact import ImpactLevel


def test_maturity_scale_has_expected_members():
    assert [m.name for m in ModelMaturity] == ["M0", "M1", "M2", "M3", "M4", "M5"]
    assert ModelMaturity.M0.value == "placeholder"
    assert ModelMaturity.M2.value == "analytical"
    assert ModelMaturity.M5.value == "industry_grade"


def test_maturity_ranks_are_monotonic():
    ranks = [MATURITY_RANK[m] for m in ModelMaturity]
    assert ranks == list(range(6))


def test_parse_maturity_accepts_name_and_label():
    assert parse_maturity("M2") is ModelMaturity.M2
    assert parse_maturity("analytical") is ModelMaturity.M2
    assert parse_maturity(ModelMaturity.M3) is ModelMaturity.M3


def test_valid_m2_descriptor_passes():
    desc = ModelDescriptor(
        id="mean_piston_speed",
        maturity=ModelMaturity.M2,
        owner="PhysicsEngine",
        equation_id="eq_mean_piston_speed",
        engineering_reference="Heywood",
        benchmarked=True,
        independently_verified=True,
        impact="HIGH",
        impact_level=ImpactLevel.HIGH,
        affected_outputs=("validation",),
        upgrade_priority="HIGH",
    )
    validate_descriptor(desc)  # does not raise
    payload = desc.to_dict()
    assert payload["maturity"] == "M2"
    assert payload["maturity_rank"] == 2
    assert payload["impact_level"] == "HIGH"


def test_m4_without_independent_verification_rejected():
    desc = ModelDescriptor(
        id="fake_m4",
        maturity=ModelMaturity.M4,
        owner="Test",
        benchmarked=True,
        independently_verified=False,
        impact="HIGH",
        impact_level=ImpactLevel.HIGH,
        upgrade_priority="HIGH",
    )
    with pytest.raises(MaturityValidationError, match="independently_verified"):
        validate_descriptor(desc)


def test_m4_without_benchmark_rejected():
    desc = ModelDescriptor(
        id="fake_m4_nb",
        maturity=ModelMaturity.M4,
        owner="Test",
        benchmarked=False,
        independently_verified=True,
        impact="HIGH",
        impact_level=ImpactLevel.HIGH,
        upgrade_priority="HIGH",
    )
    with pytest.raises(MaturityValidationError, match="benchmark"):
        validate_descriptor(desc)


def test_m5_without_production_validation_rejected():
    desc = ModelDescriptor(
        id="fake_m5",
        maturity=ModelMaturity.M5,
        owner="Test",
        benchmarked=True,
        independently_verified=True,
        production_validated=False,
        impact="HIGH",
        impact_level=ImpactLevel.HIGH,
        upgrade_priority="HIGH",
    )
    with pytest.raises(MaturityValidationError, match="production_validated"):
        validate_descriptor(desc)


def test_m5_without_benchmark_rejected():
    desc = ModelDescriptor(
        id="fake_m5_nb",
        maturity=ModelMaturity.M5,
        owner="Test",
        benchmarked=False,
        independently_verified=True,
        production_validated=True,
        impact="HIGH",
        impact_level=ImpactLevel.HIGH,
        upgrade_priority="HIGH",
    )
    with pytest.raises(MaturityValidationError, match="benchmarked"):
        validate_descriptor(desc)
