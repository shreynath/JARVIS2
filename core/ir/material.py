"""Typed material specification with physics properties."""

from __future__ import annotations

from pydantic import BaseModel, Field


class MaterialSpec(BaseModel):
    """Material with physics properties for downstream CAD/FEM."""

    name: str
    density_kg_m3: float
    yield_strength_mpa: float | None = None
    fatigue_strength_mpa: float | None = None
    thermal_conductivity_w_mk: float | None = None
    temperature_limit_c: float | None = None
    relative_cost: float | None = None
    source: str = "knowledge.materials.catalog"
    suitable_for: list[str] = Field(default_factory=list)
    selection_rationale: str = ""
    selection_metrics: dict[str, str | float | int | bool | None] = Field(default_factory=dict)
    candidate_rankings: list[dict[str, str | float | int | bool | None]] = Field(default_factory=list)

    @classmethod
    def from_catalog(cls, key: str) -> MaterialSpec | None:
        from knowledge.materials.catalog import MATERIAL_CATALOG

        entry = MATERIAL_CATALOG.get(key)
        if entry is None:
            return None
        return cls(**entry)
