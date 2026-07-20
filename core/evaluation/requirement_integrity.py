"""Shared requirement integrity gates — contradictions block engineering."""

from __future__ import annotations

from core.evaluation.issue import Issue
from core.ir.requirement_spec import RequirementSpecification


def blocking_issues_from_spec(spec: RequirementSpecification) -> list[Issue]:
    """A contradiction is a blocked evaluation state, not an unknown to default."""
    issues: list[Issue] = []
    for conflict in spec.conflicts:
        field = str(conflict.get("field") or "requirement")
        issues.append(
            Issue(
                code="requirement_conflict",
                message=str(conflict.get("description") or conflict.get("inputs") or "Requirement conflict"),
                severity="blocking",
                field=field,
            )
        )
    return issues


def has_blocking_requirement_conflicts(spec: RequirementSpecification) -> bool:
    return bool(spec.conflicts)
