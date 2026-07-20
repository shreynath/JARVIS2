"""Independent formula reimplementations — MUST NOT import PhysicsEngine.

These verifiers recompute analytical identities from first principles / textbooks
so JARVIS outputs can be falsified without trusting the implementation.
"""

from __future__ import annotations

import math
from typing import Any

HP_TO_KW = 0.745699872
KW_TORQUE_CONSTANT = 9549.0  # = 60_000 / (2π) rounded common engineering constant
FTLB_PER_HP_RPM = 5252.0
NM_PER_FTLB = 1.3558179483314004


def torque_nm_from_hp_rpm(horsepower: float, rpm: float) -> float:
    """τ [N·m] from brake horsepower and RPM via SI path."""
    if rpm == 0:
        raise ZeroDivisionError("rpm must be nonzero")
    power_kw = horsepower * HP_TO_KW
    return power_kw * KW_TORQUE_CONSTANT / rpm


def torque_nm_from_english(horsepower: float, rpm: float) -> float:
    """Cross-check via English torque (lb·ft) then convert to N·m."""
    if rpm == 0:
        raise ZeroDivisionError("rpm must be nonzero")
    return (horsepower * FTLB_PER_HP_RPM / rpm) * NM_PER_FTLB


def displacement_l_from_bmep(
    horsepower: float,
    rpm: float,
    bmep_pa: float,
) -> float:
    """Four-stroke: V[m³] = P[W] * 120 / (BMEP[Pa] * N[rpm]); return litres."""
    if rpm == 0 or bmep_pa == 0:
        raise ZeroDivisionError("rpm and bmep must be nonzero")
    power_w = horsepower * HP_TO_KW * 1000.0
    displacement_m3 = power_w * 120.0 / (bmep_pa * rpm)
    return displacement_m3 * 1000.0


def stroke_m_from_volume_ratio(disp_per_cyl_m3: float, bore_stroke_ratio: float) -> float:
    """V = (π/4) * bore² * stroke with bore = λ * stroke → stroke = cbrt(4V/(π λ²))."""
    return (4.0 * disp_per_cyl_m3 / (math.pi * bore_stroke_ratio**2)) ** (1.0 / 3.0)


def mean_piston_speed_m_s(stroke_m: float, rpm: float) -> float:
    """Vp = 2 * S * N / 60."""
    return 2.0 * stroke_m * rpm / 60.0


def peak_piston_acceleration_m_s2(stroke_m: float, rpm: float) -> float:
    """a ≈ r ω² with r = S/2, ω = 2π N/60."""
    r = stroke_m / 2.0
    omega = 2.0 * math.pi * rpm / 60.0
    return r * omega**2


def rod_stress_mpa(load_n: float, area_m2: float) -> float:
    if area_m2 == 0:
        raise ZeroDivisionError("section area must be nonzero")
    return (load_n / area_m2) / 1e6


def heat_rejection_kw(horsepower: float, eta_th: float, cool_frac: float) -> float:
    if eta_th == 0:
        raise ZeroDivisionError("thermal efficiency must be nonzero")
    brake_kw = horsepower * HP_TO_KW
    return brake_kw / eta_th * cool_frac


def combustion_temp_empirical_c(cooling_heat_kw: float) -> float:
    """JARVIS empirical map — reimplemented only to detect drift, not to endorse."""
    return 180.0 + min(120.0, cooling_heat_kw / 8.0)


def percent_error(expected: float, actual: float) -> float:
    if expected == 0:
        return 0.0 if actual == 0 else float("inf")
    return abs(actual - expected) / abs(expected) * 100.0


def classify_error(pct: float, *, pass_tol: float = 0.1, warn_tol: float = 1.0) -> str:
    if pct <= pass_tol:
        return "pass"
    if pct <= warn_tol:
        return "warn"
    return "fail"


def verify_record(
    name: str,
    expected: float,
    actual: float,
    *,
    pass_tol: float = 0.1,
    warn_tol: float = 1.0,
    unit: str = "",
) -> dict[str, Any]:
    pct = percent_error(expected, actual)
    return {
        "name": name,
        "expected": expected,
        "actual": actual,
        "unit": unit,
        "percent_error": pct,
        "status": classify_error(pct, pass_tol=pass_tol, warn_tol=warn_tol),
        "pass_tol_pct": pass_tol,
        "warn_tol_pct": warn_tol,
    }
