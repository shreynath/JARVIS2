"""Shared constraint and requirement types."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class ConstraintPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Severity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class ConstraintSpec(BaseModel):
    """A constraint extracted from user intent."""

    type: str
    description: str = ""
    priority: ConstraintPriority = ConstraintPriority.MEDIUM
    value: str | float | None = None


class Constraint(BaseModel):
    """A constraint applied to a design graph node."""

    id: str
    type: str
    description: str
    priority: ConstraintPriority = ConstraintPriority.MEDIUM
    value: str | float | None = None
    source: str = "intent"


class Requirement(BaseModel):
    """An engineering requirement on a component or assembly."""

    id: str
    description: str
    metric: str | None = None
    target_value: str | float | None = None
    priority: ConstraintPriority = ConstraintPriority.MEDIUM


class Assumption(BaseModel):
    """A recorded assumption where the design lacks certainty."""

    id: str
    field: str
    assumed_value: str
    rationale: str = ""
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    source: str = "assumption_manager"


class Interface(BaseModel):
    """Connection interface between components."""

    id: str
    name: str
    interface_type: str
    connects_to: str | None = None
    description: str = ""


class FailureMode(BaseModel):
    """Known failure mode for a component."""

    id: str
    mode: str
    cause: str = ""
    effect: str = ""
    severity: Severity = Severity.WARNING


class CriticIssue(BaseModel):
    """An issue raised by the design critic."""

    id: str
    node_id: str
    description: str
    severity: Severity
    category: str = "consistency"
    suggested_fix: str = ""
