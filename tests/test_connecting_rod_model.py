"""Phase 5.0 — connecting rod geometry-aware model."""

from __future__ import annotations

from core.engineering.connecting_rod_model import ConnectingRodModel, RodSectionType
from core.reasoning.pipeline import SemanticKernelPipeline
from core.verification.model_registry import MODEL_REGISTRY
from core.verification.model_maturity import ModelMaturity
from llm.ollama_client import DeterministicProvider
from verification.formulas import euler_buckling_load_n, i_beam_area_m2


def test_rod_model_outputs_required_fields():
    result = ConnectingRodModel().analyze(
        bore_mm=92.0,
        stroke_mm=75.0,
        tensile_load_n=50_000,
        compressive_load_n=80_000,
        section_type=RodSectionType.I_BEAM,
    )
    assert result.maximum_tensile_stress_mpa > 0
    assert result.compressive_stress_mpa > 0
    assert result.buckling_margin > 0
    assert result.fatigue_margin > 0
    assert result.cross_section_area_m2 > 0
    assert result.section_type == "i_beam"
    assert result.assumption_records


def test_h_beam_differs_from_i_beam():
    kwargs = dict(
        bore_mm=90.0,
        stroke_mm=80.0,
        tensile_load_n=40_000,
        compressive_load_n=60_000,
    )
    i_beam = ConnectingRodModel().analyze(**kwargs, section_type=RodSectionType.I_BEAM)
    h_beam = ConnectingRodModel().analyze(**kwargs, section_type=RodSectionType.H_BEAM)
    assert i_beam.cross_section_area_m2 != h_beam.cross_section_area_m2


def test_rod_area_and_buckling_match_independent_formulas():
    bore_m = 0.09
    tw = 0.08 * bore_m
    bf = 0.35 * bore_m
    tf = 0.10 * bore_m
    d = 0.55 * bore_m
    area = i_beam_area_m2(
        web_thickness=tw, depth=d, flange_width=bf, flange_thickness=tf
    )
    result = ConnectingRodModel().analyze(
        bore_mm=90.0,
        stroke_mm=80.0,
        tensile_load_n=50_000,
        compressive_load_n=70_000,
        rod_length_mm=80.0 * 1.65,
    )
    assert abs(result.cross_section_area_m2 - area) / area < 0.01
    p_cr = euler_buckling_load_n(
        200e9, result.second_moment_m4, result.rod_length_mm / 1000.0
    )
    assert abs(p_cr - result.euler_critical_load_n) / p_cr < 0.01


def test_physics_engine_attaches_rod_model_metadata():
    result = SemanticKernelPipeline(provider=DeterministicProvider()).run(
        "Design a 9000 RPM naturally aspirated V12 producing 800 horsepower."
    )
    stress = result.physics_analysis.by_id("calc_rod_stress_requirement")
    assert stress is not None and stress.status == "computed"
    assert stress.inputs.get("rod_model") == "ConnectingRodModel"
    assert "connecting_rod" in result.physics_analysis.engineering_attachments
    # M4 withheld honestly
    assert MODEL_REGISTRY["connecting_rod_model"].maturity is ModelMaturity.M3
    assert MODEL_REGISTRY["connecting_rod_model"].benchmarked is False
