"""Registry of every engineering model JARVIS currently exposes.

Honesty rules:
- Maturity reflects model sophistication, not run confidence.
- M4/M5 claims must satisfy evidence gates in validate_descriptor.
- Phase 5.0 upgrades remaining M1 mass heuristics → M2 geometry estimates;
  rod stress remains M3 until published load benchmarks exist (reported honestly).
"""

from __future__ import annotations

from typing import Any

from knowledge.equations.catalog import CALC_TO_EQUATION, EQUATION_CATALOG
from core.verification.model_impact import ImpactLevel
from core.verification.model_maturity import (
    ModelDescriptor,
    ModelMaturity,
    make_descriptor,
    validate_descriptor,
)

# Calculation IDs that PhysicsEngine always emits (computed or skipped).
ENGINEERING_CALCULATION_IDS: frozenset[str] = frozenset(CALC_TO_EQUATION.keys())


def _ref_citation(equation_id: str | None) -> str | None:
    if not equation_id:
        return None
    rec = EQUATION_CATALOG.get(equation_id) or {}
    eng = rec.get("engineering_reference") or {}
    return eng.get("citation") or eng.get("note")


def _status(equation_id: str | None) -> str | None:
    if not equation_id:
        return None
    return (EQUATION_CATALOG.get(equation_id) or {}).get("validation_status")


_PHYSICS: list[ModelDescriptor] = [
    make_descriptor(
        id="calc_torque",
        maturity=ModelMaturity.M2,
        owner="PhysicsEngine",
        equation_id="eq_torque_kw_rpm",
        engineering_reference=_ref_citation("eq_torque_kw_rpm"),
        validation_status=_status("eq_torque_kw_rpm"),
        benchmarked=True,
        independently_verified=True,
        known_limitations="Identity only — does not model friction or accessory loads.",
        impact_level=ImpactLevel.HIGH,
        affected_outputs=("operating_conditions", "validation"),
        sensitivity_rank=20,
        upgrade_priority="MEDIUM",
        subsystem="physics",
    ),
    make_descriptor(
        id="calc_displacement",
        maturity=ModelMaturity.M3,
        owner="PhysicsEngine",
        equation_id="eq_displacement_bmep",
        engineering_reference=_ref_citation("eq_displacement_bmep"),
        validation_status=_status("eq_displacement_bmep"),
        known_limitations="Analytical BMEP identity with ASSUMED NA/boosted BMEP bands.",
        impact_level=ImpactLevel.HIGH,
        affected_outputs=("stroke", "rod_loading", "mean_piston_speed", "material_selection"),
        sensitivity_rank=15,
        upgrade_priority="HIGH",
        subsystem="physics",
    ),
    make_descriptor(
        id="calc_stroke",
        maturity=ModelMaturity.M2,
        owner="PhysicsEngine",
        equation_id="eq_stroke_geometry",
        engineering_reference=_ref_citation("eq_stroke_geometry"),
        validation_status=_status("eq_stroke_geometry"),
        independently_verified=True,
        known_limitations="Geometry identity; bore/stroke ratio band is ASSUMED when stroke unknown.",
        impact_level=ImpactLevel.MEDIUM,
        affected_outputs=("mean_piston_speed", "piston_acceleration", "rod_loading", "geometry"),
        sensitivity_rank=18,
        upgrade_priority="MEDIUM",
        subsystem="physics",
    ),
    make_descriptor(
        id="calc_mean_piston_speed",
        maturity=ModelMaturity.M2,
        owner="PhysicsEngine",
        equation_id="eq_mean_piston_speed",
        engineering_reference=_ref_citation("eq_mean_piston_speed"),
        validation_status=_status("eq_mean_piston_speed"),
        benchmarked=True,
        independently_verified=True,
        known_limitations="Kinematic definition only; hard limit 26 m/s is an engineering standard, not a physics law.",
        impact_level=ImpactLevel.CRITICAL,
        affected_outputs=("validation", "constraint_evaluation"),
        sensitivity_rank=5,
        upgrade_priority="HIGH",
        subsystem="physics",
    ),
    make_descriptor(
        id="calc_piston_acceleration",
        maturity=ModelMaturity.M2,
        owner="PhysicsEngine",
        equation_id="eq_peak_piston_acceleration",
        engineering_reference=_ref_citation("eq_peak_piston_acceleration"),
        validation_status=_status("eq_peak_piston_acceleration"),
        independently_verified=True,
        known_limitations="First-harmonic approximation; rod-ratio secondary term omitted.",
        impact_level=ImpactLevel.HIGH,
        affected_outputs=("rod_loading", "rod_stress"),
        sensitivity_rank=12,
        upgrade_priority="HIGH",
        subsystem="physics",
    ),
    make_descriptor(
        id="calc_rod_loading",
        maturity=ModelMaturity.M3,
        owner="PhysicsEngine",
        equation_id="eq_rod_loading",
        engineering_reference=_ref_citation("eq_rod_loading"),
        validation_status=_status("eq_rod_loading"),
        independently_verified=True,
        known_limitations=(
            "Phase 5.0 uses geometry-derived reciprocating mass + gas load. "
            "M4 withheld: published rod-load benchmarks unavailable for absolute error bounds."
        ),
        impact_level=ImpactLevel.CRITICAL,
        affected_outputs=("rod_stress", "material_selection", "validation"),
        sensitivity_rank=3,
        upgrade_priority="VERY_HIGH",
        subsystem="physics",
    ),
    make_descriptor(
        id="calc_rod_stress_requirement",
        maturity=ModelMaturity.M3,
        owner="PhysicsEngine",
        equation_id="eq_rod_stress",
        engineering_reference=_ref_citation("eq_rod_stress"),
        validation_status=_status("eq_rod_stress"),
        independently_verified=True,
        known_limitations=(
            "Phase 5.0 uses ConnectingRodModel I/H-beam section + Euler buckling. "
            "M4 withheld: no published measured rod stress datasets for absolute validation."
        ),
        impact_level=ImpactLevel.CRITICAL,
        affected_outputs=("material_selection", "validation", "constraints"),
        sensitivity_rank=2,
        upgrade_priority="VERY_HIGH",
        subsystem="physics",
    ),
    make_descriptor(
        id="calc_heat_rejection",
        maturity=ModelMaturity.M3,
        owner="PhysicsEngine",
        equation_id="eq_heat_rejection",
        engineering_reference=_ref_citation("eq_heat_rejection"),
        validation_status=_status("eq_heat_rejection"),
        known_limitations="Energy-split estimate; η_th and coolant fraction ASSUMED — not BSFC maps.",
        impact_level=ImpactLevel.HIGH,
        affected_outputs=("combustion_temperature", "material_selection"),
        sensitivity_rank=25,
        upgrade_priority="HIGH",
        subsystem="physics",
    ),
    make_descriptor(
        id="calc_combustion_side_temperature",
        maturity=ModelMaturity.M3,
        owner="PhysicsEngine",
        equation_id="eq_combustion_temp_empirical",
        engineering_reference=_ref_citation("eq_combustion_temp_empirical"),
        validation_status=_status("eq_combustion_temp_empirical"),
        known_limitations="Internal empirical T≈180+min(120,Q/8) mapping — no peer-reviewed source.",
        impact_level=ImpactLevel.HIGH,
        affected_outputs=("material_selection", "constraints"),
        sensitivity_rank=22,
        upgrade_priority="HIGH",
        subsystem="physics",
    ),
]

