"""Independent formula validation against reported physics JSON (no PhysicsEngine import)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from verification.formulas import (
    classify_error,
    combustion_temp_empirical_c,
    heat_rejection_kw,
    mean_piston_speed_m_s,
    peak_piston_acceleration_m_s2,
    percent_error,
    rod_stress_mpa,
    stroke_m_from_volume_ratio,
    torque_nm_from_english,
    torque_nm_from_hp_rpm,
    verify_record,
)

ROOT = Path(__file__).resolve().parents[1]


def _by_id(physics: dict, calc_id: str) -> dict | None:
    for c in physics.get("calculations") or []:
        if c.get("id") == calc_id:
            return c
    return None


def validate_physics_json(physics: dict[str, Any]) -> dict[str, Any]:
    """Independently recompute what can be recomputed from calc inputs."""
    records: list[dict[str, Any]] = []

    torque = _by_id(physics, "calc_torque")
    if torque and torque.get("status") == "computed":
        hp = float(torque["inputs"]["horsepower"])
        rpm = float(torque["inputs"]["rpm"])
        expected = torque_nm_from_hp_rpm(hp, rpm)
        expected_en = torque_nm_from_english(hp, rpm)
        records.append(verify_record("torque_si_path", expected, float(torque["result"]), unit="Nm"))
        records.append(
            verify_record("torque_english_crosscheck", expected_en, float(torque["result"]), unit="Nm", pass_tol=0.1)
        )

    mps = _by_id(physics, "calc_mean_piston_speed")
    if mps and mps.get("status") == "computed":
        rpm = float(mps["inputs"]["max_rpm"])
        s_low = float(mps["inputs"]["stroke_mm_low"]) / 1000.0
        s_high = float(mps["inputs"]["stroke_mm_high"]) / 1000.0
        exp_low = mean_piston_speed_m_s(s_low, rpm)
        exp_high = mean_piston_speed_m_s(s_high, rpm)
        actual_range = mps.get("value_range") or [mps["result"], mps["result"]]
        records.append(verify_record("mps_low", exp_low, float(actual_range[0]), unit="m/s"))
        records.append(verify_record("mps_high", exp_high, float(actual_range[1]), unit="m/s"))

    acc = _by_id(physics, "calc_piston_acceleration")
    if acc and acc.get("status") == "computed":
        rpm = float(acc["inputs"]["rpm"])
        s_low = float(acc["inputs"]["stroke_mm_low"]) / 1000.0
        s_high = float(acc["inputs"]["stroke_mm_high"]) / 1000.0
        ar = acc.get("value_range") or [acc["result"], acc["result"]]
        records.append(
            verify_record("accel_low", peak_piston_acceleration_m_s2(s_low, rpm), float(ar[0]), unit="m/s^2")
        )
        records.append(
            verify_record("accel_high", peak_piston_acceleration_m_s2(s_high, rpm), float(ar[1]), unit="m/s^2")
        )

    stress = _by_id(physics, "calc_rod_stress_requirement")
    if stress and stress.get("status") == "computed":
        inputs = stress.get("inputs") or {}
        load_low = float(inputs["load_low_n"])
        load_high = float(inputs["load_high_n"])
        sr = stress.get("value_range") or [stress["result"], stress["result"]]
        if "area_low_m2" in inputs and "area_high_m2" in inputs:
            # Legacy Phase-4 assumed-area identity path
            area_low = float(inputs["area_low_m2"])
            area_high = float(inputs["area_high_m2"])
            exp_low = rod_stress_mpa(load_low, area_high)
            exp_high = rod_stress_mpa(load_high, area_low)
            records.append(
                verify_record("rod_stress_low", exp_low, float(sr[0]), unit="MPa", pass_tol=0.5, warn_tol=2.0)
            )
            records.append(
                verify_record("rod_stress_high", exp_high, float(sr[1]), unit="MPa", pass_tol=0.5, warn_tol=2.0)
            )
        else:
            # Phase 5.0 ConnectingRodModel path — range extrema must be ordered and positive.
            records.append(
                {
                    "name": "rod_stress_geometry_model",
                    "expected": "geometry_aware_section",
                    "actual_range": sr,
                    "unit": "MPa",
                    "status": "pass" if float(sr[0]) > 0 and float(sr[1]) >= float(sr[0]) else "fail",
                    "note": (
                        "Absolute σ=F/A_assumed identity retired; "
                        "independent section checks live in tests/validation/test_rod_models.py"
                    ),
                    "rod_model": inputs.get("rod_model"),
                    "buckling_margin_min": inputs.get("buckling_margin_min"),
                    "fatigue_margin_min": inputs.get("fatigue_margin_min"),
                }
            )

    heat = _by_id(physics, "calc_heat_rejection")
    if heat and heat.get("status") == "computed":
        hp = float(heat["inputs"]["horsepower"])
        eta_l = float(heat["inputs"]["brake_thermal_efficiency_low"])
        eta_h = float(heat["inputs"]["brake_thermal_efficiency_high"])
        f_l = float(heat["inputs"]["coolant_heat_fraction_low"])
        f_h = float(heat["inputs"]["coolant_heat_fraction_high"])
        # extrema of product
        candidates = [heat_rejection_kw(hp, e, f) for e in (eta_l, eta_h) for f in (f_l, f_h)]
        hr = heat.get("value_range") or [heat["result"], heat["result"]]
        records.append(verify_record("heat_low", min(candidates), float(hr[0]), unit="kW", pass_tol=0.5, warn_tol=2.0))
        records.append(verify_record("heat_high", max(candidates), float(hr[1]), unit="kW", pass_tol=0.5, warn_tol=2.0))

    temp = _by_id(physics, "calc_combustion_side_temperature")
    if temp and temp.get("status") == "computed":
        q = float(temp["inputs"]["cooling_heat_rejection_kw"])
        expected = combustion_temp_empirical_c(q)
        records.append(
            verify_record(
                "combustion_temp_empirical_drift",
                expected,
                float(temp["result"]),
                unit="C",
                pass_tol=0.1,
            )
        )
        records.append(
            {
                "name": "combustion_temp_scientific_status",
                "status": "warn",
                "note": "Empirical map is UNVALIDATED against literature — formula drift check only.",
                "validation_status": "UNVALIDATED",
            }
        )

    stroke = _by_id(physics, "calc_stroke")
    disp = _by_id(physics, "calc_displacement")
    if stroke and disp and stroke.get("status") == "computed" and disp.get("status") == "computed":
        cyl = float(stroke["inputs"].get("cylinder_count") or 0)
        if cyl:
            # Spot-check mid displacement with mid ratio
            d_mid = float(disp["result"]) / 1000.0 / cyl  # m3 per cyl from litres mid
            ratio = (
                float(stroke["inputs"]["bore_stroke_ratio_low"])
                + float(stroke["inputs"]["bore_stroke_ratio_high"])
            ) / 2.0
            exp_mm = stroke_m_from_volume_ratio(d_mid, ratio) * 1000.0
            records.append(
                verify_record(
                    "stroke_mid_spotcheck",
                    exp_mm,
                    float(stroke["result"]),
                    unit="mm",
                    pass_tol=15.0,  # mid-of-range vs mid-of-ratios are not identical definitions
                    warn_tol=25.0,
                )
            )

    fails = [r for r in records if r.get("status") == "fail"]
    warns = [r for r in records if r.get("status") == "warn"]
    return {
        "records": records,
        "fail_count": len(fails),
        "warn_count": len(warns),
        "passed": len(fails) == 0,
    }


def validate_output_physics_file(path: Path | str = "output/physics_analysis.json") -> dict[str, Any]:
    path = Path(path)
    if not path.is_absolute():
        path = ROOT / path
    physics = json.loads(path.read_text())
    report = validate_physics_json(physics)
    report["source_file"] = str(path)
    return report
