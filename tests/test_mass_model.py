"""Phase 5.0 — reciprocating mass model."""

from __future__ import annotations

from core.engineering.reciprocating_mass import ReciprocatingMassModel
from core.epistemology.assumption_registry import AssumptionRegistry
from core.verification.model_registry import MODEL_REGISTRY
from core.verification.model_maturity import ModelMaturity
from verification.formulas import piston_shell_mass_kg


def test_mass_model_exposes_assumptions():
    reg = AssumptionRegistry()
    result = ReciprocatingMassModel().estimate(bore_mm=87.0, stroke_mm=84.0, registry=reg)
    assert result.reciprocating_mass_kg > result.piston_mass_kg > 0
    assert result.pin_mass_kg > 0
    assert result.ring_mass_kg > 0
    assert result.assumption_records
    assert len(reg) >= 5
    assert result.confidence == "medium"
    assert result.maturity == "M2"


def test_piston_mass_matches_independent_shell_formula():
    bore, stroke = 87.0, 84.0
    result = ReciprocatingMassModel().estimate(bore_mm=bore, stroke_mm=stroke)
    independent = piston_shell_mass_kg(bore, stroke)
    assert abs(result.piston_mass_kg - independent) / independent < 0.001


def test_mass_maturity_upgraded_from_m1():
    assert MODEL_REGISTRY["piston_mass_estimate"].maturity is ModelMaturity.M2
    assert MODEL_REGISTRY["reciprocating_mass_model"].maturity is ModelMaturity.M2