_PLACEHOLDERS: list[ModelDescriptor] = [
    make_descriptor(
        id="eq_oil_flow",
        maturity=ModelMaturity.M0,
        owner="PhysicsEngine",
        equation_id="eq_oil_flow",
        engineering_reference=_ref_citation("eq_oil_flow"),
        validation_status=_status("eq_oil_flow"),
        known_limitations="Not implemented — OUT_OF_MODEL.",
        impact_level=ImpactLevel.MEDIUM,
        affected_outputs=("lubrication",),
        sensitivity_rank=80,
        upgrade_priority="MEDIUM",
        subsystem="lubrication",
    ),
    make_descriptor(
        id="packaging",
        maturity=ModelMaturity.M0,
        owner="CandidateDesign",
        validation_status="OUT_OF_MODEL",
        known_limitations="No packaging geometry or spatial packing model exists.",
        impact_level=ImpactLevel.MEDIUM,
        affected_outputs=("candidate_feasibility",),
        sensitivity_rank=70,
        upgrade_priority="MEDIUM",
        subsystem="packaging",
    ),
    make_descriptor(
        id="manufacturing_cost",
        maturity=ModelMaturity.M0,
        owner="CandidateDesign",
        validation_status="OUT_OF_MODEL",
        known_limitations="No cost model — OUT_OF_MODEL parameter role.",
        impact_level=ImpactLevel.LOW,
        affected_outputs=("cost",),
        sensitivity_rank=90,
        upgrade_priority="LOW",
        subsystem="cost",
    ),
]

