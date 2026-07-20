"""External calibration — compare predictions to measured reality.

Never tunes models. Reports errors only.
Independent analytical predictors live here (verification.formulas).
JARVIS open-loop predictors must live outside this module (runner/CLI).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Callable

from core.verification.datasets.validation_case import ValidationCase
from verification.formulas import (
    mean_piston_speed_m_s,
    torque_nm_from_hp_rpm,
)


@dataclass(frozen=True)
class CalibrationResult:
    case_id: str
    quantity: str
    predicted: float | None
    measured: float | None
    absolute_error: float | None
    relative_error: float | None
    uncertainty_interval: float | None
    pass_status: str  # pass | fail | skipped | unknown
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


Predictor = Callable[[ValidationCase], dict[str, float | None]]


def compare_prediction(
    *,
    case_id: str,
    quantity: str,
    predicted: float | None,
    measured: float | None,
    uncertainty: float | None = None,
    relative_tol: float = 0.10,
) -> CalibrationResult:
    """Compute errors. Never adjusts the prediction."""
    if measured is None:
        return CalibrationResult(
            case_id=case_id,
            quantity=quantity,
            predicted=predicted,
            measured=None,
            absolute_error=None,
            relative_error=None,
            uncertainty_interval=uncertainty,
            pass_status="unknown",
            notes="measured value unavailable — left unknown",
        )
    if predicted is None:
        return CalibrationResult(
            case_id=case_id,
            quantity=quantity,
            predicted=None,
            measured=measured,
            absolute_error=None,
            relative_error=None,
            uncertainty_interval=uncertainty,
            pass_status="skipped",
            notes="no prediction produced",
        )
    abs_err = abs(predicted - measured)
    rel_err = abs_err / abs(measured) if measured != 0 else None
    if rel_err is None:
        status = "fail"
    elif uncertainty is not None and abs_err <= uncertainty:
        status = "pass"
    elif rel_err <= relative_tol:
        status = "pass"
    else:
        status = "fail"
    return CalibrationResult(
        case_id=case_id,
        quantity=quantity,
        predicted=predicted,
        measured=measured,
        absolute_error=abs_err,
        relative_error=rel_err,
        uncertainty_interval=uncertainty,
        pass_status=status,
    )


def independent_kinematics_predictor(case: ValidationCase) -> dict[str, float | None]:
    """Independent verification model — MPS from published stroke/RPM.

    Torque at redline is also computed from HP+RPM for reporting, but must not be
    compared against published *peak* torque (usually a different RPM) without
    an explicit torque-at-max-rpm measurement.
    """
    hp = case.inputs.get("horsepower")
    rpm = case.inputs.get("max_rpm")
    stroke_mm = case.measured_outputs.get("stroke_mm")
    out: dict[str, float | None] = {
        "torque_at_max_rpm_nm": None,
        "mean_piston_speed_m_s": None,
    }
    if hp is not None and rpm is not None and float(rpm) != 0:
        out["torque_at_max_rpm_nm"] = torque_nm_from_hp_rpm(float(hp), float(rpm))
    if stroke_mm is not None and rpm is not None:
        out["mean_piston_speed_m_s"] = mean_piston_speed_m_s(
            float(stroke_mm) / 1000.0, float(rpm)
        )
    return out


def calibrate_case(
    case: ValidationCase,
    predictor: Predictor,
    *,
    quantities: list[str] | None = None,
    relative_tol: float = 0.10,
) -> list[CalibrationResult]:
    predicted = predictor(case)
    keys = quantities or sorted(set(predicted) | set(case.measured_outputs))
    results: list[CalibrationResult] = []
    for quantity in keys:
        if quantity not in predicted and quantity not in case.measured_outputs:
            continue
        unc = case.uncertainty.get(quantity)
        # Manufacturer uncertainty is often percent; convert when values look like %
        unc_abs = None
        measured = case.measured(quantity)
        if unc is not None and measured is not None:
            # treat uncertainty entries as percent of measurement when < 50
            unc_abs = abs(measured) * (unc / 100.0) if unc < 50 else unc
        results.append(
            compare_prediction(
                case_id=case.id,
                quantity=quantity,
                predicted=predicted.get(quantity),
                measured=measured,
                uncertainty=unc_abs,
                relative_tol=relative_tol,
            )
        )
    return results


def run_calibration(
    cases: list[ValidationCase],
    predictor: Predictor,
    *,
    model_id: str,
    quantities: list[str] | None = None,
    relative_tol: float = 0.10,
) -> dict[str, Any]:
    """Batch calibration. Reports only — never mutates models."""
    rows: list[CalibrationResult] = []
    for case in cases:
        rows.extend(
            calibrate_case(
                case, predictor, quantities=quantities, relative_tol=relative_tol
            )
        )
    return {
        "model": model_id,
        "case_count": len(cases),
        "result_count": len(rows),
        "results": [r.to_dict() for r in rows],
        "policy": (
            "Compare prediction to external measurement. "
            "Errors are reported; models are never adjusted to fit."
        ),
    }
