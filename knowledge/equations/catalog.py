"""Equation provenance registry — shared by PhysicsEngine (emit) and independent verifiers.

Honesty rule: if a formula lacks an external engineering reference, mark
``validation_status`` as UNVALIDATED rather than inventing citations.
"""

from __future__ import annotations

from typing import Any

# Canonical equation records. References are textbook/standard identities where
# applicable; empirical / order-of-magnitude mappings stay UNVALIDATED.
EQUATION_CATALOG: dict[str, dict[str, Any]] = {
    "eq_torque_kw_rpm": {
        "equation_id": "eq_torque_kw_rpm",
        "name": "Rotational power–torque relationship",
        "equation": "torque_nm = power_kw * 9549 / rpm",
        "equivalent": "torque_nm = horsepower * 5252 / rpm * 1.3558179483314",
        "equation_source": "SI mechanical power identity (P = τω)",
        "engineering_reference": {
            "citation": "Standard rotational dynamics; SI conversion HP→kW = 0.745699872",
            "text": None,
            "edition": None,
            "chapter": None,
            "page": None,
        },
        "validation_status": "INDEPENDENTLY_VERIFIED",
        "unit_check": "kW * 1 / (1/min) → N·m",
        "confidence": "high",
    },
    "eq_displacement_bmep": {
        "equation_id": "eq_displacement_bmep",
        "name": "Four-stroke BMEP power relation",
        "equation": "displacement_m3 = brake_power_w * 120 / (bmep_pa * rpm)",
        "equation_source": "Four-stroke indicated/brake mean effective pressure identity",
        "engineering_reference": {
            "citation": "Heywood, Internal Combustion Engine Fundamentals — BMEP/power relation",
            "text": "Internal Combustion Engine Fundamentals",
            "author": "John B. Heywood",
            "edition": "1st/standard ICE reference",
            "chapter": "Performance",
            "page": None,
            "note": "Page not pinned in this repo; identity is standard. BMEP numeric bands are ASSUMED.",
        },
        "validation_status": "FORMULA_VERIFIED_PARAMETERS_ASSUMED",
        "unit_check": "W * 1 / (Pa * 1/min) → m³",
        "confidence": "medium",
    },
    "eq_stroke_geometry": {
        "equation_id": "eq_stroke_geometry",
        "name": "Stroke from swept volume and bore/stroke ratio",
        "equation": "stroke = cbrt(4 * V_cyl / (π * λ²)) where λ = bore/stroke",
        "equation_source": "Cylinder geometry identity",
        "engineering_reference": {
            "citation": "Elementary swept-volume geometry",
            "text": None,
            "edition": None,
            "chapter": None,
            "page": None,
            "note": "Bore/stroke ratio range is ASSUMED engineering band, not measured.",
        },
        "validation_status": "FORMULA_VERIFIED_PARAMETERS_ASSUMED",
        "unit_check": "m³ → m",
        "confidence": "medium",
    },
    "eq_mean_piston_speed": {
        "equation_id": "eq_mean_piston_speed",
        "name": "Mean piston speed",
        "equation": "Vp = 2 * stroke * RPM / 60",
        "equation_source": "Kinematic definition of mean piston speed",
        "engineering_reference": {
            "citation": "Heywood, Internal Combustion Engine Fundamentals — mean piston speed",
            "text": "Internal Combustion Engine Fundamentals",
            "author": "John B. Heywood",
            "edition": "standard ICE reference",
            "chapter": "Engine performance / geometry",
            "page": None,
        },
        "validation_status": "INDEPENDENTLY_VERIFIED",
        "unit_check": "m * (1/min) → m/s",
        "confidence": "high",
    },
    "eq_peak_piston_acceleration": {
        "equation_id": "eq_peak_piston_acceleration",
        "name": "First-order peak piston acceleration",
        "equation": "a_peak ≈ r * ω²  (r = stroke/2, ω = 2πn)",
        "equation_source": "Slider-crank kinematics, first harmonic / primary term",
        "engineering_reference": {
            "citation": "Standard slider-crank kinematics; secondary (λ) terms omitted",
            "text": None,
            "edition": None,
            "chapter": None,
            "page": None,
            "note": "Approximate — rod-ratio secondary acceleration not modeled.",
        },
        "validation_status": "FORMULA_VERIFIED_MODEL_APPROXIMATE",
        "unit_check": "m * (rad/s)² → m/s²",
        "confidence": "medium",
    },
    "eq_rod_loading": {
        "equation_id": "eq_rod_loading",
        "name": "Connecting-rod load estimate",
        "equation": "F ≈ m_piston * a + p_peak * A_bore",
        "equation_source": "Order-of-magnitude inertia + gas load combination",
        "engineering_reference": {
            "citation": None,
            "text": None,
            "note": "Piston mass and peak-pressure factors are ASSUMED ranges — not FEA.",
        },
        "validation_status": "UNVALIDATED",
        "unit_check": "kg·m/s² + Pa·m² → N",
        "confidence": "low",
    },
    "eq_rod_stress": {
        "equation_id": "eq_rod_stress",
        "name": "Rod stress requirement",
        "equation": "σ = F / A_section",
        "equation_source": "Elementary continuum mechanics",
        "engineering_reference": {
            "citation": "σ = F/A identity",
            "note": "Section area is an ASSUMED band, not a designed section.",
        },
        "validation_status": "FORMULA_VERIFIED_PARAMETERS_ASSUMED",
        "unit_check": "N / m² → Pa (reported as MPa)",
        "confidence": "low",
    },
    "eq_heat_rejection": {
        "equation_id": "eq_heat_rejection",
        "name": "Coolant heat rejection estimate",
        "equation": "Q_cool ≈ P_brake / η_th * f_cool",
        "equation_source": "Energy-split order-of-magnitude model",
        "engineering_reference": {
            "citation": None,
            "note": "η_th and coolant fraction are ASSUMED bands — not measured BSFC maps.",
        },
        "validation_status": "UNVALIDATED",
        "unit_check": "kW / 1 * 1 → kW",
        "confidence": "low",
    },
    "eq_combustion_temp_empirical": {
        "equation_id": "eq_combustion_temp_empirical",
        "name": "Empirical combustion-side temperature map",
        "equation": "T ≈ 180 + min(120, Q_cool_kw / 8)",
        "equation_source": "Internal empirical mapping (not CFD)",
        "engineering_reference": {
            "citation": None,
            "note": "No peer-reviewed source for this exact mapping — UNVALIDATED.",
        },
        "validation_status": "UNVALIDATED",
        "unit_check": "empirical °C mapping — not dimensionally derived from first principles",
        "confidence": "low",
    },
    "eq_bridge_deck_moment": {
        "equation_id": "eq_bridge_deck_moment",
        "name": "Simply-supported beam maximum moment",
        "equation": "M_max = w * L^2 / 8",
        "equation_source": "Elementary beam theory — simply supported UDL",
        "engineering_reference": {
            "citation": "Hibbeler, Structural Analysis — beam internal moment diagram",
            "text": "Structural Analysis",
            "author": "R. C. Hibbeler",
            "edition": "standard structural analysis text",
            "chapter": "Internal forces in beams",
            "page": None,
            "note": "Live load w is ASSUMED when not specified in prompt.",
        },
        "validation_status": "FORMULA_VERIFIED_PARAMETERS_ASSUMED",
        "unit_check": "(N/m) * m² → N·m",
        "confidence": "medium",
    },
    "eq_truss_member_stress": {
        "equation_id": "eq_truss_member_stress",
        "name": "Truss member axial stress",
        "equation": "sigma = F_member / A_member; F_member ≈ M_max / truss_depth",
        "equation_source": "Truss analogy from equivalent beam moment",
        "engineering_reference": {
            "citation": "Hibbeler, Structural Analysis — truss internal forces",
            "text": "Structural Analysis",
            "author": "R. C. Hibbeler",
            "edition": "standard structural analysis text",
            "chapter": "Truss analysis",
            "page": None,
            "note": "Member area and live load may be ASSUMED bands.",
        },
        "validation_status": "FORMULA_VERIFIED_PARAMETERS_ASSUMED",
        "unit_check": "N / m² → Pa",
        "confidence": "medium",
    },
    "eq_oil_flow": {
        "equation_id": "eq_oil_flow",
        "name": "Oil flow",
        "equation": None,
        "equation_source": None,
        "engineering_reference": {"citation": None, "note": "Not implemented in PhysicsEngine."},
        "validation_status": "OUT_OF_MODEL",
        "confidence": "unknown",
    },
}

