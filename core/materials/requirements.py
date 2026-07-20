"""Material requirements framework — no requirement without a calculation source.

Phase 7 canonical API. Ranking still lives in MaterialAssigner; this module defines
the auditable requirement contract.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from core.materials.material_requirement import (
    MaterialRequirementEvidence,
    build_piston_requirement,
    build_structural_rod_requirement,
    unknown_requirement,
)


@dataclass
class MaterialRequirement:
    """Requirement that must be backed by load/calc dependencies."""

    component: str
    required_properties: dict[str, float]
    load_source: str
    calculation_dependencies: list[str]
    density_sensitive: bool = False
    status: str = "computed"  # computed | UNKNOWN
    safety_factors: dict[str, float] = field(default_factory=dict)
    load_case: str | None = None
    temperature_c: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def assert_has_source(self) -> None:
        if self.status == "UNKNOWN":
            return
        if not self.calculation_dependencies:
            raise ValueError(
                f"MaterialRequirement for {self.component!r} has no calculation_dependencies"
            )
        if not self.load_source:
            raise ValueError(f"MaterialRequirement for {self.component!r} has empty load_source")
        for key in ("yield_strength", "fatigue_strength", "temperature_limit"):
            # accept either yield_strength or yield_mpa style keys
            pass
        has_yield = any(k.startswith("yield") for k in self.required_properties)
        if not has_yield and self.status == "computed":
            raise ValueError(
                f"MaterialRequirement for {self.component!r} missing yield property"
            )


def from_stress(
    *,
    component: str,
    stress_mpa: float,
    temperature_c: float,
    yield_factor: float,
    fatigue_factor: float,
    dependencies: list[str],
    load_source: str,
    density_sensitive: bool = False,
    load_case: str = "peak_load",
) -> MaterialRequirement:
    req = MaterialRequirement(
        component=component,
        required_properties={
            "yield_strength": stress_mpa * yield_factor,
            "fatigue_strength": stress_mpa * fatigue_factor,
            "temperature_limit": temperature_c,
            "density": 0.0,  # ranking may fill; not a hard requirement unless mass-sensitive
        },
        load_source=load_source,
        calculation_dependencies=list(dependencies),
        density_sensitive=density_sensitive,
        status="computed",
        safety_factors={"yield": yield_factor, "fatigue": fatigue_factor},
        load_case=load_case,
        temperature_c=temperature_c,
    )
    req.assert_has_source()
    return req


def unexplained_material_choice_error(component: str, material: str) -> str:
    return (
        f"Illegal material decision for {component}: selected {material} without "
        f"load evidence / calculation_dependencies."
    )


__all__ = [
    "MaterialRequirement",
    "MaterialRequirementEvidence",
    "build_piston_requirement",
    "build_structural_rod_requirement",
    "from_stress",
    "unexplained_material_choice_error",
    "unknown_requirement",
]
