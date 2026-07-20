"""MaterialDecision — every assignment must carry computed evidence or be UNKNOWN."""

from __future__ import annotations

from dataclasses import dataclass, field

from core.epistemology.evidence import Evidence


@dataclass
class MaterialDecision:
    component_id: str
    role: str
    selected_material: str | None
    requirement_source: str | None
    requirement_value: float | None
    evidence: list[Evidence] = field(default_factory=list)
    confidence: str = "UNKNOWN"

    def as_dict(self) -> dict[str, object]:
        return {
            "component_id": self.component_id,
            "role": self.role,
            "selected_material": self.selected_material,
            "requirement_source": self.requirement_source,
            "requirement_value": self.requirement_value,
            "evidence": [
                {
                    "claim": e.claim,
                    "state": e.state.value if hasattr(e.state, "value") else str(e.state),
                    "confidence": e.confidence,
                    "reason": e.reason,
                    "source_calc_id": e.source_calc_id,
                }
                for e in self.evidence
            ],
            "confidence": self.confidence,
        }
