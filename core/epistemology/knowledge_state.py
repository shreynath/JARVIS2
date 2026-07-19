"""KnowledgeState — categorical labels only. No ordering operators."""

from __future__ import annotations

from enum import Enum


class KnowledgeState(str, Enum):
    """Provenance category for a claim. Not ordered — never compare with < / >.

    Subclasses ``str`` only so Phase 1 JSON dumps stay string-valued (same payloads).
    Preference between states is claim-family-scoped and belongs to the caller,
    never on this enum.
    """

    KNOWN = "known"
    DERIVED = "derived"
    SIMULATED = "simulated"
    EMPIRICAL = "empirical"
    INTERPOLATED = "interpolated"
    ESTIMATED = "estimated"
    ASSUMED = "assumed"
    UNKNOWN = "unknown"

    def __lt__(self, other: object) -> bool:  # pragma: no cover - must raise
        raise TypeError("KnowledgeState has no global ordering; use a claim-family comparator")

    def __gt__(self, other: object) -> bool:  # pragma: no cover
        raise TypeError("KnowledgeState has no global ordering; use a claim-family comparator")

    def __le__(self, other: object) -> bool:  # pragma: no cover
        raise TypeError("KnowledgeState has no global ordering; use a claim-family comparator")

    def __ge__(self, other: object) -> bool:  # pragma: no cover
        raise TypeError("KnowledgeState has no global ordering; use a claim-family comparator")
