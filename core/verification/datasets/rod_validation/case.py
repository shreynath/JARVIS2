"""RodValidationCase schema."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class RodValidationCase:
    """External rod/reciprocating evidence packet. No PhysicsEngine coupling."""

    engine_name: str
    engine_id: str
    rpm: float | None
    stroke_mm: float | None
    rod_length_mm: float | None
    piston_mass_g: float | None
    rod_mass_g: float | None
    bore_mm: float | None
    reported_component_data: dict[str, Any]
    source: str
    confidence: str  # high | medium | low | missing_masses

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def has_absolute_mass(self) -> bool:
        return self.piston_mass_g is not None and self.rod_mass_g is not None

    @property
    def has_geometry(self) -> bool:
        return self.stroke_mm is not None and self.rpm is not None and self.bore_mm is not None