_ENGINEERING: list[ModelDescriptor] = [
    make_descriptor(
        id="geometry_model",
        maturity=ModelMaturity.M2,
        owner="GeometryModel",
        engineering_reference="Swept-volume / crank geometry identities",
        validation_status="INDEPENDENTLY_VERIFIED",
        independently_verified=True,
        known_limitations="Closed-form geometry only; no FEA packaging.",
        impact_level=ImpactLevel.HIGH,
        affected_outputs=("stroke", "bore", "rod_loading", "reciprocating_mass"),
        sensitivity_rank=10,
        upgrade_priority="HIGH",
        subsystem="geometry",
    ),
    make_descriptor(
        id="reciprocating_mass_model",
        maturity=ModelMaturity.M2,
        owner="ReciprocatingMassModel",
        engineering_reference="Geometry + density shell estimate",
        validation_status="FORMULA_VERIFIED_PARAMETERS_ASSUMED",
        independently_verified=True,
        known_limitations=(
            "Upgraded from kg/L heuristic (M1→M2). Thickness/density fractions are explicit "
            "assumptions. M3/M4 withheld: no OEM piston-mass correlation dataset wired yet."
        ),
        impact_level=ImpactLevel.CRITICAL,
        affected_outputs=("rod_loading", "rod_stress", "material_selection"),
        sensitivity_rank=4,
        upgrade_priority="VERY_HIGH",
        subsystem="physics",
    ),
    make_descriptor(
        id="connecting_rod_model",
        maturity=ModelMaturity.M3,
        owner="ConnectingRodModel",
        engineering_reference="I/H-beam section + Euler buckling",
        validation_status="FORMULA_VERIFIED_PARAMETERS_ASSUMED",
        independently_verified=True,
        known_limitations=(
            "Geometry-aware section vs assumed area band. M4 withheld pending published "
            "rod-section / measured-stress correlation."
        ),
        impact_level=ImpactLevel.CRITICAL,
        affected_outputs=("rod_stress", "material_selection", "buckling", "fatigue"),
        sensitivity_rank=1,
        upgrade_priority="VERY_HIGH",
        subsystem="physics",
    ),
    # Legacy alias kept for upgrade-priority reports.
    make_descriptor(
        id="piston_mass_estimate",
        maturity=ModelMaturity.M2,
        owner="ReciprocatingMassModel",
        engineering_reference="Delegates to ReciprocatingMassModel (Phase 5.0)",
        validation_status="FORMULA_VERIFIED_PARAMETERS_ASSUMED",
        independently_verified=True,
        known_limitations="Alias of reciprocating_mass_model — see that entry.",
        impact_level=ImpactLevel.HIGH,
        affected_outputs=("rod_loading", "rod_stress"),
        sensitivity_rank=6,
        upgrade_priority="HIGH",
        subsystem="physics",
    ),
    make_descriptor(
        id="engine_cycle_model",
        maturity=ModelMaturity.M2,
        owner="EngineCycleModel",
        engineering_reference="Empirical NA/boosted BMEP + efficiency bands with provenance",
        validation_status="FORMULA_VERIFIED_PARAMETERS_ASSUMED",
        independently_verified=True,
        known_limitations=(
            "Replaces naked BMEP constants with ProvenancedValue sources. "
            "M3/M4 withheld until family-separated BMEP error bounds are accepted as calibration."
        ),
        impact_level=ImpactLevel.CRITICAL,
        affected_outputs=("displacement", "stroke", "mps", "rod_loading"),
        sensitivity_rank=7,
        upgrade_priority="VERY_HIGH",
        subsystem="physics",
    ),
    make_descriptor(
        id="thermal_model",
        maturity=ModelMaturity.M3,
        owner="ThermalModel",
        engineering_reference="Calculated heat rejection; empirical combustion temperature",
        validation_status="FORMULA_VERIFIED_PARAMETERS_ASSUMED",
        independently_verified=True,
        known_limitations=(
            "Separates calculated energy-split from empirical combustion-side map. "
            "Combustion temperature remains UNVALIDATED."
        ),
        impact_level=ImpactLevel.HIGH,
        affected_outputs=("heat_rejection", "combustion_temperature", "material_selection"),
        sensitivity_rank=11,
        upgrade_priority="HIGH",
        subsystem="thermal",
    ),
]

