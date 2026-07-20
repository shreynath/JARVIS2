"""Model registry coverage and integrity."""

from __future__ import annotations

from knowledge.equations.catalog import CALC_TO_EQUATION
from core.verification.model_maturity import ModelMaturity, validate_descriptor
from core.verification.model_registry import (
    ENGINEERING_CALCULATION_IDS,
    MODEL_REGISTRY,
    descriptor_for_calc,
    maturity_for_calc,
    registry_coverage,
)
from core.reasoning.pipeline import SemanticKernelPipeline
from llm.ollama_client import DeterministicProvider


def test_every_registered_model_has_maturity():
    assert MODEL_REGISTRY
    for model_id, desc in MODEL_REGISTRY.items():
        assert desc.id == model_id
        assert isinstance(desc.maturity, ModelMaturity)
        validate_descriptor(desc)


def test_registry_covers_every_engineering_calculation():
    assert ENGINEERING_CALCULATION_IDS == frozenset(CALC_TO_EQUATION.keys())
    for calc_id in CALC_TO_EQUATION:
        desc = descriptor_for_calc(calc_id)
        assert desc is not None, calc_id
        assert desc.maturity is not None
        assert maturity_for_calc(calc_id) is desc.maturity


def test_registry_coverage_equals_engineering_calculations():
    cov = registry_coverage()
    assert cov["coverage_complete"] is True
    assert cov["missing_calculation_ids"] == []
    assert set(cov["registered_calculation_ids"]) == set(CALC_TO_EQUATION)


def test_physics_calculations_carry_model_maturity():
    result = SemanticKernelPipeline(provider=DeterministicProvider()).run(
        "Design a 9000 RPM naturally aspirated V12 producing 800 horsepower."
    )
    assert result.physics_analysis is not None
    for calc in result.physics_analysis.calculations:
        assert calc.model_maturity, calc.id
        assert calc.model_maturity in {m.name for m in ModelMaturity}
        # confidence and validation_status remain independent
        assert calc.confidence in {"high", "medium", "low"}
        assert calc.validation_status


def test_no_model_claims_m5():
    assert all(d.maturity is not ModelMaturity.M5 for d in MODEL_REGISTRY.values())


def test_placeholders_are_m0():
    for model_id in ("packaging", "eq_oil_flow", "manufacturing_cost"):
        assert MODEL_REGISTRY[model_id].maturity is ModelMaturity.M0


def test_representative_maturity_assignments():
    # Phase 8.5 Campaign A: kinematic identities earned M3.
    assert MODEL_REGISTRY["calc_mean_piston_speed"].maturity is ModelMaturity.M3
    assert MODEL_REGISTRY["calc_torque"].maturity is ModelMaturity.M3
    assert MODEL_REGISTRY["calc_piston_acceleration"].maturity is ModelMaturity.M3
    assert MODEL_REGISTRY["calc_combustion_side_temperature"].maturity is ModelMaturity.M3
    assert MODEL_REGISTRY["piston_mass_estimate"].maturity is ModelMaturity.M2
    assert MODEL_REGISTRY["material_req_structural"].maturity is ModelMaturity.M2
    # M4 honestly withheld for rod loading.
    assert MODEL_REGISTRY["calc_rod_loading"].maturity is ModelMaturity.M3
    assert MODEL_REGISTRY["calc_rod_loading"].benchmarked is False
