"""Phase 2 evaluation package — EngineeringEvaluator firewall."""

from __future__ import annotations

from typing import Any

__all__ = [
    "Completeness",
    "EngineeringEvaluator",
    "EvaluationResult",
    "EvaluationStatus",
    "IllegalCandidateVariablesError",
    "Issue",
    "Phase1Provider",
    "VariableValidationResult",
    "validate_candidate_variables",
]


def __getattr__(name: str) -> Any:
    if name in {"Completeness", "EvaluationResult"}:
        from core.evaluation import evaluation_result as mod

        return getattr(mod, name)
    if name == "Issue":
        from core.evaluation.issue import Issue

        return Issue
    if name == "EvaluationStatus":
        from core.evaluation.evaluation_status import EvaluationStatus

        return EvaluationStatus
    if name == "EngineeringEvaluator":
        from core.evaluation.engineering_evaluator import EngineeringEvaluator

        return EngineeringEvaluator
    if name == "Phase1Provider":
        from core.evaluation.provider import Phase1Provider

        return Phase1Provider
    if name in {
        "IllegalCandidateVariablesError",
        "VariableValidationResult",
        "validate_candidate_variables",
    }:
        from core.evaluation import variable_validator as mod

        return getattr(mod, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
