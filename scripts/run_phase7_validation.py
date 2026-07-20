#!/usr/bin/env python3
"""Phase 7.0 validation runner — closure artifacts without model mutation."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.reasoning.pipeline import SemanticKernelPipeline
from core.verification.bmep_validation import write_bmep_validation
from core.verification.model_closure import write_model_closure_report
from core.verification.model_maturity import ModelMaturity
from core.verification.model_registry import MODEL_REGISTRY
from core.verification.uncertainty import run_uncertainty_analysis
from llm.ollama_client import DeterministicProvider
from verification.impact_analysis import write_model_impact_report

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
    assert hist == EXPECTED_MATURITY, f"maturity drift: {hist} != {EXPECTED_MATURITY}"

    result = SemanticKernelPipeline(provider=DeterministicProvider()).run(BASELINE)
    physics = result.physics_analysis.model_dump()
    (out / "physics_analysis.json").write_text(json.dumps(physics, indent=2, default=str))

    torque = result.physics_analysis.by_id("calc_torque")
    mps = result.physics_analysis.by_id("calc_mean_piston_speed")
    assert torque is not None and abs(torque.result - 633.0) < 0.5
    assert mps is not None and mps.passes is False
    assert result.validation_report is not None
    assert result.validation_report.hard_violations == 1

    write_bmep_validation(out)
    unc = run_uncertainty_analysis(horsepower=800, rpm=9000, cylinder_count=12, n_samples=1500)
    (out / "uncertainty_propagation.json").write_text(json.dumps(unc, indent=2, default=str))
    write_model_impact_report(out, physics=physics)
    write_model_closure_report(out, physics=physics)

    summary = {
        "phase": "7.0",
        "maturity_histogram": hist,
        "baseline": {
            "torque_nm": torque.result,
            "mps_high": max(mps.value_range),
            "mps_passes": mps.passes,
            "hard_violations": result.validation_report.hard_violations,
        },
        "attachments": sorted(result.physics_analysis.engineering_attachments.keys()),
        "policy": "No auto-tuning; maturity rises only with evidence.",
    }
    (out / "phase7_closure_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print(json.dumps(summary, indent=2))
    print("Phase 7.0 validation OK")


if __name__ == "__main__":
    main()
