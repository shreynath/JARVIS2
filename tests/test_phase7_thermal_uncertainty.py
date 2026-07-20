"""Phase 7 — thermal model separation and uncertainty propagation."""

from __future__ import annotations

from core.engineering.thermal_model import ThermalModel
from core.verification.uncertainty import propagate_bmep_uncertainty
from core.reasoning.pipeline import SemanticKernelPipeline
from llm.ollama_client import DeterministicProvider


def test_thermal_separates_calculated_and_empirical():
    result = ThermalModel().analyze(horsepower=800.0)
    assert result.heat_rejection_kw is not None
    assert result.heat_rejection_kw.kind == "calculated"
    assert result.combustion_side_temperature_c is not None
    assert result.combustion_side_temperature_c.kind == "empirical"
    assert result.heat_rejection_kw.maturity == "M3"
    assert result.combustion_side_temperature_c.validation_status == "UNVALIDATED"


def test_thermal_attachment_on_pipeline():
    result = SemanticKernelPipeline(provider=DeterministicProvider()).run(
        "Design a 9000 RPM naturally aspirated V12 producing 800 horsepower."
    )
    thermal = result.physics_analysis.engineering_attachments["thermal"]
    assert thermal["heat_rejection_kw"]["kind"] == "calculated"
    assert thermal["combustion_side_temperature_c"]["kind"] == "empirical"


def test_uncertainty_preserves_rpm_mps_relationship():
    report = propagate_bmep_uncertainty(
        horsepower=800, rpm=9000, cylinder_count=12, n_samples=500, seed=1
    )
    checks = report["physics_relationship_checks"]
    assert checks["higher_rpm_raises_mps_at_fixed_stroke"] is True
    assert checks["mps_at_1_1x_rpm"] > checks["mps_at_0_9x_rpm"]
    assert "stroke_mm" in report["distributions"]
    assert "mean_piston_speed_m_s" in report["distributions"]
    assert "rod_stress_proxy_mpa" in report["distributions"]
    assert 0.0 <= report["material_survival_probability"] <= 1.0


def test_uncertainty_does_not_optimize():
    report = propagate_bmep_uncertainty(n_samples=100, seed=2)
    assert "policy" in report
    assert "optimization" in report["policy"].lower() or "no optimization" in report["policy"].lower()
