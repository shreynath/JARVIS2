#!/usr/bin/env python3
"""Phase 10.0 — execute evidence campaigns and report M4 eligibility (no auto-promotion)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.verification.campaign_executor import CampaignExecutor
from core.verification.campaigns.bmep_campaign import write_bmep_campaign_result
from core.verification.campaigns.material_campaign import write_material_campaign_result
from core.verification.campaigns.rod_campaign import write_rod_campaign_result
from core.verification.maturity_registry import build_maturity_progress, check_m4_requirements
from core.verification.model_maturity import ModelMaturity
from core.verification.model_registry import MODEL_REGISTRY

EXPECTED = {"M0": 3, "M1": 1, "M2": 9, "M3": 10, "M4": 0, "M5": 0}


def _histogram() -> dict[str, int]:
    return {m.name: sum(1 for d in MODEL_REGISTRY.values() if d.maturity is m) for m in ModelMaturity}


def main() -> None:
    out = ROOT / "output"
    out.mkdir(parents=True, exist_ok=True)
    hist = _histogram()
    assert hist == EXPECTED, f"Maturity inflation detected: {hist}"

    executor = CampaignExecutor()
    results = executor.run_all(out)
    write_rod_campaign_result(out)
    write_bmep_campaign_result(out)
    write_material_campaign_result(out)

    m4_checks = {
        mid: check_m4_requirements(mid, res.to_dict())
        for mid, res in [
            ("rod_stress", results["rod_stress"]),
            ("engine_cycle_model", results["bmep"]),
            ("material_req_structural", results["material"]),
        ]
    }

    progress = build_maturity_progress()
    execution_report = {
        "phase": "10.0",
        "campaigns": {k: v.to_dict() for k, v in results.items()},
        "policy": "Execution only — no automatic promotion.",
    }
    (out / "campaign_execution_report.json").write_text(
        json.dumps(execution_report, indent=2, default=str) + "\n"
    )

    m4_report = {
        "phase": "10.0",
        "checks": m4_checks,
        "maturity_progress": progress,
        "histogram": hist,
        "m4_ready_models": [k for k, v in m4_checks.items() if v.get("eligible")],
    }
    (out / "m4_readiness_report.json").write_text(json.dumps(m4_report, indent=2, default=str) + "\n")

    gaps = {
        "phase": "10.0",
        "gaps": [
            {
                "model": k,
                "missing": v.get("missing"),
                "evidence_cases": v.get("evidence_cases"),
                "required_cases": v.get("required_cases"),
                "reason": v.get("reason"),
            }
            for k, v in m4_checks.items()
            if not v.get("eligible")
        ],
    }
    (out / "evidence_gap_report.json").write_text(json.dumps(gaps, indent=2, default=str) + "\n")

    summary = {
        "phase": "10.0",
        "histogram": hist,
        "m4_ready_models": m4_report["m4_ready_models"],
        "maturity_progress": progress,
        "campaign_files": [
            "rod_campaign_result.json",
            "bmep_campaign_result.json",
            "material_campaign_result.json",
            "campaign_execution_report.json",
            "m4_readiness_report.json",
            "evidence_gap_report.json",
        ],
        "policy": "M4 is a scientific achievement — software only proves whether it happened.",
    }
    (out / "phase10_summary.json").write_text(json.dumps(summary, indent=2, default=str) + "\n")
    print(json.dumps(summary, indent=2))
    print("Phase 10.0 OK — M4 still locked at 0 unless promote_m4_model.py is run after eligibility.")


if __name__ == "__main__":
    main()
