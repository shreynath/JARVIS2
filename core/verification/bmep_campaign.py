"""Phase 8.7 BMEP / displacement prediction campaign — families never pooled."""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.verification.datasets.bmep import (
    FAMILIES,
    bmep_bar_from_torque_displacement,
    displacement_l_from_hp_rpm_bmep,
    load_all_bmep_families,
)

# Mid-band assumptions for open-loop displacement prediction (not retuned).
FAMILY_BMEP_MID_BAR = {
    "naturally_aspirated": 14.0,
    "turbocharged": 20.5,
    "diesel": 18.0,  # light-duty turbo diesel placeholder band mid — documented assumed
    "aircraft": 10.0,  # low-BMEP NA aero gasoline placeholder — documented assumed
    "motorcycle": 13.0,  # high-RPM motorcycle NA mid — documented assumed
}


def _stats(errors: list[float]) -> dict[str, float | None]:
    if not errors:
        return {"n": 0, "mae": None, "rmse": None, "bias": None, "variance": None}
    n = len(errors)
    mean = sum(errors) / n
    mae = sum(abs(e) for e in errors) / n
    rmse = math.sqrt(sum(e * e for e in errors) / n)
    var = sum((e - mean) ** 2 for e in errors) / n
    return {"n": n, "mae": mae, "rmse": rmse, "bias": mean, "variance": var}


def build_bmep_campaign_report() -> dict[str, Any]:
    families = load_all_bmep_families()
    family_reports: dict[str, Any] = {}
    for family, rows in families.items():
        measured: list[dict[str, Any]] = []
        disp_errors: list[float] = []
        bmep_vals: list[float] = []
        mid = FAMILY_BMEP_MID_BAR[family]
        for rec in rows:
            raw_path_note = None
            if rec.torque_nm is None or rec.displacement_l is None:
                measured.append(
                    {
                        "engine_id": rec.engine_id,
                        "status": "incomplete",
                        "torque_nm": rec.torque_nm,
                        "displacement_l": rec.displacement_l,
                    }
                )
                continue
            if rec.hp is None or rec.rpm is None:
                measured.append(
                    {
                        "engine_id": rec.engine_id,
                        "status": "incomplete_power_rpm",
                    }
                )
                continue
            bmep = bmep_bar_from_torque_displacement(
                float(rec.torque_nm), float(rec.displacement_l)
            )
            pred_disp = displacement_l_from_hp_rpm_bmep(
                float(rec.hp), float(rec.rpm), mid
            )
            err = (pred_disp - float(rec.displacement_l)) / float(rec.displacement_l)
            bmep_vals.append(bmep)
            disp_errors.append(err)
            measured.append(
                {
                    "engine_id": rec.engine_id,
                    "status": "ok",
                    "measured_bmep_bar": round(bmep, 3),
                    "published_displacement_l": rec.displacement_l,
                    "predicted_displacement_l_mid_band": round(pred_disp, 3),
                    "relative_displacement_error": err,
                    "assumed_bmep_mid_bar": mid,
                    "source": rec.source,
                }
            )
        family_reports[family] = {
            "samples_total": len(rows),
            "samples_complete": sum(1 for m in measured if m.get("status") == "ok"),
            "assumed_bmep_mid_bar": mid,
            "measured_bmep_mean": (
                sum(bmep_vals) / len(bmep_vals) if bmep_vals else None
            ),
            "displacement_error": _stats(disp_errors),
            "engines": measured,
            "note": "Family never pooled with other aspiration/fuel classes.",
        }

    # Baseline 800 HP / 9000 RPM NA V12 narrative answer
    na_mid = FAMILY_BMEP_MID_BAR["naturally_aspirated"]
    pred = displacement_l_from_hp_rpm_bmep(800.0, 9000.0, na_mid)
    na_err = family_reports["naturally_aspirated"]["displacement_error"]
    uncertainty_l = None
    if na_err.get("mae") is not None:
        uncertainty_l = abs(pred) * float(na_err["mae"])

    return {
        "phase": "8.7",
        "campaign": "bmep_displacement",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "families": family_reports,
        "family_counts": {f: len(families[f]) for f in FAMILIES},
        "baseline_design_answer": {
            "input": "Design 9000 RPM naturally aspirated V12 800 HP",
            "required_displacement_l": round(pred, 2),
            "confidence": "medium",
            "reason": "BMEP mid-band assumption for NA high-performance gasoline",
            "evidence": "naturally_aspirated family campaign",
            "uncertainty_l": None if uncertainty_l is None else round(uncertainty_l, 2),
            "limitation": "BMEP distribution dominates displacement error",
            "assumed_bmep_bar": na_mid,
        },
        "models": [
            {
                "model": "engine_cycle_model",
                "current": "M2",
                "target": "M4",
                "upgrade_recommendation": "NOT M4 eligible — mid-band prediction errors remain large; need mapped BMEP distributions",
            },
            {
                "model": "bmep_assumption_bands",
                "current": "M2",
                "target": "M3/M4",
                "upgrade_recommendation": "Family datasets established; M4 withheld until predictive bias <15% with quantified uncertainty",
            },
            {
                "model": "calc_displacement",
                "current": "M3",
                "target": "M4",
                "upgrade_recommendation": "NOT M4 eligible — inherits BMEP band uncertainty",
            },
        ],
        "policy": "Never retune BMEP bands to fit campaign errors. Families never pooled.",
    }


