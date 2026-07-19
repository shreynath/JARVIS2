"""Requirement specification — compiled engineering intent before decomposition."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from core.ir.constraint import ConstraintPriority, Requirement


class SpecificationStatus(StrEnum):
    COMPLETE = "complete"
    INCOMPLETE = "incomplete"


class DecisionCategory(StrEnum):
    ARCHITECTURE = "architecture"
    ASPIRATION = "aspiration"
    TARGET_OUTPUT = "target_output"
    DUTY_CYCLE = "duty_cycle"
    FUEL = "fuel"
    CONSTRAINTS = "constraints"


class DecisionStatus(StrEnum):
    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"


class RequiredDecision(BaseModel):
    """A design decision the engineer must make before synthesis proceeds."""

    id: str
    category: DecisionCategory
    question: str
    options: list[str] = Field(default_factory=list)
    status: DecisionStatus = DecisionStatus.UNRESOLVED
    resolved_value: str | None = None
    rationale: str = ""


class CompiledRequirement(BaseModel):
    """A traceable engineering requirement derived from intent or reference profile."""

    id: str
    description: str
    metric: str | None = None
    target_value: str | float | None = None
    unit: str | None = None
    priority: ConstraintPriority = ConstraintPriority.MEDIUM
    source: str = "requirement_compiler"
    originating_text: str = ""
    affected_assemblies: list[str] = Field(default_factory=list)
    affected_components: list[str] = Field(default_factory=list)
    downstream_design_consequences: list[str] = Field(default_factory=list)
    derived_from: list[str] = Field(default_factory=list)
    satisfies_decisions: list[str] = Field(default_factory=list)


class RequirementSpecification(BaseModel):
    """Compiled requirement document — the output of the Engineering Requirement Compiler."""

    status: SpecificationStatus
    object_type: str
    design_goal: str
    requirements: list[CompiledRequirement] = Field(default_factory=list)
    required_decisions: list[RequiredDecision] = Field(default_factory=list)
    resolved_parameters: dict[str, str | float | int] = Field(default_factory=dict)
    reference_profile: str | None = None
    completeness_rationale: str = ""
    unrecognized_terms: list[dict[str, str]] = Field(default_factory=list)
    conflicts: list[dict[str, str]] = Field(default_factory=list)
    implausible_parameters: list[dict[str, str | float | int]] = Field(default_factory=list)

    def is_complete(self) -> bool:
        return self.status == SpecificationStatus.COMPLETE

    def unresolved_decisions(self) -> list[RequiredDecision]:
        return [d for d in self.required_decisions if d.status == DecisionStatus.UNRESOLVED]

    def to_requirement_nodes(self) -> list[Requirement]:
        return [
            Requirement(
                id=r.id,
                description=r.description,
                metric=r.metric,
                target_value=r.target_value,
                priority=r.priority,
            )
            for r in self.requirements
        ]
