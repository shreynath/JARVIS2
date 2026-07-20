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


def bore_mm_from_displacement_stroke(
    displacement_l: float,
    cylinder_count: float,
    stroke_mm: float,
) -> float:
    """Independent geometry: bore from swept volume identity."""
    if cylinder_count == 0 or stroke_mm == 0:
        raise ZeroDivisionError("cylinder_count and stroke must be nonzero")
    per_cyl_m3 = (displacement_l / 1000.0) / cylinder_count
    stroke_m = stroke_mm / 1000.0
    bore_m = math.sqrt(4.0 * per_cyl_m3 / (math.pi * stroke_m))
    return bore_m * 1000.0


def piston_area_m2(bore_mm: float) -> float:
    bore_m = bore_mm / 1000.0
    return math.pi * bore_m**2 / 4.0


def crank_radius_mm(stroke_mm: float) -> float:
    return stroke_mm / 2.0


def piston_shell_mass_kg(
    bore_mm: float,
    stroke_mm: float,
    *,
    density_kg_m3: float = 2700.0,
    crown_frac: float = 0.08,
    skirt_h_frac: float = 0.55,
    wall_frac: float = 0.04,
) -> float:
    """Independent reimplementation of ReciprocatingMassModel piston body mass."""
    bore_m = bore_mm / 1000.0
    stroke_m = stroke_mm / 1000.0
    crown_t = crown_frac * bore_m
    skirt_h = skirt_h_frac * stroke_m
    wall_t = wall_frac * bore_m
    crown_vol = math.pi * bore_m**2 / 4.0 * crown_t
    skirt_vol = math.pi * ((bore_m / 2.0) ** 2 - ((bore_m / 2.0) - wall_t) ** 2) * skirt_h
    return density_kg_m3 * (crown_vol + skirt_vol)


def euler_buckling_load_n(
    youngs_modulus_pa: float,
    second_moment_m4: float,
    length_m: float,
    *,
    k: float = 1.0,
) -> float:
    if length_m == 0:
        raise ZeroDivisionError("length must be nonzero")
    return (math.pi**2) * youngs_modulus_pa * second_moment_m4 / (k * length_m) ** 2


def i_beam_area_m2(
    *,
    web_thickness: float,
    depth: float,
    flange_width: float,
    flange_thickness: float,
) -> float:
    return web_thickness * (depth - 2 * flange_thickness) + 2 * flange_width * flange_thickness


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
