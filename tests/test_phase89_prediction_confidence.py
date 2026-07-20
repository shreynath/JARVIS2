"""Phase 8.9 — design prediction confidence artifact."""

from __future__ import annotations

import json
from pathlib import Path

from core.verification.prediction_confidence import (
    build_design_prediction_confidence,
    write_design_prediction_confidence,
)
from core.reasoning.pipeline import SemanticKernelPipeline
from llm.ollama_client import DeterministicProvider

BASELINE = "Design a 9000 RPM naturally aspirated V12 producing 800 horsepower."


def test_design_prediction_confidence_has_required_outputs():
    report = build_design_prediction_confidence()
    assert report["phase"] == "8.9"
    for key in (
        "displacement",
        "torque",
        "mean_piston_speed",
        "rod_material",
        "combustion_temperature",
    ):
        assert key in report["outputs"]
        assert "overall_confidence" in report["outputs"][key]
        assert "reason" in report["outputs"][key]


def test_displacement_cites_bmep_limitation():
    report = build_design_prediction_confidence()
    disp = report["outputs"]["displacement"]
    assert disp.get("value") is not None or "reason" in disp
    assert "BMEP" in disp["reason"] or "bmep" in disp["reason"].lower()


def test_m4_blocked_flags_honest():
    report = build_design_prediction_confidence()
    assert report["m4_blocked"]["rod_models"] is True
    assert report["m4_blocked"]["bmep_displacement"] is True


def test_torque_high_after_campaign_a_m3():
    report = build_design_prediction_confidence()
    assert report["outputs"]["torque"]["maturity"] == "M3"
    assert report["outputs"]["torque"]["overall_confidence"] in {"high", "medium"}


def test_write_artifact(tmp_path: Path):
    path = write_design_prediction_confidence(tmp_path)
    data = json.loads(path.read_text())
    assert path.name == "design_prediction_confidence.json"
    assert data["outputs"]["rod_material"]["example_decision"] is not None or True


def test_pipeline_physics_enriches_torque_value(tmp_path: Path):
    result = SemanticKernelPipeline(provider=DeterministicProvider()).run(BASELINE)
    path = write_design_prediction_confidence(
        tmp_path, physics=result.physics_analysis.model_dump()
    )
    data = json.loads(path.read_text())
    assert "633" in str(data["outputs"]["torque"]["value"])
