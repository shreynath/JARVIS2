"""Phase 6 — reality audit embeds calibration status without PhysicsEngine import."""

from __future__ import annotations

import ast
import json
from pathlib import Path

from core.verification.phase6_reports import write_phase6_reports
from core.reasoning.pipeline import SemanticKernelPipeline
from llm.ollama_client import DeterministicProvider
from verification.reality_auditor import run_reality_audit


def test_auditor_still_isolated():
    path = Path(__file__).resolve().parents[1] / "verification" / "reality_auditor.py"
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            assert "physics_engine" not in mod
            assert all(a.name != "PhysicsEngine" for a in node.names)
        if isinstance(node, ast.Import):
            assert all("physics_engine" not in a.name for a in node.names)


def test_reality_audit_includes_phase6_fields(tmp_path: Path):
    result = SemanticKernelPipeline(provider=DeterministicProvider()).run(
        "Design a 9000 RPM naturally aspirated V12 producing 800 horsepower."
    )
    assert result.physics_analysis is not None
    (tmp_path / "physics_analysis.json").write_text(
        json.dumps(result.physics_analysis.model_dump(), indent=2, default=str)
    )
    (tmp_path / "requirement_specification.json").write_text(
        json.dumps(result.requirement_spec.model_dump(), indent=2, default=str)
    )
    (tmp_path / "engine_design_graph.json").write_text(
        json.dumps(
            result.graph.to_spec_dict(
                requirement_spec=result.requirement_spec,
                physics_analysis=result.physics_analysis,
                constraint_graph=result.constraint_graph,
            ),
            indent=2,
            default=str,
        )
    )
    write_phase6_reports(tmp_path, include_jarvis=False)
    report = run_reality_audit(tmp_path)

    for key in (
        "scientific_confidence",
        "validated_models",
        "unvalidated_high_impact_models",
        "known_biases",
        "recommended_research",
        "external_calibration_status",
        "validation_coverage",
        "weakest_models",
        "strongest_models",
    ):
        assert key in report, key
    assert report["external_calibration_status"] == "present"
    assert isinstance(report["scientific_confidence"], (int, float))
    assert report["validated_models"]  # at least torque / MPS
    final = tmp_path / "final_reality_audit.json"
    final.write_text(json.dumps(report, indent=2, default=str))
    assert json.loads(final.read_text())["scientific_confidence"] == report["scientific_confidence"]


def test_baseline_mps_and_torque_unchanged():
    result = SemanticKernelPipeline(provider=DeterministicProvider()).run(
        "Design a 9000 RPM naturally aspirated V12 producing 800 horsepower."
    )
    mps = result.physics_analysis.by_id("calc_mean_piston_speed")
    torque = result.physics_analysis.by_id("calc_torque")
    assert mps is not None and mps.passes is False
    assert torque is not None and torque.result is not None
    assert abs(torque.result - 633.0) / 633.0 < 0.02
