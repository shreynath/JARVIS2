"""Raw external evidence records — before validation-case promotion."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class EvidenceStatus(str, Enum):
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass
class RawEvidenceRecord:
    """Single external fact with full provenance. Missing fields stay None."""

    id: str
    component: str
    field: str
    value: float | int | str | None
    unit: str | None
    source_id: str
    source_title: str
    measurement_type: str  # direct | derived | estimate | unknown | synthetic
    quality: str  # high | medium | low | unknown
    provenance: dict[str, Any] = field(default_factory=dict)
    uncertainty: dict[str, float] = field(default_factory=dict)
    engine: str | None = None
    engine_id: str | None = None
    status: EvidenceStatus = EvidenceStatus.PENDING_REVIEW
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        raw = asdict(self)
        raw["status"] = self.status.value
        return raw

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> RawEvidenceRecord:
        status = payload.get("status", EvidenceStatus.PENDING_REVIEW)
        if isinstance(status, str):
            status = EvidenceStatus(status)
        return cls(
            id=str(payload["id"]),
            component=str(payload["component"]),
            field=str(payload["field"]),
            value=payload.get("value"),
            unit=payload.get("unit"),
            source_id=str(payload["source_id"]),
            source_title=str(payload.get("source_title") or payload.get("source") or ""),
            measurement_type=str(payload.get("measurement_type") or "unknown"),
            quality=str(payload.get("quality") or "unknown"),
            provenance=dict(payload.get("provenance") or {}),
            uncertainty=dict(payload.get("uncertainty") or {}),
            engine=payload.get("engine"),
            engine_id=payload.get("engine_id"),
            status=status,
            notes=payload.get("notes"),
        )

    def is_invalid(self) -> bool:
        """Synthetic or structurally incomplete records are invalid."""
        if self.measurement_type == "synthetic":
            return True
        if self.value is None:
            return True
        if not self.unit:
            return True
        if not self.source_id or not self.source_title:
            return True
        if not self.provenance:
            return True
        if not self.uncertainty:
            return True
        return False

    def rejects(self) -> bool:
        return self.is_invalid()
