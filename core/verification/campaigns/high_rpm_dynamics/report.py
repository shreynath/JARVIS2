"""Campaign A reports — validation JSON + failure packets (no maturity mutation)."""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.verification.campaigns.high_rpm_dynamics.dataset import load_high_rpm_dataset
from core.verification.campaigns.high_rpm_dynamics.evaluator import evaluate_dataset


def _summary(
    *,
    model: str,
    errors: list[float],
    uncertainty: str,
    validation_quality: str,
    passed: bool,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    mean_err = sum(errors) / len(errors) if errors else None
    max_err = max(errors) if errors else None
    payload = {
        "model": model,
        "samples": len(errors),
        "mean_error": mean_err,
        "max_error": max_err,
        "uncertainty": uncertainty,
        "validation_quality": validation_quality,
        "maturity_gate": "M2_to_M3",
        "passed": passed,
    }
    if extra:
        payload.update(extra)
    return payload


def build_validation_report(evaluation: dict[str, Any] | None = None) -> dict[str, Any]:
    evaluation = evaluation or evaluate_dataset(load_high_rpm_dataset())
    engines = evaluation["engines"]

    # --- Torque: SI identity dual-path (not published peak) ---
    torque_errs = []
    for e in engines:
        t = e.get("torque") or {}
        err = t.get("identity_relative_error")
        if err is not None:
            torque_errs.append(float(err))
    torque = _summary(
        model="calc_torque",
        errors=torque_errs,
        uncertainty=(
            "Dual-path SI vs engineering-constant relative discrepancy; "
            "HP/RPM published figures typical OEM rounding ±1–2%."
        ),
        validation_quality="manufacturer",
        passed=bool(torque_errs) and max(torque_errs) < 0.01,
        extra={
            "metric": "si_vs_engineering_identity",
            "equations_documented": True,
            "independent_verifier": True,
            "known_limitations": [
                "Does not model friction or accessory loads.",
                "SI torque at redline is not published peak torque.",
            ],
        },
    )

    # --- MPS: independent vs dataset derived kinematic note ---
    mps_errs = []
    for e in engines:
        m = e.get("mean_piston_speed") or {}
        err = m.get("relative_error")
        if err is not None:
            mps_errs.append(float(err))
    mps = _summary(
        model="calc_mean_piston_speed",
        errors=mps_errs,
        uncertainty="Stroke publishing resolution typically ±0.1 mm → low-tenths % MPS effect.",
        validation_quality="manufacturer",
        passed=bool(mps_errs) and max(mps_errs) < 0.01,
        extra={
            "metric": "independent_vs_dataset_derived_mps",
            "equations_documented": True,
            "independent_verifier": True,
            "known_limitations": [
                "Kinematic definition only.",
                "Hard limit 26 m/s is an engineering standard, not a physics law.",
            ],
        },
    )

    # --- Acceleration: proportionality residual across engine pairs ---
    accel_rows = []
    for e in engines:
        a = e.get("piston_acceleration") or {}
        if a.get("proportional_factor_S_N2") is not None and a.get("independent_m_s2") is not None:
            accel_rows.append(a)
    # residual: a / (S N²) should be constant (= 2 π² / 3600)
    theoretical = 2.0 * (math.pi**2) / 3600.0
    accel_errs = []
    for a in accel_rows:
        factor = float(a["proportional_factor_S_N2"])
        if factor == 0:
            continue
        predicted = theoretical * factor
        actual = float(a["independent_m_s2"])
        accel_errs.append(abs(actual - predicted) / predicted)
    accel = _summary(
        model="calc_piston_acceleration",
        errors=accel_errs,
        uncertainty=(
            "First-harmonic only; rod-ratio secondary term omitted "
            "(typical few-% vs full kinematic series at high λ)."
        ),
        validation_quality="manufacturer_geometry",
        passed=bool(accel_errs) and max(accel_errs) < 0.01,
        extra={
            "metric": "first_harmonic_identity_and_S_N2_proportionality",
            "equations_documented": True,
            "independent_verifier": True,
            "published_absolute_accel_available": False,
            "known_limitations": [
                "No OEM published peak piston acceleration in campaign dataset (null).",
                "First-harmonic approximation.",
            ],
        },
    )

    # --- Displacement estimate: mid BMEP — expected fail ---
    disp_errs = []
    for e in engines:
        d = e.get("displacement_estimation") or {}
        err = d.get("relative_error")
        if err is not None:
            disp_errs.append(float(err))
    disp = _summary(
        model="displacement_estimation",
        errors=disp_errs,
        uncertainty="Dominated by assumed NA BMEP mid-band (14 bar).",
        validation_quality="assumption_vs_manufacturer_geometry",
        passed=bool(disp_errs) and max(disp_errs) < 0.05,
        extra={
            "metric": "mid_bmep_estimate_vs_published_displacement",
            "equations_documented": True,
            "independent_verifier": True,
            "known_limitations": [
                "BMEP band is empirical catalog assumption, not measured BSFC.",
            ],
            "maturity_gate": "M2_to_M3",
        },
    )

    return {
        "phase": "8.5",
        "campaign": "high_rpm_dynamics",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "models": [torque, mps, accel, disp],
        "physics_relationship_checks": evaluation["physics_relationship_checks"],
        "engine_results": engines,
        "policy": "Reports evidence only — does not modify MODEL_REGISTRY.",
    }


def build_failure_packet(validation: dict[str, Any] | None = None) -> dict[str, Any]:
    validation = validation or build_validation_report()
    failures: list[dict[str, Any]] = []
    for model_row in validation["models"]:
        if model_row.get("passed"):
            continue
        model = model_row["model"]
        if model == "displacement_estimation":
            failures.append(
                {
                    "model": model,
                    "status": "failed",
                    "error": model_row.get("mean_error"),
                    "max_error": model_row.get("max_error"),
                    "cause": "BMEP assumption uncertainty",
                    "action": "requires BMEP campaign",
                    "model_change_justified": False,
                    "reason": (
                        "Displacement identity is correct; mid-band BMEP assumption "
                        "does not predict published displacement tightly. "
                        "Do not retune equations — acquire BMEP family evidence."
                    ),
                }
            )
        else:
            failures.append(
                {
                    "model": model,
                    "status": "failed",
                    "error": model_row.get("mean_error"),
                    "max_error": model_row.get("max_error"),
                    "cause": "campaign criteria not met",
                    "action": "retain current maturity; expand evidence",
                    "model_change_justified": False,
                }
            )

    # Always record the known torque peak≠redline limitation as non-blocking evidence.
    peak_cases = []
    for e in validation.get("engine_results") or []:
        t = e.get("torque") or {}
        if t.get("peak_vs_redline_relative_error") is not None:
            peak_cases.append(
                {
                    "id": e.get("id"),
                    "peak_vs_redline_relative_error": t["peak_vs_redline_relative_error"],
                }
            )
    return {
        "phase": "8.5",
        "campaign": "high_rpm_dynamics",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "failures": failures,
        "non_blocking_known_limitations": [
            {
                "model": "calc_torque",
                "status": "documented_limitation",
                "cause": "Published peak torque ≠ SI torque at redline HP/RPM",
                "cases": peak_cases,
                "model_change_justified": False,
                "action": "Keep identity model; never calibrate to peak torque.",
            }
        ],
        "policy": "Failure is evidence. No equation retuning from this packet.",
    }


def write_high_rpm_reports(output_dir: Path | str) -> dict[str, Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    validation = build_validation_report()
    failures = build_failure_packet(validation)
    v_path = out / "high_rpm_dynamics_validation.json"
    f_path = out / "high_rpm_failure_packet.json"
    v_path.write_text(json.dumps(validation, indent=2, default=str))
    f_path.write_text(json.dumps(failures, indent=2, default=str))
    return {"validation": v_path, "failures": f_path}


def evaluate_high_rpm_campaign() -> dict[str, Any]:
    """Convenience: load → evaluate → validation report."""
    return build_validation_report()
