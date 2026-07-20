"""Phase 6 — calibration reports errors; never mutates models to fit data."""

from __future__ import annotations

from core.verification.calibration import (
    CalibrationResult,
    compare_prediction,
    independent_kinematics_predictor,
    run_calibration,
)
from core.verification.datasets.sources import manufacturer_source
from core.verification.datasets.validation_case import (
    SystemType,
    ValidationCase,
    ValidationQuality,
)
from core.verification.model_registry import MODEL_REGISTRY
from core.verification.model_maturity import ModelMaturity


def test_intentionally_wrong_prediction_reports_error():
    result = compare_prediction(
        case_id="synthetic",
        quantity="torque_nm",
        predicted=1000.0,
        measured=500.0,
        relative_tol=0.05,
    )
    assert isinstance(result, CalibrationResult)
    assert result.pass_status == "fail"
    assert result.absolute_error == 500.0
    assert abs(result.relative_error - 1.0) < 1e-9


def test_calibration_does_not_mutate_registry_maturity():
    before = {mid: desc.maturity for mid, desc in MODEL_REGISTRY.items()}
    case = ValidationCase(
        id="toy",
        system_type=SystemType.ENGINE,
        reference_source=manufacturer_source(name="Toy"),
        inputs={"horsepower": 800, "max_rpm": 9000},
        measured_outputs={"mean_piston_speed_m_s": 10.0, "stroke_mm": 80.0},  # wrong MPS on purpose
        validation_quality=ValidationQuality.MANUFACTURER,
    )
    report = run_calibration(
        [case],
        independent_kinematics_predictor,
        model_id="independent_kinematics",
        quantities=["mean_piston_speed_m_s"],
    )
    assert any(r["pass_status"] == "fail" for r in report["results"])
    after = {mid: desc.maturity for mid, desc in MODEL_REGISTRY.items()}
    assert before == after
    assert MODEL_REGISTRY["calc_rod_loading"].maturity is ModelMaturity.M3


def test_unknown_measurement_not_forced_to_pass():
    result = compare_prediction(
        case_id="x",
        quantity="compression_ratio",
        predicted=12.5,
        measured=None,
    )
    assert result.pass_status == "unknown"
    assert result.measured is None
