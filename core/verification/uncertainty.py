"""Uncertainty propagation — Monte Carlo over assumption bands (no optimization)."""

from __future__ import annotations

import math
import random
from typing import Any

from core.engineering.engine_cycle_model import EngineCycleModel
from verification.formulas import (
    mean_piston_speed_m_s,
    peak_piston_acceleration_m_s2,
    stroke_m_from_volume_ratio,
    torque_nm_from_hp_rpm,
)
from verification.monte_carlo import run_monte_carlo as _legacy_run_monte_carlo


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
        return {
            "mean": float("nan"),
            "sigma": float("nan"),
            "p05": float("nan"),
            "p95": float("nan"),
            "min": float("nan"),
            "max": float("nan"),
            "n": 0.0,
        }
    s = sorted(samples)
    mean = sum(s) / len(s)
    var = sum((x - mean) ** 2 for x in s) / len(s)
    return {
        "mean": mean,
        "sigma": math.sqrt(var),
        "p05": _percentile(s, 5),
        "p95": _percentile(s, 95),
        "min": s[0],
        "max": s[-1],
        "n": float(len(s)),
    }


def propagate_bmep_uncertainty(
    *,
    horsepower: float = 800.0,
    rpm: float = 9000.0,
    cylinder_count: float = 12.0,
    aspiration: str = "Naturally aspirated",
    n_samples: int = 2000,
    seed: int = 7,
    yield_mpa_gate: float = 700.0,
) -> dict[str, Any]:
    """If BMEP varies within the cycle band, how do stroke / MPS / stress disperse?"""
    rng = random.Random(seed)
    bmep_low, bmep_high = EngineCycleModel().bmep_range_pa(aspiration)
    power_w = horsepower * 0.745699872 * 1000.0

    strokes_mm: list[float] = []
    mps: list[float] = []
    rod_stress: list[float] = []
    material_survive = 0

    for _ in range(n_samples):
        bmep = rng.uniform(bmep_low, bmep_high)
        disp_l = power_w * 120.0 / (bmep * rpm) * 1000.0
        per_cyl = disp_l / 1000.0 / cylinder_count
        ratio = rng.uniform(1.0, 1.25)
        stroke_m = stroke_m_from_volume_ratio(per_cyl, ratio)
        stroke_mm = stroke_m * 1000.0
        strokes_mm.append(stroke_mm)
        vp = mean_piston_speed_m_s(stroke_m, rpm)
        mps.append(vp)
        accel = peak_piston_acceleration_m_s2(stroke_m, rpm)
        # Rough stress proxy: mass ~ 1.1 kg/L * per_cyl_L, area ~ mid rod section
        mass = max(0.2, (disp_l / cylinder_count) * 1.1)
        load = mass * accel + bmep * 10.0 * (per_cyl / stroke_m)
        stress = (load / 4.5e-4) / 1e6
        rod_stress.append(stress)
        if stress * 1.25 <= yield_mpa_gate:
            material_survive += 1

    # Physics relationship check samples for monotonic RPM→MPS at fixed stroke
    fixed_stroke = 0.08
    mps_low_rpm = mean_piston_speed_m_s(fixed_stroke, rpm * 0.9)
    mps_high_rpm = mean_piston_speed_m_s(fixed_stroke, rpm * 1.1)

    return {
        "phase": "7.0",
        "inputs": {
            "horsepower": horsepower,
            "rpm": rpm,
            "cylinder_count": cylinder_count,
            "aspiration": aspiration,
            "bmep_pa": (bmep_low, bmep_high),
            "n_samples": n_samples,
        },
        "distributions": {
            "stroke_mm": _summary(strokes_mm),
            "mean_piston_speed_m_s": _summary(mps),
            "rod_stress_proxy_mpa": _summary(rod_stress),
        },
        "material_survival_probability": material_survive / n_samples,
        "yield_mpa_gate": yield_mpa_gate,
        "physics_relationship_checks": {
            "higher_rpm_raises_mps_at_fixed_stroke": mps_high_rpm > mps_low_rpm,
            "mps_at_0_9x_rpm": mps_low_rpm,
            "mps_at_1_1x_rpm": mps_high_rpm,
        },
        "policy": "Uncertainty only — no optimization or candidate selection.",
        "legacy_monte_carlo": "verification.monte_carlo.run_monte_carlo",
    }


def run_uncertainty_analysis(**kwargs: Any) -> dict[str, Any]:
    """Facade combining Phase 7 BMEP propagation + legacy monte carlo summary."""
    prop = propagate_bmep_uncertainty(**{
        k: kwargs[k]
        for k in (
            "horsepower",
            "rpm",
            "cylinder_count",
            "aspiration",
            "n_samples",
            "seed",
            "yield_mpa_gate",
        )
        if k in kwargs
    })
    legacy = _legacy_run_monte_carlo(
        horsepower=kwargs.get("horsepower", 800.0),
        rpm=kwargs.get("rpm", 9000.0),
        cylinder_count=kwargs.get("cylinder_count", 12.0),
        n_samples=int(kwargs.get("n_samples", 2000)),
        seed=int(kwargs.get("seed", 7)),
    )
    return {"bmep_propagation": prop, "legacy_monte_carlo": legacy}
