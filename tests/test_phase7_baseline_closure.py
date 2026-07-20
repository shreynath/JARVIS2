"""Phase 7 — baseline regression + closure report + impact scoring."""

from __future__ import annotations

import json
from pathlib import Path

from core.verification.bmep_validation import write_bmep_validation
from core.verification.model_closure import build_model_closure_report, write_model_closure_report
from core.verification.uncertainty import run_uncertainty_analysis
from core.reasoning.pipeline import SemanticKernelPipeline
from llm.ollama_client import DeterministicProvider
from verification.impact_analysis import analyze_model_impact


BASELINE = "Design a 9000 RPM naturally aspirated V12 producing 800 horsepower."


def test_baseline_torque_mps_hard_violation():
    result = SemanticKernelPipeline(provider=DeterministicProvider()).run(BASELINE)
    torque = result.physics_analysis.by_id("calc_torque")
    mps = result.physics_analysis.by_id("calc_mean_piston_speed")
    assert torque is not None and abs(torque.result - 633.0) < 0.5
    assert mps is not None and mps.passes is False
    assert mps.value_range is not None
    assert abs(max(mps.value_range) - 26.68) < 0.05
    assert result.validation_report is not None
    assert result.validation_report.hard_violations == 1


def test_physics_emits_cycle_and_thermal_provenance():
    result = SemanticKernelPipeline(provider=DeterministicProvider()).run(BASELINE)
    att = result.physics_analysis.engineering_attachments
    assert "engine_cycle" in att
    assert att["engine_cycle"]["bmep"]["source"] == "empirical"
    assert "thermal" in att
    disp = result.physics_analysis.by_id("calc_displacement")
    assert disp.inputs.get("bmep_source") == "empirical"


def test_impact_score_includes_uncertainty_and_dependencies():
    report = analyze_model_impact({"calculations": []})
    assert report["phase"] == "7.0"
    assert "uncertainty" in report["scoring"]
    bmep = report["models"]["engine_cycle_model"]
    assert bmep["closure_impact_score"] > 0
    assert bmep["uncertainty"] > 0
    assert bmep["dependency_count"] >= 1


def test_model_closure_report_lists_dominant_uncertainties(tmp_path: Path):
    result = SemanticKernelPipeline(provider=DeterministicProvider()).run(BASELINE)
    physics = result.physics_analysis.model_dump()
    impact = analyze_model_impact(physics)
    report = build_model_closure_report(physics=physics, impact_report=impact)
    assert report["dominant_uncertainties"]
    assert report["engine_cycle_present"] is True
    assert report["thermal_separated"] is True
    assert "why_this_displacement" in report["answers"]
    path = write_model_closure_report(tmp_path, physics=physics, impact_report=impact)
    assert path.exists()


def test_write_bmep_and_uncertainty_artifacts(tmp_path: Path):
    write_bmep_validation(tmp_path)
    unc = run_uncertainty_analysis(n_samples=200, seed=3)
    (tmp_path / "uncertainty_propagation.json").write_text(
        json.dumps(unc, indent=2, default=str)
    )
    bmep = json.loads((tmp_path / "bmep_validation.json").read_text())
    assert "families" in bmep
    assert bmep["policy"]


def test_displacement_answer_chain_exists():
    """Auditable chain: power/RPM → cycle assumptions → displacement."""
    result = SemanticKernelPipeline(provider=DeterministicProvider()).run(BASELINE)
    cycle = result.physics_analysis.engineering_attachments["engine_cycle"]
    disp = result.physics_analysis.by_id("calc_displacement")
    assert cycle["provenance"]["category"] == "na"
    assert disp.assumptions  # explicit assumptions recorded
    assert disp.result is not None
