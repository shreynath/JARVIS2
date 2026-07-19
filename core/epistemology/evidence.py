"""Evidence — 1:1 wrap of Phase 1 calculation provenance. String confidence only."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from core.epistemology.knowledge_state import KnowledgeState

ConfidenceStr = Literal["high", "medium", "low"]


@dataclass(frozen=True)
class Evidence:
    claim: str
    state: KnowledgeState
    confidence: ConfidenceStr
    reason: str
    source_calc_id: str | None = None


def _as_knowledge_state(value: Any) -> KnowledgeState:
    if isinstance(value, KnowledgeState):
        return value
    if hasattr(value, "value"):
        return KnowledgeState(str(value.value))
    return KnowledgeState(str(value))


def _as_confidence(value: Any) -> ConfidenceStr:
    text = str(value or "medium").strip().lower()
    if text not in {"high", "medium", "low"}:
        # Preserve Phase 1 fidelity: unexpected values stay visible as medium only if empty;
        # otherwise raise so we never invent a parallel confidence system.
        if not value:
            return "medium"
        raise ValueError(f"Evidence.confidence must be high|medium|low, got {value!r}")
    return text  # type: ignore[return-value]


def wrap_calculation(calc: Any) -> Evidence:
    """Map an existing PhysicsCalculation (or dict) into Evidence — read-only wrap."""
    if isinstance(calc, dict):
        calc_id = calc.get("id")
        name = calc.get("name") or calc_id or "unnamed"
        state = _as_knowledge_state(calc.get("knowledge_state", KnowledgeState.UNKNOWN))
        confidence = _as_confidence(calc.get("confidence", "medium"))
        reason = calc.get("assessment") or calc.get("reason") or ""
        return Evidence(
            claim=str(name),
            state=state,
            confidence=confidence,
            reason=str(reason),
            source_calc_id=str(calc_id) if calc_id else None,
        )

    calc_id = getattr(calc, "id", None)
    name = getattr(calc, "name", None) or calc_id or "unnamed"
    state = _as_knowledge_state(getattr(calc, "knowledge_state", KnowledgeState.UNKNOWN))
    confidence = _as_confidence(getattr(calc, "confidence", "medium"))
    reason = getattr(calc, "assessment", None) or getattr(calc, "reason", None) or ""
    return Evidence(
        claim=str(name),
        state=state,
        confidence=confidence,
        reason=str(reason),
        source_calc_id=str(calc_id) if calc_id else None,
    )
