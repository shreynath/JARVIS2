"""Phase 10 BMEP distribution campaign — families never pooled.

Replaces midpoint-only narrative with per-family distribution statistics.
Does not retune BMEP bands. Does not import PhysicsEngine.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from core.verification.bmep_campaign import FAMILY_BMEP_MID_BAR
from core.verification.campaign_executor import CampaignResult, finalize_result, uncertainty_label
from core.verification.datasets.bmep import (
    FAMILIES,
    bmep_bar_from_torque_displacement,
    displacement_l_from_hp_rpm_bmep,
    load_all_bmep_families,
)
from core.verification.independent_campaign_validator import IndependentCampaignValidator

FAMILY_DISPLAY = {
    "naturally_aspirated": "NA gasoline",
    "turbocharged": "Turbo gasoline",
    "diesel": "Diesel",
    "aircraft": "Aircraft piston",
    "motorcycle": "Motorcycle",
}

FAMILY_TARGETS = {
    "naturally_aspirated": 20,
    "turbocharged": 20,
    "diesel": 10,
    "aircraft": 10,
    "motorcycle": 10,
}


def _std(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    mean = sum(values) / len(values)
    var = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    return math.sqrt(var)


def _prediction_interval(mean: float | None, std: float | None, *, z: float = 1.96) -> list[float] | None:
    if mean is None or std is None:
        return None
    return [round(mean - z * std, 4), round(mean + z * std, 4)]


def run_family_distribution(family: str, rows: list[Any]) -> dict[str, Any]:
    """Per-family distribution: measured BMEP + mid-band displacement error."""
    validator = IndependentCampaignValidator()
    measured_bmep: list[float] = []
    disp_errors: list[float] = []
    failure_cases: list[dict[str, Any]] = []
    engines: list[dict[str, Any]] = []
    mid = FAMILY_BMEP_MID_BAR[family]

    for rec in rows:
        if rec.torque_nm is None or rec.displacement_l is None or rec.hp is None or rec.rpm is None:
            failure_cases.append(
                {
                    "engine_id": rec.engine_id,
                    "reason": "incomplete_torque_displacement_or_power_rpm",
                }
            )
            engines.append({"engine_id": rec.engine_id, "status": "incomplete"})
            continue
        # Reject synthetic-tagged sources
        if "synthetic" in (rec.source or "").lower() or "estimate" in (rec.source or "").lower():
            failure_cases.append({"engine_id": rec.engine_id, "reason": "synthetic_or_estimate"})
            continue

        bmep = bmep_bar_from_torque_displacement(float(rec.torque_nm), float(rec.displacement_l))
        indep_bmep = validator.bmep_bar(float(rec.torque_nm), float(rec.displacement_l))
        pred_disp = displacement_l_from_hp_rpm_bmep(float(rec.hp), float(rec.rpm), mid)
        err = (pred_disp - float(rec.displacement_l)) / float(rec.displacement_l)
        measured_bmep.append(bmep)
        disp_errors.append(err)
        engines.append(
            {
                "engine_id": rec.engine_id,
                "status": "ok",
                "measured_bmep_bar": round(bmep, 3),
                "independent_bmep_bar": round(indep_bmep, 3),
                "published_displacement_l": rec.displacement_l,
                "predicted_displacement_l_mid_band": round(pred_disp, 3),
                "relative_displacement_error": err,
                "assumed_bmep_mid_bar": mid,
                "source": rec.source,
            }
        )

    mean_bmep = sum(measured_bmep) / len(measured_bmep) if measured_bmep else None
    std_bmep = _std(measured_bmep)
    mae = sum(abs(e) for e in disp_errors) / len(disp_errors) if disp_errors else None
    bias = sum(disp_errors) / len(disp_errors) if disp_errors else None
    target = FAMILY_TARGETS[family]
    eligible = (
        len(disp_errors) >= target
        and mae is not None
        and mae < 0.15
        and std_bmep is not None
    )
    return {
        "family": FAMILY_DISPLAY[family],
        "family_id": family,
        "samples": len(disp_errors),
        "samples_total": len(rows),
        "target_samples": target,
        "mean_absolute_error": None if mae is None else round(mae, 4),
        "bias": None if bias is None else round(bias, 4),
        "measured_bmep_mean": None if mean_bmep is None else round(mean_bmep, 3),
        "measured_bmep_std": None if std_bmep is None else round(std_bmep, 3),
        "prediction_interval_95": _prediction_interval(mean_bmep, std_bmep),
        "uncertainty": uncertainty_label(mae, n=len(disp_errors)),
        "failure_cases": failure_cases,
        "eligible_for_m4": eligible,
        "assumed_bmep_mid_bar": mid,
        "engines": engines,
        "note": "Family never pooled. Mid-band assumption not retuned.",
    }


def run_bmep_distribution_campaign(*, dataset_path: Path | None = None) -> CampaignResult:
    if dataset_path is not None:
        # Optional override: expect JSON with family→list mapping; fall back to built-in.
        raw = json.loads(Path(dataset_path).read_text()) if Path(dataset_path).is_file() else None
        if raw:
            raise ValueError("Custom BMEP dataset path JSON override not used in Phase 10 — use built-in families")
    families = load_all_bmep_families()
    family_reports: dict[str, Any] = {}
    all_errors: list[float] = []
    failure_modes: list[str] = []
    successful = 0
    failed = 0
    accepted = 0

    for family in FAMILIES:
        report = run_family_distribution(family, families.get(family, []))
        family_reports[family] = report
        accepted += int(report["samples"])
        successful += int(report["samples"])
        failed += len(report["failure_cases"])
        for eng in report["engines"]:
            if eng.get("status") == "ok" and eng.get("relative_displacement_error") is not None:
                all_errors.append(float(eng["relative_displacement_error"]))
        if not report["eligible_for_m4"]:
            failure_modes.append(f"{family}_below_m4_threshold")

    # Never pool for eligibility — overall M4 only if EVERY family eligible.
    overall_eligible = all(r["eligible_for_m4"] for r in family_reports.values())
    if not overall_eligible and "insufficient_family_distributions" not in failure_modes:
        failure_modes.append("insufficient_family_distributions")

    result = finalize_result(
        campaign_id="bmep_distribution",
        model_id="engine_cycle_model",
        errors=all_errors,
        successful=successful,
        failed=failed,
        accepted=accepted,
        rejected=0,
        failure_modes=failure_modes if not overall_eligible else [],
        independent_verifier=True,
        details={"families": family_reports, "phase": "10.0", "pooled": False},
        min_cases_for_m4=sum(FAMILY_TARGETS.values()),
    )
    # Override eligibility: must be per-family, never pooled.
    result.eligible_for_m4 = overall_eligible
    result.eligible_for_upgrade = overall_eligible
    if overall_eligible:
        result.failure_modes = []
    return result


def write_bmep_campaign_result(output_dir: Path | str) -> Path:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    result = run_bmep_distribution_campaign()
    # Primary artifact: per-family summary list + full result
    families = result.details.get("families") or {}
    summary = {
        "campaign": "bmep_distribution",
        "phase": "10.0",
        "families": [
            {
                "family": fr["family"],
                "samples": fr["samples"],
                "mean_absolute_error": fr["mean_absolute_error"],
                "uncertainty": fr["uncertainty"],
                "eligible_for_m4": fr["eligible_for_m4"],
                "standard_deviation": fr["measured_bmep_std"],
                "prediction_interval": fr["prediction_interval_95"],
                "bias": fr["bias"],
                "failure_cases": len(fr["failure_cases"]),
            }
            for fr in families.values()
        ],
        "eligible_for_m4": result.eligible_for_m4,
        **result.to_dict(),
    }
    path = out / "bmep_campaign_result.json"
    path.write_text(json.dumps(summary, indent=2, default=str) + "\n")
    return path
