"""Phase 2 evaluation package — EngineeringEvaluator firewall."""

from __future__ import annotations

from core.evaluation.engineering_evaluator import EngineeringEvaluator
from core.evaluation.evaluation_result import Completeness, EvaluationResult
from core.evaluation.provider import Phase1Provider
from core.evaluation.variable_validator import (
    IllegalCandidateVariablesError,
    VariableValidationResult,
    validate_candidate_variables,
)

__all__ = [
    "Completeness",
    "EngineeringEvaluator",
    "EvaluationResult",
    "IllegalCandidateVariablesError",
    "Phase1Provider",
    "VariableValidationResult",
    "validate_candidate_variables",
]

