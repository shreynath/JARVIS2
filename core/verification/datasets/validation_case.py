"""External validation case — ground truth for calibration (never JARVIS-generated)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class SystemType(Enum):
    ENGINE = "engine"
    STRUCTURE = "structure"
    MATERIAL = "material"
    THERMAL = "thermal"


class ValidationQuality(Enum):
    EXPERIMENTAL = "experimental"
    MANUFACTURER = "manufacturer"
    LITERATURE = "literature"
    ESTIMATED = "estimated"


@dataclass(frozen=True)
class ValidationCase:
    """External truth record. Missing measured fields remain None — never filled."""

    id: str
    system_type: SystemType
    reference_source: dict[str, Any]
    inputs: dict[str, float | int | None]
    measured_outputs: dict[str, float | int | None]
    uncertainty: dict[str, float] = field(default_factory=dict)
    validation_quality: ValidationQuality = ValidationQuality.MANUFACTURER
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        raw = asdict(self)
        raw["system_type"] = self.system_type.value
        raw["validation_quality"] = self.validation_quality.value
        return raw

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ValidationCase:
        from core.verification.datasets.schemas import validate_case_dict

        validate_case_dict(payload)
        return cls(
            id=str(payload["id"]),
            system_type=SystemType(payload["system_type"]),
            reference_source=dict(payload["reference_source"]),
            inputs=dict(payload["inputs"]),
            measured_outputs=dict(payload["measured_outputs"]),
            uncertainty=dict(payload.get("uncertainty") or {}),
            validation_quality=ValidationQuality(payload["validation_quality"]),
            notes=payload.get("notes"),
        )

    def measured(self, key: str) -> float | None:
        value = self.measured_outputs.get(key)
        if value is None:
            return None
        return float(value)
