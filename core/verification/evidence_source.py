"""External evidence source metadata — provenance for ingested engineering facts."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class SourceType(str, Enum):
    OEM_DOCUMENTATION = "OEM_DOCUMENTATION"
    PEER_REVIEWED_PAPER = "PEER_REVIEWED_PAPER"
    TEARDOWN_DATA = "TEARDOWN_DATA"
    ENGINEERING_DATABASE = "ENGINEERING_DATABASE"
    TECHNICAL_MANUAL = "TECHNICAL_MANUAL"
    SECONDARY_ESTIMATE = "SECONDARY_ESTIMATE"


ALLOWED_SOURCE_TYPES = frozenset(SourceType)


@dataclass(frozen=True)
class EvidenceSource:
    """Catalog entry describing where external facts originate."""

    source_id: str
    title: str
    organization: str
    source_type: SourceType
    publication_date: str | None = None
    url_or_reference: str | None = None
    license: str | None = None
    credibility_rating: str = "medium"  # high | medium | low
    notes: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        raw = asdict(self)
        raw["source_type"] = self.source_type.value
        raw["extra"] = dict(self.extra)
        return raw

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> EvidenceSource:
        st = payload.get("source_type")
        if isinstance(st, SourceType):
            source_type = st
        else:
            source_type = SourceType(str(st))
        if source_type not in ALLOWED_SOURCE_TYPES:
            raise ValueError(f"Unknown source_type: {st!r}")
        return cls(
            source_id=str(payload["source_id"]),
            title=str(payload["title"]),
            organization=str(payload.get("organization") or ""),
            source_type=source_type,
            publication_date=payload.get("publication_date"),
            url_or_reference=payload.get("url_or_reference"),
            license=payload.get("license"),
            credibility_rating=str(payload.get("credibility_rating") or "medium"),
            notes=payload.get("notes"),
            extra=dict(payload.get("extra") or {}),
        )
