"""Independent high-RPM dynamics evaluator.

MUST NOT import PhysicsEngine, EngineeringEvaluator, MaterialAssigner,
or ConstraintEvaluator. Reimplements campaign identities from first principles.
"""

from __future__ import annotations

import math
from typing import Any

# SI constants — local to this campaign (do not pull production modules).
_HP_TO_W = 745.6998715822702  # exact-ish HP→W used in SI power identity
_HP_TO_KW = 0.745699872
_KW_TORQUE_CONSTANT = 9549.0  # common engineering: τ = P_kW * 9549 / N


def torque_nm_from_hp_rpm(horsepower: float, rpm: float) -> float:
    """τ = P / ω with P from HP→W and ω = 2π N/60.

    Directive form: HP × 745.7 / angular_velocity (W / (rad/s) → N·m).
    """
    if rpm == 0:
        raise ZeroDivisionError("rpm must be nonzero")
    power_w = horsepower * _HP_TO_W
    omega = 2.0 * math.pi * rpm / 60.0
    return power_w / omega


def torque_nm_engineering_constant(horsepower: float, rpm: float) -> float:
    """Cross-check: τ = P_kW * 9549 / N."""
    if rpm == 0:
        raise ZeroDivisionError("rpm must be nonzero")
    return (horsepower * _HP_TO_KW) * _KW_TORQUE_CONSTANT / rpm


def mean_piston_speed_m_s(stroke_m: float, rpm: float) -> float:
    """Vp = 2 × stroke × RPM / 60."""
    return 2.0 * stroke_m * rpm / 60.0


def peak_piston_acceleration_m_s2(stroke_m: float, rpm: float) -> float:
    """First-harmonic peak accel ≈ r ω² with r = S/2 — proportional to S × N²."""
    r = stroke_m / 2.0
    omega = 2.0 * math.pi * rpm / 60.0
    return r * omega**2


def accel_proportional_factor(stroke_m: float, rpm: float) -> float:
    """S × N² factor (relative checks without absolute OEM accel data)."""
    return stroke_m * (rpm**2)


def displacement_l_from_bmep_mid(
    horsepower: float,
    rpm: float,
    *,
    bmep_bar_mid: float = 14.0,
) -> float:
    """Four-stroke mid-band displacement estimate — for failure analysis only.

    V[L] = P[W] * 120 / (BMEP[Pa] * N) * 1000
    Uses NA catalog mid 14 bar — intentionally assumed; errors are evidence.
    """
    if rpm == 0:
        raise ZeroDivisionError("rpm must be nonzero")
    bmep_pa = bmep_bar_mid * 1e5
    power_w = horsepower * _HP_TO_KW * 1000.0
    return power_w * 120.0 / (bmep_pa * rpm) * 1000.0


def evaluate_engine(engine: dict[str, Any]) -> dict[str, Any]:
    """Per-engine independent checks. Never invents missing published fields."""
    pub = engine.get("published") or {}
    derived = engine.get("derived_checks") or {}
    hp = pub.get("horsepower")
    rpm = pub.get("max_rpm")
    stroke_mm = pub.get("stroke_mm")
    disp = pub.get("displacement_l")
    pub_torque = pub.get("torque_nm")

    row: dict[str, Any] = {
        "id": engine.get("id"),
        "name": engine.get("name"),
        "data_quality": engine.get("data_quality"),
        "verified_sources": list(engine.get("verified_sources") or []),
    }

    if hp is not None and rpm is not None:
        t_si = torque_nm_from_hp_rpm(float(hp), float(rpm))
        t_eng = torque_nm_engineering_constant(float(hp), float(rpm))
        identity_rel_err = abs(t_si - t_eng) / t_si if t_si else None
        row["torque"] = {
            "si_at_max_rpm_nm": t_si,
            "engineering_constant_nm": t_eng,
            "identity_relative_error": identity_rel_err,
            "published_peak_torque_nm": pub_torque,  # may be null
            "peak_vs_redline_relative_error": (
                None
                if pub_torque is None
                else abs(t_si - float(pub_torque)) / float(pub_torque)
            ),
            "note": (
                "Model under test is SI power/RPM identity at stated RPM. "
                "Published peak torque is a different operating point — not a gate metric."
            ),
        }
    else:
        row["torque"] = {"status": "skipped", "reason": "missing hp or rpm"}

    if stroke_mm is not None and rpm is not None:
        stroke_m = float(stroke_mm) / 1000.0
        mps = mean_piston_speed_m_s(stroke_m, float(rpm))
        dataset_mps = derived.get("mean_piston_speed_at_redline_m_s")
        mps_err = (
            None
            if dataset_mps is None
            else abs(mps - float(dataset_mps)) / float(dataset_mps)
        )
        accel = peak_piston_acceleration_m_s2(stroke_m, float(rpm))
        row["mean_piston_speed"] = {
            "independent_m_s": mps,
            "dataset_derived_m_s": dataset_mps,
            "relative_error": mps_err,
        }
        row["piston_acceleration"] = {
            "independent_m_s2": accel,
            "published_m_s2": pub.get("peak_piston_acceleration_m_s2"),
            "proportional_factor_S_N2": accel_proportional_factor(stroke_m, float(rpm)),
            "note": (
                "No OEM published peak accel in dataset (null). "
                "Validation uses kinematic identity + S×N² proportionality."
            ),
        }
    else:
        row["mean_piston_speed"] = {"status": "skipped"}
        row["piston_acceleration"] = {"status": "skipped"}

    if hp is not None and rpm is not None and disp is not None:
        est = displacement_l_from_bmep_mid(float(hp), float(rpm))
        err = abs(est - float(disp)) / float(disp)
        row["displacement_estimation"] = {
            "published_l": disp,
            "mid_bmep_estimate_l": est,
            "bmep_bar_mid_assumed": 14.0,
            "relative_error": err,
            "note": "Assumed BMEP mid-band — expected to fail design prediction accuracy.",
        }
    else:
        row["displacement_estimation"] = {"status": "skipped"}

    return row


def evaluate_dataset(engines: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "campaign": "high_rpm_dynamics",
        "engines": [evaluate_engine(e) for e in engines],
        "physics_relationship_checks": _relationship_checks(),
    }


def _relationship_checks() -> dict[str, Any]:
    """Fixed-HP / fixed-stroke monotonicity — must hold for campaign identities."""
    hp = 800.0
    stroke = 0.08
    t_low = torque_nm_from_hp_rpm(hp, 8000.0)
    t_high = torque_nm_from_hp_rpm(hp, 9000.0)
    mps_low = mean_piston_speed_m_s(stroke, 8000.0)
    mps_high = mean_piston_speed_m_s(stroke, 9000.0)
    a_low = peak_piston_acceleration_m_s2(stroke, 8000.0)
    a_high = peak_piston_acceleration_m_s2(stroke, 9000.0)
    return {
        "higher_rpm_lowers_torque_at_fixed_hp": t_high < t_low,
        "higher_rpm_raises_mps_at_fixed_stroke": mps_high > mps_low,
        "higher_rpm_raises_accel_at_fixed_stroke": a_high > a_low,
        "samples": {
            "torque_nm_8000": t_low,
            "torque_nm_9000": t_high,
            "mps_8000": mps_low,
            "mps_9000": mps_high,
            "accel_8000": a_low,
            "accel_9000": a_high,
        },
    }
