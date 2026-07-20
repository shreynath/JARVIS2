"""Monte Carlo uncertainty propagation over assumed input bands (JSON-driven)."""

from __future__ import annotations

import math
import random
from typing import Any

from verification.formulas import (
    heat_rejection_kw,
    mean_piston_speed_m_s,
    peak_piston_acceleration_m_s2,
    rod_stress_mpa,
    stroke_m_from_volume_ratio,
    torque_nm_from_hp_rpm,
)


def _percentile(sorted_vals: list[float], p: float) -> float:
    if not sorted_vals:
        return float("nan")
    k = (len(sorted_vals) - 1) * p / 100.0
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_vals[int(k)]
    return sorted_vals[f] * (c - k) + sorted_vals[c] * (k - f)


def _summary(samples: list[float]) -> dict[str, float]:
    if not samples:
        return {"mean": float("nan"), "sigma": float("nan"), "p95_low": float("nan"), "p95_high": float("nan"), "p99_low": float("nan"), "p99_high": float("nan")}
    s = sorted(samples)
    mean = sum(s) / len(s)
    var = sum((x - mean) ** 2 for x in s) / len(s)
    return {
        "mean": mean,
        "sigma": math.sqrt(var),
        "p95_low": _percentile(s, 2.5),
        "p95_high": _percentile(s, 97.5),
        "p99_low": _percentile(s, 0.5),
        "p99_high": _percentile(s, 99.5),
        "min": s[0],
        "max": s[-1],
        "n": float(len(s)),
    }


def run_monte_carlo(
    *,
    horsepower: float = 800.0,
    rpm: float = 9000.0,
    cylinder_count: float = 12.0,
    bmep_low_pa: float = 1.2e6,
    bmep_high_pa: float = 1.6e6,
    bore_stroke_low: float = 1.0,
    bore_stroke_high: float = 1.25,
    mass_factor_low: float = 0.9,
    mass_factor_high: float = 1.3,
    pressure_factor_low: float = 8.0,
    pressure_factor_high: float = 12.0,
    area_low: float = 3.5e-4,
    area_high: float = 5.5e-4,
    eta_low: float = 0.28,
    eta_high: float = 0.34,
    cool_low: float = 0.25,
    cool_high: float = 0.35,
    n_samples: int = 1000,
    seed: int = 42,
) -> dict[str, Any]:
    rng = random.Random(seed)
    torque_s: list[float] = []
    mps_s: list[float] = []
    acc_s: list[float] = []
    stress_s: list[float] = []
    heat_s: list[float] = []

    for _ in range(n_samples):
        bmep = rng.uniform(bmep_low_pa, bmep_high_pa)
        # V[L] = P_w * 120 / (bmep * rpm) * 1000
        power_w = horsepower * 0.745699872 * 1000.0
        disp_l = power_w * 120.0 / (bmep * rpm) * 1000.0
        ratio = rng.uniform(bore_stroke_low, bore_stroke_high)
        per_cyl_m3 = (disp_l / 1000.0) / cylinder_count
        stroke_m = stroke_m_from_volume_ratio(per_cyl_m3, ratio)
        mps = mean_piston_speed_m_s(stroke_m, rpm)
        acc = peak_piston_acceleration_m_s2(stroke_m, rpm)
        mass = max(0.2, (disp_l / cylinder_count) * rng.uniform(mass_factor_low, mass_factor_high))
        bore_area = per_cyl_m3 / stroke_m
        gas = bmep * rng.uniform(pressure_factor_low, pressure_factor_high) * bore_area
        load = mass * acc + gas
        area = rng.uniform(area_low, area_high)
        stress = rod_stress_mpa(load, area)
        heat = heat_rejection_kw(horsepower, rng.uniform(eta_low, eta_high), rng.uniform(cool_low, cool_high))

        torque_s.append(torque_nm_from_hp_rpm(horsepower, rpm))
        mps_s.append(mps)
        acc_s.append(acc)
        stress_s.append(stress)
        heat_s.append(heat)

    return {
        "n_samples": n_samples,
        "seed": seed,
        "fixed_inputs": {"horsepower": horsepower, "rpm": rpm, "cylinder_count": cylinder_count},
        "distributions": {
            "torque_nm": _summary(torque_s),
            "mean_piston_speed_m_s": _summary(mps_s),
            "peak_acceleration_m_s2": _summary(acc_s),
            "rod_stress_mpa": _summary(stress_s),
            "cooling_heat_kw": _summary(heat_s),
        },
        "note": (
            "Samples assumed input bands (BMEP, bore/stroke, masses, areas, efficiencies). "
            "This quantifies assumption-driven uncertainty, not measurement error."
        ),
    }
