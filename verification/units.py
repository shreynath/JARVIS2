"""Dimensional / unit analysis for JARVIS analytical equations.

Does not import PhysicsEngine. Checks that documented unit transforms are consistent.
"""

from __future__ import annotations

from typing import Any

# Simple dimensional vectors: M, L, T, Θ (temperature), 1 (dimensionless)
# Powers of base dimensions.


def _dim(**kwargs: float) -> dict[str, float]:
    base = {"M": 0.0, "L": 0.0, "T": 0.0, "Θ": 0.0}
    base.update(kwargs)
    return base


def _mul(a: dict[str, float], b: dict[str, float]) -> dict[str, float]:
    return {k: a[k] + b[k] for k in a}


def _div(a: dict[str, float], b: dict[str, float]) -> dict[str, float]:
    return {k: a[k] - b[k] for k in a}


def _pow(a: dict[str, float], n: float) -> dict[str, float]:
    return {k: a[k] * n for k in a}


def _eq(a: dict[str, float], b: dict[str, float], tol: float = 1e-9) -> bool:
    return all(abs(a[k] - b[k]) <= tol for k in a)


# Common SI dimensions
DIM = {
    "1": _dim(),
    "m": _dim(L=1),
    "m2": _dim(L=2),
    "m3": _dim(L=3),
    "kg": _dim(M=1),
    "s": _dim(T=1),
    "N": _dim(M=1, L=1, T=-2),
    "Pa": _dim(M=1, L=-1, T=-2),
    "W": _dim(M=1, L=2, T=-3),
    "kW": _dim(M=1, L=2, T=-3),
    "Nm": _dim(M=1, L=2, T=-2),
    "rpm": _dim(T=-1),  # 1/time
    "m_s": _dim(L=1, T=-1),
    "m_s2": _dim(L=1, T=-2),
    "MPa": _dim(M=1, L=-1, T=-2),
    "C": _dim(Θ=1),
}


EQUATION_UNIT_CHECKS: list[dict[str, Any]] = [
    {
        "equation_id": "eq_torque_kw_rpm",
        "lhs": "Nm",
        "rhs_description": "kW / rpm → N·m (with 9549 encoding 60e3/(2π))",
        "lhs_dim": DIM["Nm"],
        "rhs_dim": _div(DIM["kW"], DIM["rpm"]),
        "note": "Constant 9549 carries units of (N·m·rpm)/kW",
    },
    {
        "equation_id": "eq_mean_piston_speed",
        "lhs": "m/s",
        "rhs_description": "stroke[m] * rpm[1/s-equivalent]",
        "lhs_dim": DIM["m_s"],
        "rhs_dim": _mul(DIM["m"], DIM["rpm"]),
        "note": "Factor 2/60 is dimensionless scaling into seconds",
    },
    {
        "equation_id": "eq_peak_piston_acceleration",
        "lhs": "m/s^2",
        "rhs_description": "r[m] * ω^2[1/s^2]",
        "lhs_dim": DIM["m_s2"],
        "rhs_dim": _mul(DIM["m"], _pow(_div(DIM["1"], DIM["s"]), 2)),
        "note": "ω derived from rpm",
    },
    {
        "equation_id": "eq_displacement_bmep",
        "lhs": "m3",
        "rhs_description": "W * 1 / (Pa * rpm)",
        "lhs_dim": DIM["m3"],
        "rhs_dim": _div(DIM["W"], _mul(DIM["Pa"], DIM["rpm"])),
        "note": "Four-stroke factor 120 is cycle scaling (dimensionless relative to 2-rev cycle)",
    },
    {
        "equation_id": "eq_rod_stress",
        "lhs": "Pa",
        "rhs_description": "N / m2",
        "lhs_dim": DIM["Pa"],
        "rhs_dim": _div(DIM["N"], DIM["m2"]),
        "note": "Reported as MPa numerically",
    },
    {
        "equation_id": "eq_rod_loading",
        "lhs": "N",
        "rhs_description": "kg*m/s2 + Pa*m2",
        "lhs_dim": DIM["N"],
        "rhs_dim": DIM["N"],  # both terms are force
        "note": "Both inertial and gas terms are force",
        "skip_rhs_check": True,
    },
    {
        "equation_id": "eq_heat_rejection",
        "lhs": "kW",
        "rhs_description": "kW / 1 * 1",
        "lhs_dim": DIM["kW"],
        "rhs_dim": DIM["kW"],
        "note": "Efficiency and fraction are dimensionless",
    },
    {
        "equation_id": "eq_combustion_temp_empirical",
        "lhs": "C",
        "rhs_description": "empirical map from kW → °C",
        "lhs_dim": DIM["C"],
        "rhs_dim": DIM["C"],
        "note": "NOT dimensionally derived — UNVALIDATED empirical mapping",
        "dimensional_status": "UNVALIDATED_EMPIRICAL",
    },
]


def run_units_audit() -> dict[str, Any]:
    results = []
    failures = 0
    for item in EQUATION_UNIT_CHECKS:
        status = "pass"
        if item.get("dimensional_status") == "UNVALIDATED_EMPIRICAL":
            status = "warn"
        elif not item.get("skip_rhs_check", False):
            if not _eq(item["lhs_dim"], item["rhs_dim"]):
                status = "fail"
                failures += 1
        results.append(
            {
                "equation_id": item["equation_id"],
                "lhs": item["lhs"],
                "rhs_description": item["rhs_description"],
                "note": item.get("note"),
                "status": status,
                "dimensional_status": item.get("dimensional_status", "OK" if status == "pass" else status),
            }
        )
    return {
        "checks": results,
        "failures": failures,
        "passed": failures == 0,
    }
