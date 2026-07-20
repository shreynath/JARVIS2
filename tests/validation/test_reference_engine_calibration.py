"""Phase 6 — reference engine validation cases cover required kinematics."""

from __future__ import annotations

from pathlib import Path

from core.verification.calibration import (
    independent_kinematics_predictor,
    run_calibration,
)
from core.verification.datasets.registry import load_engine_validation_cases
from verification.benchmark import kinematic_check, load_engines

ENGINES = Path(__file__).resolve().parents[2] / "datasets" / "reference_engines"

REQUIRED = {
    "honda_f20c",
    "ferrari_f140",
    "bmw_s65",
    "chevy_ls7",
    "cosworth_dfv",
    "lycoming_io360",
    "toyota_2jz_gte",
    "nissan_vr38dett",
    "bmw_s85",
    "ferrari_458_f136",
    "ferrari_812_f140",
    "lexus_lfa_1lr_gue",
    "porsche_991_gt3_ma1",
    "porsche_991_turbo",
    "mercedes_m159",
}


def test_required_phase6_engines_present():
    ids = {p.stem for p in ENGINES.glob("*.json")}
    assert REQUIRED <= ids
    assert len(ids) >= 20


def test_every_engine_kinematic_check_passes():
    for engine in load_engines():
        check = kinematic_check(engine)
        assert check["status"] == "pass", (engine["id"], check)


def test_independent_mps_calibrates_against_published_derived():
    cases = load_engine_validation_cases()
    report = run_calibration(
        cases,
        independent_kinematics_predictor,
        model_id="independent_kinematics",
        quantities=["mean_piston_speed_m_s"],
        relative_tol=0.05,
    )
    mps_rows = [
        r
        for r in report["results"]
        if r["quantity"] == "mean_piston_speed_m_s" and r["pass_status"] != "unknown"
    ]
    assert len(mps_rows) >= 15
    assert all(r["pass_status"] == "pass" for r in mps_rows)


def test_published_peak_torque_is_not_confused_with_redline_identity():
    """Honesty: published peak torque must not be treated as max-RPM SI torque."""
    cases = {c.id: c for c in load_engine_validation_cases()}
    f20c = cases["honda_f20c"]
    pred = independent_kinematics_predictor(f20c)
    assert pred["torque_at_max_rpm_nm"] is not None
    # Peak published torque (if present) is a different quantity — may differ from redline SI.
    if f20c.measured_outputs.get("torque_nm") is not None:
        # Calibration of redline identity is not claimed against peak torque.
        assert "torque_nm" not in pred


def test_validation_case_count_matches_engine_files():
    assert len(load_engine_validation_cases()) == len(list(ENGINES.glob("*.json")))
