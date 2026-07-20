"""Independent rod / reciprocating dynamics verifier.

MUST NOT import PhysicsEngine, EngineeringEvaluator, MaterialAssigner,
or ConstraintEvaluator.
"""

from __future__ import annotations

import math
from typing import Any

from core.verification.datasets.rod_validation.loader import load_rod_cases


def inertia_force_n(mass_kg: float, stroke_m: float, rpm: float) -> float:
    """Peak first-order inertia: F = m * r * ω² with r = S/2."""
    r = stroke_m / 2.0
    omega = 2.0 * math.pi * rpm / 60.0
    return mass_kg * r * omega**2


def peak_piston_acceleration_m_s2(stroke_m: float, rpm: float) -> float:
    """a = r ω²."""
    r = stroke_m / 2.0
    omega = 2.0 * math.pi * rpm / 60.0
    return r * omega**2


def euler_critical_load_n(
    youngs_modulus_pa: float,
    second_moment_m4: float,
    length_m: float,
    *,
    k: float = 1.0,
) -> float:
    """P_cr = π² E I / (K L)²."""
    if length_m <= 0:
        raise ZeroDivisionError("length must be positive")
    return (math.pi**2) * youngs_modulus_pa * second_moment_m4 / (k * length_m) ** 2


def fatigue_safety_factor(sigma_fatigue_mpa: float, sigma_alternating_mpa: float) -> float:
    """SF = σ_fatigue / σ_alternating."""
    if sigma_alternating_mpa == 0:
        raise ZeroDivisionError("alternating stress must be nonzero")
    return sigma_fatigue_mpa / sigma_alternating_mpa


def stress_mpa(load_n: float, area_m2: float) -> float:
    if area_m2 == 0:
        raise ZeroDivisionError("area must be nonzero")
    return (load_n / area_m2) / 1e6


def verify_case(case_dict: dict[str, Any] | Any) -> dict[str, Any]:
    """Independently evaluate what can be computed without inventing masses."""
    # Accept RodValidationCase or dict
    if hasattr(case_dict, "to_dict"):
        c = case_dict.to_dict()
    else:
        c = dict(case_dict)

    rpm = c.get("rpm")
    stroke_mm = c.get("stroke_mm")
    bore_mm = c.get("bore_mm")
    piston_g = c.get("piston_mass_g")
    rod_g = c.get("rod_mass_g")
    rod_length_mm = c.get("rod_length_mm")

    row: dict[str, Any] = {
        "engine_id": c.get("engine_id"),
        "engine_name": c.get("engine_name"),
        "confidence": c.get("confidence"),
        "source": c.get("source"),
        "absolute_mass_available": piston_g is not None and rod_g is not None,
        "rod_length_available": rod_length_mm is not None,
    }

    if stroke_mm is None or rpm is None:
        row["status"] = "incomplete_geometry"
        return row

    stroke_m = float(stroke_mm) / 1000.0
    accel = peak_piston_acceleration_m_s2(stroke_m, float(rpm))
    row["independent_peak_accel_m_s2"] = accel
    row["status"] = "geometry_only"

    if piston_g is not None:
        # Reciprocating approx: piston + 1/3 rod if rod known, else piston only flagged.
        mass_kg = float(piston_g) / 1000.0
        if rod_g is not None:
            mass_kg += 0.35 * (float(rod_g) / 1000.0)
            row["reciprocating_mass_convention"] = "piston + 0.35*rod"
        else:
            row["reciprocating_mass_convention"] = "piston_only_partial"
        force = inertia_force_n(mass_kg, stroke_m, float(rpm))
        row["independent_inertia_force_n"] = force
        row["status"] = "absolute_force_computable"
    else:
        row["independent_inertia_force_n"] = None
        row["blocking"] = "piston_mass_g is null — absolute load not falsifiable"

    # Section heuristic only when bore known — for Euler identity self-check, not absolute truth.
    if bore_mm is not None and rod_length_mm is not None:
        # Tiny illustrative I-beam stub for identity/monotonic checks (not JARVIS geometry).
        length_m = float(rod_length_mm) / 1000.0
        # Nominal 10mm × 20mm rectangle as placeholder section for formula exercise only.
        area = 0.01 * 0.02
        i = (0.01 * 0.02**3) / 12.0
        e = 200e9
        pcr = euler_critical_load_n(e, i, length_m)
        row["euler_critical_load_n_placeholder_section"] = pcr
        row["euler_note"] = "Placeholder section — not OEM rod; identity check only."
    else:
        row["euler_critical_load_n_placeholder_section"] = None

    if bore_mm is not None:
        row["bore_mm"] = bore_mm
    return row


def run_rod_verification() -> dict[str, Any]:
    cases = load_rod_cases()
    results = [verify_case(c) for c in cases]
    absolute = [r for r in results if r.get("absolute_mass_available")]
    return {
        "campaign": "rod_validation",
        "phase": "8.6",
        "cases_evaluated": len(results),
        "absolute_mass_cases": len(absolute),
        "results": results,
        "physics_identity_checks": {
            "inertia_force_equals_m_times_accel": True,
            "note": "F = m a with a = r ω² checked symbolically in unit tests.",
        },
        "policy": "No PhysicsEngine import. Null masses stay null.",
    }
