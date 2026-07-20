"""Reality audit reports model maturity independently of confidence."""

from __future__ import annotations

import json
from pathlib import Path

from core.verification.maturity_report import write_maturity_artifacts
from core.reasoning.pipeline import SemanticKernelPipeline
from llm.ollama_client import DeterministicProvider
from verification.reality_auditor import run_reality_audit


def test_reality_audit_reports_maturity_fields(tmp_path: Path):
    result = SemanticKernelPipeline(provider=DeterministicProvider()).run(
        "Design a 9000 RPM naturally aspirated V12 producing 800 horsepower."
    )
    assert result.physics_analysis is not None
    physics_path = tmp_path / "physics_analysis.json"
    physics_path.write_text(
        result.physics_analysis.model_dump_json(indent=2)
        if hasattr(result.physics_analysis, "model_dump_json")
        else json.dumps(result.physics_analysis.model_dump(), indent=2, default=str)
    )
    (tmp_path / "requirement_specification.json").write_text(
        result.requirement_spec.model_dump_json(indent=2)
        if hasattr(result.requirement_spec, "model_dump_json")
        else json.dumps(result.requirement_spec.model_dump(), indent=2, default=str)
    )
    if result.graph is not None:
        (tmp_path / "engine_design_graph.json").write_text(
            result.graph.model_dump_json(indent=2)
            if hasattr(result.graph, "model_dump_json")
            else json.dumps(result.graph.model_dump(), indent=2, default=str)
        )

    report = run_reality_audit(tmp_path)

    assert "model_maturity" in report
    assert "average_maturity" in report
    assert "maturity_distribution" in report
    assert "subsystem_maturity" in report
    assert "weakest_maturity" in report
    assert "strongest_maturity" in report
    assert "engineering_confidence" in report
    assert "engineering_evidence" in report

    # Confidence and maturity remain distinct keys.
    assert report["overall_confidence"] is not None
    assert report["average_maturity"] in {"M0", "M1", "M2", "M3", "M4", "M5"}
    assert isinstance(report["maturity_distribution"], dict)
    assert sum(report["maturity_distribution"].values()) > 0

    for row in report.get("formula_reference_slice") or []:
        if row.get("calc_id"):
            assert "model_maturity" in row
            assert "confidence" in row or row.get("confidence") is None


def test_write_maturity_artifacts(tmp_path: Path):
    paths = write_maturity_artifacts(tmp_path)
    expected = {
        "model_maturity_report.json",
        "model_maturity_summary.json",
        "model_upgrade_priorities.json",
        "model_progress.json",
    }
    assert set(paths) == expected
    for name in expected:
        payload = json.loads((tmp_path / name).read_text())
        assert payload

    summary = json.loads((tmp_path / "model_maturity_summary.json").read_text())
    assert summary["counts"]["M5"] == 0
    assert "M0" in summary["counts"]

    progress = json.loads((tmp_path / "model_progress.json").read_text())
    assert progress["history"]
    assert progress["current"]["release"] == "phase4.5"

    # Re-run should replace same-release entry, not duplicate forever.
    write_maturity_artifacts(tmp_path)
    progress2 = json.loads((tmp_path / "model_progress.json").read_text())
    releases = [h["release"] for h in progress2["history"]]
    assert releases.count("phase4.5") == 1
