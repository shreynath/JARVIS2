"""Candidate designs package — minimal input types for EngineeringEvaluator."""

from __future__ import annotations

from core.candidates.candidate_design import CandidateDesign, CandidateStatus
from core.candidates.parameter_roles import (
    ParameterClaim,
    ParameterProvenance,
    ParameterRole,
)

__all__ = [
    "CandidateDesign",
    "CandidateStatus",
    "ParameterClaim",
    "ParameterProvenance",
    "ParameterRole",
]
