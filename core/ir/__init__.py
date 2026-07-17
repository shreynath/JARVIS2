"""Intermediate representation — typed engineering design graph structures."""

from core.ir.assembly import AssemblyNode
from core.ir.component import ComponentNode
from core.ir.constraint import (
    Assumption,
    Constraint,
    ConstraintPriority,
    ConstraintSpec,
    CriticIssue,
    FailureMode,
    Interface,
    Requirement,
    Severity,
)
from core.ir.design_graph import EngineeringDesignGraph, EngineeringIntent

__all__ = [
    "AssemblyNode",
    "Assumption",
    "ComponentNode",
    "Constraint",
    "ConstraintPriority",
    "ConstraintSpec",
    "CriticIssue",
    "EngineeringDesignGraph",
    "EngineeringIntent",
    "FailureMode",
    "Interface",
    "Requirement",
    "Severity",
]
