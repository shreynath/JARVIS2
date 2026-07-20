"""Phase 5.0 — model impact framework."""

from __future__ import annotations

from core.verification.model_impact import ImpactLevel, impact_level_from_str
from core.verification.model_registry import MODEL_REGISTRY
from verification.impact_analysis import analyze_model_impact


def test_impact_level_enum():
    assert ImpactLevel.CRITICAL.value == "critical"
    assert impact_level_from_str("HIGH") is ImpactLevel.HIGH
    assert impact_level_from_str("critical") is ImpactLevel.CRITICAL


def test_descriptors_carry_impact_fields():
    for desc in MODEL_REGISTRY.values():
        assert isinstance(desc.impact_level, ImpactLevel)
        assert isinstance(desc.affected_outputs, tuple)
        assert isinstance(desc.sensitivity_rank, int)
        assert desc.upgrade_priority in {"VERY_HIGH", "HIGH", "MEDIUM", "LOW"}


def test_impact_analysis_ranks_rod_loading_high():
    physics = {
        "calculations": [
            {"id": "calc_piston_acceleration", "dependency_ids": ["calc_stroke"]},
            {"id": "calc_rod_loading", "dependency_ids": ["calc_piston_acceleration", "calc_displacement"]},
            {"id": "calc_rod_stress_requirement", "dependency_ids": ["calc_rod_loading"]},
        ]
    }
    report = analyze_model_impact(physics)
    assert "calc_rod_loading" in report["models"]
    rod = report["models"]["calc_rod_loading"]
    assert rod["impact"] in {"high", "critical"}
    assert "rod_stress" in rod["outputs"] or "calc_rod_stress_requirement" in rod["outputs"]
    assert report["impact_ranking"]
    assert report["impact_ranking"][0]["model"]  # ranked list non-empty
