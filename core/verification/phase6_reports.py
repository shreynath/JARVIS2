"""Phase 6 calibration / validation report writers."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.verification.calibration import (
    independent_kinematics_predictor,
    run_calibration,
)
from core.verification.datasets.registry import all_validation_cases
from core.verification.error_analysis import (
    build_model_error_report,
    build_validation_matrix,
    characterize_errors,
)
from core.verification.failure_prediction import rank_failure_risks
from core.verification.model_maturity import ModelMaturity
from core.verification.model_registry import MODEL_REGISTRY


def build_calibration_report(
    *,
    include_jarvis: bool = True,
) -> dict[str, Any]:
    cases = all_validation_cases()
    independent = run_calibration(
        cases,
        independent_kinematics_predictor,
        model_id="independent_kinematics",
        quantities=["mean_piston_speed_m_s"],
        relative_tol=0.02,
    )
    jarvis: dict[str, Any] | None = None
    if include_jarvis:
        from verification.jarvis_predictor import jarvis_open_loop_predictor

        jarvis = run_calibration(
            cases,
            jarvis_open_loop_predictor,
            model_id="jarvis_open_loop",
            quantities=[
                "torque_nm",
                "displacement_l",
                "stroke_mm",
                "mean_piston_speed_m_s",
            ],
            relative_tol=0.25,  # open-loop sizing — wide tol; still reports absolute errors
        )
    return {
        "phase": "6.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "external_case_count": len(cases),
        "independent": independent,
        "jarvis_open_loop": jarvis,
        "policy": (
            "External datasets are truth. Predictions are compared, never fitted."
        ),
    }


def build_per_model_validation_summary(error_report: dict[str, Any]) -> list[dict[str, Any]]:
    """Shape required by Deliverable 5 example rows."""
    rows: list[dict[str, Any]] = []
    jarvis_q = ((error_report.get("jarvis_open_loop") or {}).get("quantities")) or {}
    ind_q = ((error_report.get("independent_verification_model") or {}).get("quantities")) or {}

    mapping = {
        "stroke_mm": ("stroke_estimation", "M2"),
        "displacement_l": ("displacement_bmep_sizing", "M3"),
        "torque_nm": ("torque_identity", "M2"),
        "mean_piston_speed_m_s": ("mean_piston_speed", "M2"),
    }
    for quantity, (label, maturity) in mapping.items():
        meta = jarvis_q.get(quantity) or ind_q.get(quantity) or {}
        rows.append(
            {
                "model": label,
                "quantity": quantity,
                "samples": meta.get("samples", 0),
                "mean_error": meta.get("mean_error"),
                "median_error": meta.get("median_error"),
                "bias": meta.get("bias"),
                "validation_quality": "manufacturer",
                "maturity_supported": maturity,
                "upgrade_required": meta.get("upgrade_required", True),
                "interpretation": meta.get("interpretation"),
            }
        )
    return rows


def write_phase6_reports(
    output_dir: Path | str,
    *,
    include_jarvis: bool = True,
) -> dict[str, Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    calibration = build_calibration_report(include_jarvis=include_jarvis)
    error_report = build_model_error_report(
        independent_calibration=calibration["independent"],
        jarvis_calibration=calibration.get("jarvis_open_loop"),
    )
    all_results = list(calibration["independent"]["results"])
    if calibration.get("jarvis_open_loop"):
        all_results.extend(calibration["jarvis_open_loop"]["results"])
    matrix = build_validation_matrix(all_results)
    risks = rank_failure_risks(
        external_case_count=calibration["external_case_count"],
        error_report=error_report,
    )

    maturity_snapshot = {
        m.name: sum(1 for d in MODEL_REGISTRY.values() if d.maturity is m)
        for m in ModelMaturity
    }

    payloads = {
        "calibration_report.json": calibration,
        "model_error_report.json": {
            **error_report,
            "per_model_summary": build_per_model_validation_summary(error_report),
        },
        "model_validation_matrix.json": matrix,
        "validation_matrix.json": matrix,  # alias requested by Phase 6 script
        "failure_prediction_report.json": risks,
        "maturity_report.json": {
            "phase": "6.0",
            "counts": maturity_snapshot,
            "note": "Maturity levels unchanged from Phase 5.0 unless upgrade evidence passes gates.",
            "models": {
                mid: {
                    "maturity": d.maturity.name,
                    "benchmarked": d.benchmarked,
                    "independently_verified": d.independently_verified,
                    "known_limitations": d.known_limitations,
                }
                for mid, d in sorted(MODEL_REGISTRY.items())
            },
        },
        "upgrade_priorities.json": {
            "phase": "6.0",
            "highest_risk_models": risks["highest_risk_models"],
            "scoring": risks["scoring"],
        },
    }

    paths: dict[str, Path] = {}
    for name, payload in payloads.items():
        path = out / name
        path.write_text(json.dumps(payload, indent=2, default=str))
        paths[name] = path
    return paths
