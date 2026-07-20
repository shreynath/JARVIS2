#!/usr/bin/env python3
"""Phase 8.0 — maturity advancement program (evidence only; no registry mutation)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.reasoning.pipeline import SemanticKernelPipeline
from core.verification.evidence_registry import evidence_registry_snapshot
from core.verification.maturity_campaigns import write_campaign_report
from core.verification.maturity_planner import write_maturity_roadmap
from core.verification.maturity_scorecard import write_maturity_scorecard
from core.verification.model_maturity import ModelMaturity
from core.verification.model_registry import MODEL_REGISTRY
from llm.ollama_client import DeterministicProvider
from verification.impact_analysis import analyze_model_impact, write_model_impact_report

EXPECTED_MATURITY = {"M0": 3, "M1": 1, "M2": 9, "M3": 10, "M4": 0, "M5": 0}
BASELINE = "Design a 9000 RPM naturally aspirated V12 producing 800 horsepower."


def _histogram() -> dict[str, int]:
    counts = {m.name: 0 for m in ModelMaturity}
    for d in MODEL_REGISTRY.values():
        counts[d.maturity.name] += 1
    return counts


def main() -> None:
    out = ROOT / "output"
    out.mkdir(parents=True, exist_ok=True)

    hist = _histogram()
    assert hist == EXPECTED_MATURITY, f"maturity inflation detected: {hist}"

    result = SemanticKernelPipeline(provider=DeterministicProvider()).run(BASELINE)
    torque = result.physics_analysis.by_id("calc_torque")
    mps = result.physics_analysis.by_id("calc_mean_piston_speed")
    assert torque is not None and abs(torque.result - 633.0) < 0.5
    assert mps is not None and mps.passes is False
    assert result.validation_report.hard_violations == 1

    impact = analyze_model_impact(result.physics_analysis.model_dump())
    write_model_impact_report(out, physics=result.physics_analysis.model_dump())
    road_path = write_maturity_roadmap(out, impact_report=impact)
    score_path = write_maturity_scorecard(out, impact_report=impact)
    camp_path = write_campaign_report(out)
    (out / "evidence_registry.json").write_text(
        json.dumps(evidence_registry_snapshot(), indent=2, default=str)
    )

    scorecard = json.loads(score_path.read_text())
    summary = {
        "phase": "8.0",
        "maturity_histogram": hist,
        "overall_maturity": scorecard["overall_maturity"],
        "best_upgrade_candidates": scorecard["best_upgrade_candidates"],
        "largest_risk_models": scorecard["largest_risk_models"],
        "m4_count": scorecard["m4_count"],
        "m5_count": scorecard["m5_count"],
        "artifacts": {
            "maturity_roadmap": str(road_path),
            "maturity_scorecard": str(score_path),
            "maturity_campaigns": str(camp_path),
        },
        "policy": "Evidence campaign only — registry maturity unchanged.",
        "baseline_ok": True,
    }
    (out / "phase8_maturity_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    print("Phase 8.0 validation OK")


if __name__ == "__main__":
    main()