_MATERIALS: list[ModelDescriptor] = [
    make_descriptor(
        id="material_req_structural",
        maturity=ModelMaturity.M2,
        owner="MaterialAssigner",
        engineering_reference="MaterialRequirementEvidence from computed rod stress",
        validation_status="FORMULA_VERIFIED_PARAMETERS_ASSUMED",
        known_limitations="Safety factors remain engineering judgment; now explicit in evidence packet.",
        impact_level=ImpactLevel.HIGH,
        affected_outputs=("material_selection", "validation"),
        sensitivity_rank=8,
        upgrade_priority="HIGH",
        subsystem="materials",
    ),
    make_descriptor(
        id="material_req_piston",
        maturity=ModelMaturity.M2,
        owner="MaterialAssigner",
        engineering_reference="MaterialRequirementEvidence from stress + combustion temp",
        validation_status="FORMULA_VERIFIED_PARAMETERS_ASSUMED",
        known_limitations="Safety factors remain engineering judgment; temperature still empirical.",
        impact_level=ImpactLevel.HIGH,
        affected_outputs=("material_selection", "validation"),
        sensitivity_rank=9,
        upgrade_priority="HIGH",
        subsystem="materials",
    ),
    make_descriptor(
        id="material_selection_ranking",
        maturity=ModelMaturity.M2,
        owner="MaterialAssigner",
        engineering_reference="Catalog threshold + ranking with evidence packet",
        validation_status="ASSUMPTION",
        known_limitations="Still catalog ranking — not FEA or fatigue life prediction.",
        impact_level=ImpactLevel.MEDIUM,
        affected_outputs=("material_selection",),
        sensitivity_rank=30,
        upgrade_priority="MEDIUM",
        subsystem="materials",
    ),
    make_descriptor(
        id="bmep_assumption_bands",
        maturity=ModelMaturity.M2,
        owner="EngineCycleModel",
        engineering_reference="Delegates to EngineCycleModel empirical BMEP bands (Phase 7.0)",
        validation_status="FORMULA_VERIFIED_PARAMETERS_ASSUMED",
        independently_verified=True,
        known_limitations=(
            "Closed from naked PE constants into EngineCycleModel ProvenancedValue. "
            "Band endpoints unchanged for baseline invariance. M4 withheld."
        ),
        impact_level=ImpactLevel.HIGH,
        affected_outputs=("displacement", "rod_loading"),
        sensitivity_rank=16,
        upgrade_priority="HIGH",
        subsystem="physics",
    ),
]

_STANDARDS: list[ModelDescriptor] = [
    make_descriptor(
        id="mean_piston_speed_hard_limit",
        maturity=ModelMaturity.M1,
        owner="ConstraintEvaluator",
        engineering_reference="Engineering standard gate at 26 m/s (not a physics law)",
        validation_status="ASSUMPTION",
        known_limitations="Hard-limit classification only; does not derive the limit from first principles.",
        impact_level=ImpactLevel.MEDIUM,
        affected_outputs=("validation",),
        sensitivity_rank=40,
        upgrade_priority="MEDIUM",
        subsystem="constraints",
    ),
]


def _build_registry() -> dict[str, ModelDescriptor]:
    entries = _PHYSICS + _PLACEHOLDERS + _ENGINEERING + _MATERIALS + _STANDARDS
    registry: dict[str, ModelDescriptor] = {}
    for desc in entries:
        validate_descriptor(desc)
        if desc.id in registry:
            raise ValueError(f"Duplicate model id: {desc.id}")
        registry[desc.id] = desc
    missing = ENGINEERING_CALCULATION_IDS - set(registry)
    if missing:
        raise ValueError(f"Registry missing engineering calculations: {sorted(missing)}")
    from core.verification.maturity_promotions import apply_recorded_promotions

    return apply_recorded_promotions(registry)


MODEL_REGISTRY: dict[str, ModelDescriptor] = _build_registry()


def get_descriptor(model_id: str) -> ModelDescriptor | None:
    return MODEL_REGISTRY.get(model_id)


def descriptor_for_calc(calc_id: str) -> ModelDescriptor | None:
    return MODEL_REGISTRY.get(calc_id)


def maturity_for_calc(calc_id: str) -> ModelMaturity | None:
    desc = descriptor_for_calc(calc_id)
    return desc.maturity if desc else None


def all_descriptors() -> list[ModelDescriptor]:
    return list(MODEL_REGISTRY.values())


def registry_coverage() -> dict[str, Any]:
    registered_calcs = ENGINEERING_CALCULATION_IDS & set(MODEL_REGISTRY)
    return {
        "engineering_calculation_ids": sorted(ENGINEERING_CALCULATION_IDS),
        "registered_calculation_ids": sorted(registered_calcs),
        "missing_calculation_ids": sorted(ENGINEERING_CALCULATION_IDS - set(MODEL_REGISTRY)),
        "extra_non_calc_models": sorted(set(MODEL_REGISTRY) - ENGINEERING_CALCULATION_IDS),
        "coverage_complete": ENGINEERING_CALCULATION_IDS <= set(MODEL_REGISTRY),
        "registry_size": len(MODEL_REGISTRY),
    }
