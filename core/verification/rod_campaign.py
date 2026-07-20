"""Phase 8.6 rod campaign reports + maturity packet (no auto-promotion)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.verification.datasets.rod_validation.loader import load_rod_cases, rod_dataset_inventory
from core.verification.model_maturity import (
    M4_MIN_EXTERNAL_CASES,
    MaturityUpgradeEvidence,
    evaluate_m3_to_m4_upgrade,
)
from core.verification.rod_verifier import run_rod_verification


TARGET_MODELS = (
    "calc_rod_loading",
    "calc_rod_stress_requirement",
    "connecting_rod_model",
    "reciprocating_mass_model",
)


def build_rod_validation_report() -> dict[str, Any]:
    verification = run_rod_verification()
    inventory = rod_dataset_inventory()
    absolute_n = inventory["with_absolute_mass"]
    # Without absolute masses there is no external load error to compute.
    mean_error = None
    worst = None
    error_documented = False
    if absolute_n >= M4_MIN_EXTERNAL_CASES:
        # Placeholder path for future OEM mass benches — not reached with current nulls.
        error_documented = True
        mean_error = 0.0
        worst = 0.0

    models = []
    for mid in TARGET_MODELS:
        models.append(
            {
                "model": mid if mid != "calc_rod_stress_requirement" else "rod_stress",
                "model_id": mid,
                "current": "M3" if mid != "reciprocating_mass_model" else "M2",
                "evidence_cases": inventory["total_cases"],
                "absolute_mass_cases": absolute_n,
                "mean_error_percent": None if mean_error is None else mean_error * 100.0,
                "worst_case_error": None if worst is None else worst * 100.0,
                "failure_modes_found": (
                    []
                    if absolute_n >= M4_MIN_EXTERNAL_CASES
                    else ["missing_published_piston_and_rod_mass"]
                ),
                "independent_verifier": True,
                "uncertainty_quantified": False,
                "upgrade_recommendation": (
                    "M4 eligible"
                    if absolute_n >= M4_MIN_EXTERNAL_CASES and error_documented
                    else "NOT M4 eligible — absolute load benchmarks unavailable"
                ),
            }
        )

    return {
        "phase": "8.6",
        "campaign": "rod_validation",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "inventory": inventory,
        "verification": verification,
        "models": models,
        "policy": "Reports evidence readiness. Does not mutate MODEL_REGISTRY.",
    }


def build_rod_failure_analysis(report: dict[str, Any] | None = None) -> dict[str, Any]:
    report = report or build_rod_validation_report()
    return {
        "phase": "8.6",
        "campaign": "rod_validation",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "failures": [
            {
                "model": "rod_stress",
                "status": "blocked",
                "error": None,
                "cause": "Published piston_mass_g / rod_mass_g / rod_length_mm are null",
                "action": "Acquire OEM or teardown mass/length benches (≥10 engines)",
                "model_change_justified": False,
                "magnitude": "complete lack of absolute external load references",
            },
            {
                "model": "reciprocating_mass_model",
                "status": "blocked",
                "cause": "No published piston mass dataset for external comparison",
                "action": "Campaign B mass acquisition before M2→M3 absolute validation",
                "model_change_justified": False,
            },
        ],
        "geometry_only_cases": report["inventory"]["with_geometry"],
        "policy": "Failure is evidence. Do not invent masses to pass M4 gates.",
    }


def build_rod_maturity_packet(
    report: dict[str, Any] | None = None,
    failures: dict[str, Any] | None = None,
) -> dict[str, Any]:
    report = report or build_rod_validation_report()
    failures = failures or build_rod_failure_analysis(report)
    absolute_n = report["inventory"]["with_absolute_mass"]
    evidence = MaturityUpgradeEvidence(
        external_validation_cases=absolute_n,
        mean_error_documented=False,
        uncertainty_documented=False,
        independent_verifier_exists=True,
        unresolved_major_failure_modes=tuple(
            f["cause"] for f in failures.get("failures") or []
        ),
    )
    gate = evaluate_m3_to_m4_upgrade(evidence)
    packets = []
    for row in report["models"]:
        packets.append(
            {
                "model": row["model"],
                "model_id": row["model_id"],
                "current": row["current"],
                "evidence_cases": absolute_n,
                "geometry_cases": report["inventory"]["total_cases"],
                "mean_error_percent": row["mean_error_percent"],
                "worst_case_error": row["worst_case_error"],
                "failure_modes_found": row["failure_modes_found"],
                "independent_verifier": True,
                "m3_to_m4_gate": gate,
                "upgrade_recommendation": row["upgrade_recommendation"],
                "eligible_for_m4": gate["allowed"],
            }
        )
    return {
        "phase": "8.6",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "packets": packets,
        "eligible_for_upgrade": False,
        "eligible_models": [],
        "policy": "No automatic promotion. M4 requires ≥10 absolute mass/load benches.",
    }


def write_rod_campaign_reports(output_dir: Path | str) -> dict[str, Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    report = build_rod_validation_report()
    failures = build_rod_failure_analysis(report)
    packet = build_rod_maturity_packet(report, failures)
    paths = {
        "validation": out / "rod_validation_report.json",
        "failures": out / "rod_failure_analysis.json",
        "maturity": out / "rod_maturity_packet.json",
    }
    paths["validation"].write_text(json.dumps(report, indent=2, default=str))
    paths["failures"].write_text(json.dumps(failures, indent=2, default=str))
    paths["maturity"].write_text(json.dumps(packet, indent=2, default=str))
    return paths