def build_bmep_failure_analysis(report: dict[str, Any] | None = None) -> dict[str, Any]:
    report = report or build_bmep_campaign_report()
    failures = []
    for fam, block in (report.get("families") or {}).items():
        err = block.get("displacement_error") or {}
        mae = err.get("mae")
        if mae is None:
            failures.append(
                {
                    "family": fam,
                    "status": "insufficient_complete_samples",
                    "cause": "Missing torque and/or displacement for BMEP identity",
                    "action": "Acquire published peak torque + displacement pairs",
                    "model_change_justified": False,
                }
            )
        elif mae > 0.15:
            failures.append(
                {
                    "family": fam,
                    "status": "failed_prediction_tolerance",
                    "error": mae,
                    "cause": "BMEP mid-band assumption mismatch vs published displacement",
                    "action": "requires BMEP distribution / duty-cycle campaign (not constant retune)",
                    "model_change_justified": False,
                }
            )
    return {
        "phase": "8.7",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "failures": failures,
        "policy": "Failure is evidence. Do not widen/narrow bands to chase MAE.",
    }


def build_bmep_maturity_packet(
    report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    report = report or build_bmep_campaign_report()
    na = (report.get("families") or {}).get("naturally_aspirated") or {}
    n = (na.get("displacement_error") or {}).get("n") or 0
    mae = (na.get("displacement_error") or {}).get("mae")
    eligible = bool(n >= 10 and mae is not None and mae < 0.15)
    return {
        "phase": "8.7",
        "eligible_for_upgrade": False,  # M4 not claimed from mid-band alone
        "eligible_models": [],
        "blocked_reason": (
            "Displacement MAE remains dominated by BMEP assumptions; "
            f"NA complete samples={n}, MAE={mae}"
        ),
        "family_separation_ok": True,
        "baseline_design_answer": report.get("baseline_design_answer"),
        "models": report.get("models"),
        "m4_policy": "M4 requires predictive BMEP model with bias/uncertainty, not band midpoints.",
    }


def write_bmep_campaign_reports(output_dir: Path | str) -> dict[str, Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    report = build_bmep_campaign_report()
    failures = build_bmep_failure_analysis(report)
    packet = build_bmep_maturity_packet(report)
    paths = {
        "validation": out / "bmep_campaign_report.json",
        "failures": out / "bmep_failure_analysis.json",
        "maturity": out / "bmep_maturity_packet.json",
    }
    paths["validation"].write_text(json.dumps(report, indent=2, default=str))
    paths["failures"].write_text(json.dumps(failures, indent=2, default=str))
    paths["maturity"].write_text(json.dumps(packet, indent=2, default=str))
    return paths
