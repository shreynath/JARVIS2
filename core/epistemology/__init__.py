"""Shared epistemology — consolidation of Phase 1 provenance into Evidence."""

from __future__ import annotations

from core.epistemology.evidence import ConfidenceStr, Evidence, wrap_calculation
from core.epistemology.knowledge_state import KnowledgeState

__all__ = [
    "ConfidenceStr",
    "Evidence",
    "KnowledgeState",
    "wrap_calculation",
]
