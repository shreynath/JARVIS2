#!/usr/bin/env python3
"""Run Campaign A — high-RPM dynamics evidence (no registry mutation)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.verification.campaign_gate import write_campaign_result
from core.verification.campaigns.high_rpm_dynamics import (
    build_failure_packet,
    build_validation_report,
    write_high_rpm_reports,
)
from core.reasoning.pipeline import SemanticKernelPipeline
from llm.ollama_client import DeterministicProvider

BASELINE = "Design a 9000 RPM naturally aspirated V12 producing 800 horsepower."


def main() -> None:
    out = ROOT / "output"
    out.mkdir(parents=True, exist_ok=True)

    paths = write_high_rpm_reports(out)
    validation = build_validation_report()
    failures = build_failure_packet(validation)
    result_path = write_campaign_result(out, validation=validation, failure_packet=failures)

    # Baseline regression (campaign must not disturb physics).
    result = SemanticKernelPipeline(provider=DeterministicProvider()).run(BASELINE)
    torque = result.physics_analysis.by_id("calc_torque")
    mps = result.physics_analysis.by_id("calc_mean_piston_speed")
    assert abs(torque.result - 633.0) < 0.5
    assert mps.passes is False
    assert abs(max(mps.value_range) - 26.68) < 0.05
    assert result.validation_report.hard_violations == 1

    campaign = json.loads(result_path.read_text())
    summary = {
        "phase": "8.5",
        "campaign": "high_rpm_dynamics",
        "eligible_for_upgrade": campaign["eligible_for_upgrade"],
        "eligible_models": campaign["eligible_models"],
        "blocked_models": campaign["blocked_models"],
        "artifacts": {k: str(v) for k, v in paths.items()}
        | {"campaign_result": str(result_path)},
        "baseline_ok": True,
        "policy": "No automatic promotions. Use scripts/promote_model_maturity.py.",
    }
    (out / "phase85_campaign_a_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    print("Campaign A evidence complete")


if __name__ == "__main__":
    main()
