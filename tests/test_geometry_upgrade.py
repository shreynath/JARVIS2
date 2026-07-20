"""Phase 5.0 — geometry model upgrade + independent verification."""

from __future__ import annotations

from core.engineering.geometry_model import GeometryModel
from core.reasoning.pipeline import SemanticKernelPipeline
from llm.ollama_client import DeterministicProvider
from verification.formulas import bore_mm_from_displacement_stroke, crank_radius_mm


def test_geometry_model_provenance_fields():
    result = GeometryModel().resolve(
        displacement_l=2.0,
        cylinder_count=4,
        bore_stroke_ratio=1.1,
    )
    assert result.stroke_mm is not None
    assert result.stroke_mm.maturity == "M2"
    assert result.stroke_mm.source == "derived_from_displacement_and_ratio"
    assert result.crank_radius_mm is not None
    assert result.crank_radius_mm.value == result.stroke_mm.value / 2.0
    assert result.assumptions  # ratio assumption recorded


def test_geometry_matches_independent_formula():
    stroke_mm = 84.0
    bore = bore_mm_from_displacement_stroke(1.997, 4, stroke_mm)
    model = GeometryModel().resolve(
        displacement_l=1.997,
        cylinder_count=4,
        stroke_mm=stroke_mm,
    )
    assert model.bore_mm is not None
    assert abs(model.bore_mm.value - bore) / bore < 0.001
    assert abs(crank_radius_mm(stroke_mm) - model.crank_radius_mm.value) < 1e-9


def test_baseline_mps_still_fails_after_geometry_upgrade():
    result = SemanticKernelPipeline(provider=DeterministicProvider()).run(
        "Design a 9000 RPM naturally aspirated V12 producing 800 horsepower."
    )
    mps = result.physics_analysis.by_id("calc_mean_piston_speed")
    assert mps is not None
    assert mps.passes is False
    torque = result.physics_analysis.by_id("calc_torque")
    assert torque is not None and torque.result is not None
    assert abs(torque.result - 633.0) / 633.0 < 0.02
