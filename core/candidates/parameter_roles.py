"""Parameter roles — semantic claims for candidate variables (Phase 3.0).

Mutability is determined by role + provenance + study declaration
(``CandidateDesign.declared_knobs``), not by parameter name alone.

Role owns *who may write the value*:
    FIXED_REQUIREMENT   — problem statement; immutable unless declared a knob
    OPTIMIZATION_KNOB   — legal CandidateDesign.variables entry
    DERIVED_OUTPUT      — EvaluationResult / physics only; never proposable
    ASSUMPTION_INTERNAL — estimation / range fill-in; never proposable
    OUT_OF_MODEL        — no consumer / no representation; reject

Provenance owns *how the value was obtained* (same key, different meaning):
    KNOWN / ASSUMED / DERIVED / UNSPECIFIED
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class ParameterRole(StrEnum):
    FIXED_REQUIREMENT = "fixed_requirement"
    OPTIMIZATION_KNOB = "optimization_knob"
    DERIVED_OUTPUT = "derived_output"
    ASSUMPTION_INTERNAL = "assumption_internal"
    OUT_OF_MODEL = "out_of_model"


class ParameterProvenance(StrEnum):
    """Origin of a parameter claim — orthogonal to ParameterRole."""

    KNOWN = "known"
    ASSUMED = "assumed"
    DERIVED = "derived"
    UNSPECIFIED = "unspecified"


class ParameterClaim(BaseModel):
    """A named parameter with role and provenance (not a physics value store)."""

    name: str
    value: float | int | str | None = None
    role: ParameterRole
    provenance: ParameterProvenance = ParameterProvenance.UNSPECIFIED
    reason: str = ""


# Default legal knobs for ICE studies — may appear in candidate.variables without
# declared_knobs. Names must be keys PhysicsEngine already reads from resolved_parameters.
DEFAULT_OPTIMIZATION_KNOBS: frozenset[str] = frozenset({"max_rpm"})

# Structural / objective keys from the requirement compiler. Mutable only when listed
# in CandidateDesign.declared_knobs (study elevates FIXED → OPTIMIZATION_KNOB).
DEFAULT_FIXED_REQUIREMENTS: frozenset[str] = frozenset(
    {
        "target_horsepower",
        "engine_architecture",
        "cylinder_count",
        "aspiration",
        "fuel_type",
        "ignition_type",
        "duty_cycle",
        "displacement_l",
        "mass_kg",
        "target_torque_nm",
        "specific_power_hp_l",
        "nvh_priority",
        "emissions_priority",
    }
)

# Physics / operating outputs — proposing them is wishing results into existence.
DERIVED_OUTPUT_KEYS: frozenset[str] = frozenset(
    {
        "torque_nm",
        "torque",
        "mean_piston_speed_m_s",
        "mean_piston_speed_m_s_high",
        "piston_speed",
        "peak_piston_acceleration_m_s2",
        "rod_stress_requirement_mpa",
        "rod_load",
        "stress",
        "cooling_heat_rejection_kw",
        "combustion_side_temperature_c",
        "displacement_l_low",
        "displacement_l_high",
    }
)

# Internal estimation levers / range constants — not candidate variables.
ASSUMPTION_INTERNAL_KEYS: frozenset[str] = frozenset(
    {
        "bore_stroke_ratio",
        "bmep",
        "bmep_pa",
        "piston_mass_per_displacement",
        "rod_section_area",
    }
)

# Known vocabulary with no Phase 1 consumer (reject; do not silently ignore).
OUT_OF_MODEL_KEYS: frozenset[str] = frozenset(
    {
        "compression_ratio",
        "stroke_mm",  # analyze() kwarg only — not yet on resolved_parameters path
        "manufacturing_cost",
        "packaging",
        "packaging_constraints",
        "cost",
    }
)

# Keys physics estimates when absent from resolved_parameters (dual-role hazard).
PHYSICS_ESTIMATED_WHEN_ABSENT: frozenset[str] = frozenset({"displacement_l"})
