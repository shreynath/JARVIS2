#!/usr/bin/env python3
"""Run Phases 8.6–8.8 evidence campaigns (rod, BMEP, material). No auto M4."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.verification.bmep_campaign import write_bmep_campaign_reports
from core.verification.campaign_gate import CampaignResult, write_generic_campaign_result
from core.verification.material_validation import write_material_campaign_reports
from core.verification.rod_campaign import (
    build_rod_maturity_packet,
    write_rod_campaign_reports,
)
from core.verification.prediction_confidence import write_design_prediction_confidence
from core.reasoning.pipeline import SemanticKernelPipeline
from llm.ollama_client import DeterministicProvider

BASELINE = "Design a 9000 RPM naturally aspirated V12 producing 800 horsepower."


def main() -> None:
    out = ROOT / "output"
    out.mkdir(parents=True, exist_ok=True)

    rod_paths = write_rod_campaign_reports(out)
    rod_packet = build_rod_maturity_packet()
    write_generic_campaign_result(
        out,
        filename="rod_campaign_result.json",
        result=CampaignResult(
            campaign="rod_validation",
            eligible_for_upgrade=bool(rod_packet.get("eligible_for_upgrade")),
            eligible_models=list(rod_packet.get("eligible_models") or []),
            blocked_models=[
                {"model": p["model_id"], "reason": p["upgrade_recommendation"]}
                for p in rod_packet.get("packets") or []
                if not p.get("eligible_for_m4")
            ],
            gate="M3_to_M4",
            evidence_summary={"packet": "rod_maturity_packet.json"},
        ),
    )

    bmep_paths = write_bmep_campaign_reports(out)
    bmep_mat = json.loads((out / "bmep_maturity_packet.json").read_text())
    write_generic_campaign_result(
        out,
        filename="bmep_campaign_result.json",
        result=CampaignResult(
            campaign="bmep_displacement",
            eligible_for_upgrade=bool(bmep_mat.get("eligible_for_upgrade")),
            eligible_models=list(bmep_mat.get("eligible_models") or []),
            blocked_models=[
                {"reason": bmep_mat.get("blocked_reason"), "models": bmep_mat.get("models")}
            ],
            gate="M3_to_M4",
            evidence_summary={"packet": "bmep_maturity_packet.json"},
        ),
    )

    mat_paths = write_material_campaign_reports(out)
    mat_packet = json.loads((out / "material_maturity_packet.json").read_text())
    write_generic_campaign_result(
        out,
        filename="material_campaign_result.json",
        result=CampaignResult(
            campaign="material_validation",
            eligible_for_upgrade=bool(mat_packet.get("eligible_for_upgrade")),
            eligible_models=list(mat_packet.get("eligible_models") or []),
            blocked_models=[{"reason": mat_packet.get("blocked_reason")}],
            gate="M3_to_M4",
            evidence_summary={"packet": "material_maturity_packet.json"},
        ),
    )

    result = SemanticKernelPipeline(provider=DeterministicProvider()).run(BASELINE)
    torque = result.physics_analysis.by_id("calc_torque")
    mps = result.physics_analysis.by_id("calc_mean_piston_speed")
    assert abs(torque.result - 633.0) < 0.5
    assert mps.passes is False
    assert abs(max(mps.value_range) - 26.68) < 0.05
    assert result.validation_report.hard_violations == 1

    summary = {
        "phase": "8.6-8.9",
        "rod_m4_eligible": rod_packet.get("eligible_for_upgrade"),
        "bmep_m4_eligible": bmep_mat.get("eligible_for_upgrade"),
        "material_m4_eligible": mat_packet.get("eligible_for_upgrade"),
        "m4_promotions_applied": 0,
        "artifacts": {
            **{f"rod_{k}": str(v) for k, v in rod_paths.items()},
            **{f"bmep_{k}": str(v) for k, v in bmep_paths.items()},
            **{f"material_{k}": str(v) for k, v in mat_paths.items()},
        },
        "baseline_ok": True,
        "policy": "Evidence campaigns complete. No automatic M4 promotions.",
        "next": "Acquire absolute rod masses / mapped BMEP distributions before promote M3→M4.",
    }
    conf_path = write_design_prediction_confidence(
        out, physics=result.physics_analysis.model_dump()
    )
    summary["design_prediction_confidence"] = str(conf_path)
    (out / "phase86_88_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print(json.dumps(summary, indent=2))
    print("Phases 8.6–8.9 campaign sweep complete")


if __name__ == "__main__":
    main()
