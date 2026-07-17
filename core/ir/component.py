"""Component node in the engineering design graph."""

from __future__ import annotations

from pydantic import BaseModel, Field

from core.ir.constraint import Constraint, FailureMode, Interface, Requirement


class ComponentNode(BaseModel):
    """A component in the design graph — leaf or intermediate."""

    id: str
    name: str
    type: str = "component"
    function: str
    material: str | None = None
    children: list[str] = Field(default_factory=list)
    parent_id: str | None = None
    constraints: list[Constraint] = Field(default_factory=list)
    requirements: list[Requirement] = Field(default_factory=list)
    interfaces: list[Interface] = Field(default_factory=list)
    failure_modes: list[FailureMode] = Field(default_factory=list)
    complexity_score: float = Field(default=1.0, ge=0.0)
    is_leaf: bool = False

    def child_count(self) -> int:
        return len(self.children)
