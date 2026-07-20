"""Computed material requirements — no assignment without evidence or explicit UNKNOWN."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class MaterialRequirementEvidence:
    """Structured requirement packet for one component material decision."""

    component: str
    required_properties: dict[str, float]
    computed_from: list[str]
    load_case: str
    temperature_c: float | None
    safety_factor: dict[str, float]
    reason_for_selection: str | None = None
    alternatives_considered: list[dict[str, Any]] = field(default_factory=list)
    status: str = "computed"  # computed | UNKNOWN
    role: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_structural_rod_requirement(
    *,
    component: str,
    stress_mpa: float,
    temperature_c: float = 160.0,
    yield_safety: float = 1.25,
    fatigue_safety: float = 0.65,
    computed_from: list[str] | None = None,
) -> MaterialRequirementEvidence:
    """Rod / structural load-path requirement from computed stress."""
    return MaterialRequirementEvidence(
        component=component,
        required_properties={
            "yield_mpa": stress_mpa * yield_safety,
            "fatigue_mpa": stress_mpa * fatigue_safety,
            "temperature_c": temperature_c,
        },
        computed_from=computed_from
        or ["calc_rod_stress_requirement", "connecting_rod_model"],
        load_case="peak_reciprocating_plus_gas_load",
        temperature_c=temperature_c,
        safety_factor={"yield": yield_safety, "fatigue_derate": fatigue_safety},
        role="structural_load_path",
        status="computed",
    )


def build_piston_requirement(
    *,
    component: str,
    stress_mpa: float,
    temperature_c: float,
    yield_safety: float = 0.55,
    fatigue_safety: float = 0.30,
    computed_from: list[str] | None = None,
) -> MaterialRequirementEvidence:
    return MaterialRequirementEvidence(
        component=component,
        required_properties={
            "yield_mpa": stress_mpa * yield_safety,
            "fatigue_mpa": stress_mpa * fatigue_safety,
            "temperature_c": temperature_c,
        },
        computed_from=computed_from
        or [
            "calc_rod_stress_requirement",
            "calc_combustion_side_temperature",
        ],
        load_case="reciprocating_thermal",
        temperature_c=temperature_c,
        safety_factor={"yield": yield_safety, "fatigue_derate": fatigue_safety},
        role="rotating_mass",
        status="computed",
    )


def unknown_requirement(component: str, reason: str) -> MaterialRequirementEvidence:
    return MaterialRequirementEvidence(
        component=component,
        required_properties={},
        computed_from=[],
        load_case="UNKNOWN",
        temperature_c=None,
        safety_factor={},
        reason_for_selection=None,
        alternatives_considered=[],
        status="UNKNOWN",
        role=None,
    )
