"""Shared epistemology — consolidation of Phase 1 provenance into Evidence."""

from __future__ import annotations

from core.epistemology.assumption_registry import AssumptionRegistry, RegisteredAssumption
from core.epistemology.evidence import ConfidenceStr, Evidence, wrap_calculation
from core.epistemology.input_requirement import (
    InputRequirement,
    InputState,
    MissingEngineeringInputError,
)
from core.epistemology.knowledge_state import KnowledgeState

__all__ = [
    "AssumptionRegistry",
    "ConfidenceStr",
    "Evidence",
    "InputRequirement",
    "InputState",
    "KnowledgeState",
    "MissingEngineeringInputError",
    "RegisteredAssumption",
    "wrap_calculation",
]