# Physics calculation id → equation_id
CALC_TO_EQUATION: dict[str, str] = {
    "calc_torque": "eq_torque_kw_rpm",
    "calc_displacement": "eq_displacement_bmep",
    "calc_stroke": "eq_stroke_geometry",
    "calc_mean_piston_speed": "eq_mean_piston_speed",
    "calc_piston_acceleration": "eq_peak_piston_acceleration",
    "calc_rod_loading": "eq_rod_loading",
    "calc_rod_stress_requirement": "eq_rod_stress",
    "calc_heat_rejection": "eq_heat_rejection",
    "calc_combustion_side_temperature": "eq_combustion_temp_empirical",
    "calc_bridge_deck_moment": "eq_bridge_deck_moment",
    "calc_truss_member_stress": "eq_truss_member_stress",
}


def provenance_for_calc(calc_id: str) -> dict[str, Any]:
    eq_id = CALC_TO_EQUATION.get(calc_id)
    if not eq_id or eq_id not in EQUATION_CATALOG:
        return {
            "equation_id": None,
            "equation_source": None,
            "engineering_reference": None,
            "validation_status": "UNVALIDATED",
        }
    rec = EQUATION_CATALOG[eq_id]
    return {
        "equation_id": rec["equation_id"],
        "equation_source": rec["equation_source"],
        "engineering_reference": rec["engineering_reference"],
        "validation_status": rec["validation_status"],
    }
