"""Phase 6 — error analysis, failure prediction, and report surfaces."""

from __future__ import annotations

import json
from pathlib import Path

from core.verification.calibration import (
    compare_prediction,
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
from core.verification.phase6_reports import write_phase6_reports
from core.verification.model_registry import MODEL_REGISTRY
from core.verification.model_maturity import ModelMaturity


def test_characterize_errors_detects_positive_bias():
    rows = [
        compare_prediction(
            case_id=f"c{i}",
            quantity="displacement_l",
            predicted=1.12,
            measured=1.0,
        ).to_dict()
        for i in range(5)
    ]
    report = characterize_errors(rows)
    meta = report["quantities"]["displacement_l"]
    assert meta["bias"] == "+"
    assert meta["samples"] == 5
    assert "overprediction" in meta["interpretation"]


def test_failure_prediction_ranks_high_impact_unbenchmarked():
    risks = rank_failure_risks(external_case_count=len(all_validation_cases()))
    assert risks["highest_risk_models"]
    top_ids = {r["model"] for r in risks["highest_risk_models"]}
    # Rod / combustion / heat models should appear among high-risk set
    assert top_ids & {
        "calc_rod_loading",
        "calc_combustion_side_temperature",
        "calc_heat_rejection",
        "connecting_rod_model",
    }


def test_write_phase6_reports_independent_only(tmp_path: Path):
    paths = write_phase6_reports(tmp_path, include_jarvis=False)
    for name in (
        "calibration_report.json",
        "model_error_report.json",
        "model_validation_matrix.json",
        "validation_matrix.json",
        "maturity_report.json",
        "upgrade_priorities.json",
        "failure_prediction_report.json",
    ):
        assert name in paths
        payload = json.loads((tmp_path / name).read_text())
        assert payload

    calib = json.loads((tmp_path / "calibration_report.json").read_text())
    assert calib["external_case_count"] >= 20
    assert calib["jarvis_open_loop"] is None

    maturity = json.loads((tmp_path / "maturity_report.json").read_text())
    assert maturity["counts"]["M4"] == 0
    assert maturity["counts"]["M5"] == 0


def test_phase5_maturity_histogram_locked():
    counts = {m.name: 0 for m in ModelMaturity}
    for d in MODEL_REGISTRY.values():
        counts[d.maturity.name] += 1
    # Phase 7.0 closure: BMEP→M2 + engine_cycle/thermal models added; M4/M5 still 0.
    assert counts == {"M0": 3, "M1": 1, "M2": 9, "M3": 10, "M4": 0, "M5": 0}


def test_validation_matrix_keys():
    cases = all_validation_cases()[:3]
    report = run_calibration(
        cases,
        independent_kinematics_predictor,
        model_id="independent_kinematics",
        quantities=["torque_nm"],
    )
    matrix = build_validation_matrix(report["results"])
    assert matrix["case_count"] == 3
    err = build_model_error_report(independent_calibration=report)
    assert "independent_verification_model" in err
