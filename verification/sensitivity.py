"""Finite-difference sensitivity of independent analytical chain."""

from __future__ import annotations

from typing import Any

from verification.formulas import (
    mean_piston_speed_m_s,
    peak_piston_acceleration_m_s2,
    rod_stress_mpa,
    stroke_m_from_volume_ratio,
    torque_nm_from_hp_rpm,
)


def _chain(hp: float, rpm: float, bmep: float, ratio: float, cyl: float = 12.0) -> dict[str, float]:
    power_w = hp * 0.745699872 * 1000.0
    disp_l = power_w * 120.0 / (bmep * rpm) * 1000.0
    per_cyl = (disp_l / 1000.0) / cyl
    stroke = stroke_m_from_volume_ratio(per_cyl, ratio)
    mps = mean_piston_speed_m_s(stroke, rpm)
    acc = peak_piston_acceleration_m_s2(stroke, rpm)
    mass = max(0.2, (disp_l / cyl) * 1.1)
    bore_area = per_cyl / stroke
    load = mass * acc + bmep * 10.0 * bore_area
    stress = rod_stress_mpa(load, 4.5e-4)
    return {
        "torque_nm": torque_nm_from_hp_rpm(hp, rpm),
        "displacement_l": disp_l,
        "stroke_m": stroke,
        "mps": mps,
        "acceleration": acc,
        "rod_stress_mpa": stress,
    }


def run_sensitivity(
    *,
    base_hp: float = 800.0,
    base_rpm: float = 9000.0,
    base_bmep: float = 1.4e6,
    base_ratio: float = 1.1,
    perturbs: tuple[float, ...] = (0.01, 0.05, 0.10),
) -> dict[str, Any]:
    base = _chain(base_hp, base_rpm, base_bmep, base_ratio)
    inputs = {
        "horsepower": base_hp,
        "rpm": base_rpm,
        "bmep_pa": base_bmep,
        "bore_stroke_ratio": base_ratio,
    }
    matrix: dict[str, Any] = {}
    classifications: list[dict[str, Any]] = []

    for name, value in inputs.items():
        row: dict[str, Any] = {}
        for pct in perturbs:
            delta = value * pct
            kwargs = dict(inputs)
            kwargs[name] = value + delta
            # map keys to _chain args
            up = _chain(kwargs["horsepower"], kwargs["rpm"], kwargs["bmep_pa"], kwargs["bore_stroke_ratio"])
            kwargs[name] = value - delta
            down = _chain(kwargs["horsepower"], kwargs["rpm"], kwargs["bmep_pa"], kwargs["bore_stroke_ratio"])
            local = {}
            for out_name, b in base.items():
                # central difference relative sensitivity: (dy/y) / (dx/x)
                if b == 0 or value == 0:
                    sens = float("nan")
                else:
                    dy = (up[out_name] - down[out_name]) / 2.0
                    sens = (dy / abs(b)) / pct
                local[out_name] = {
                    "relative_sensitivity": sens,
                    "up": up[out_name],
                    "down": down[out_name],
                    "base": b,
                }
                # classify continuity for this step
                jump = abs(up[out_name] - down[out_name]) / max(abs(b), 1e-12)
                kind = "continuous"
                if jump > 50 * pct:  # abnormally large for linearish system
                    kind = "unstable"
                if any(not math_isfinite(v) for v in (up[out_name], down[out_name], b)):
                    kind = "nonphysical"
                classifications.append(
                    {
                        "input": name,
                        "perturb_pct": pct * 100,
                        "output": out_name,
                        "classification": kind,
                        "relative_jump": jump,
                    }
                )
            row[f"±{int(pct*100)}%"] = local
        matrix[name] = row

    # Identify dominant uncertainty drivers for rod stress at ±10%
    drivers = []
    for name in inputs:
        cell = matrix[name]["±10%"]["rod_stress_mpa"]
        drivers.append({"input": name, "abs_relative_sensitivity": abs(cell["relative_sensitivity"])})
    drivers.sort(key=lambda d: d["abs_relative_sensitivity"], reverse=True)

    return {
        "base": base,
        "inputs": inputs,
        "sensitivity_matrix": matrix,
        "classifications": classifications,
        "dominant_rod_stress_drivers_at_10pct": drivers,
        "note": (
            "Independent analytical chain (not PhysicsEngine). "
            "Relative sensitivity ≈ (%Δoutput) / (%Δinput) via central differences."
        ),
    }


def math_isfinite(x: float) -> bool:
    return x == x and abs(x) != float("inf")
