"""External validation dataset package — independent of production engineering models.

MUST NOT import PhysicsEngine, MaterialAssigner, ConstraintEvaluator, or EngineeringEvaluator.
Validation cases are external truth only.
"""

from core.verification.datasets.validation_case import (
    SystemType,
    ValidationCase,
    ValidationQuality,
)
from core.verification.datasets.registry import (
    VALIDATION_CASE_REGISTRY,
    all_validation_cases,
    cases_for_system,
    get_validation_case,
    load_engine_validation_cases,
)
from core.verification.datasets.schemas import validate_case_dict

__all__ = [
    "SystemType",
    "VALIDATION_CASE_REGISTRY",
    "ValidationCase",
    "ValidationQuality",
    "all_validation_cases",
    "cases_for_system",
    "get_validation_case",
    "load_engine_validation_cases",
    "validate_case_dict",
]
