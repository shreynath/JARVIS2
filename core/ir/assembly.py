"""Assembly node in the engineering design graph."""

from __future__ import annotations

from pydantic import BaseModel, Field

from core.ir.constraint import Constraint, Interface, Requirement


class AssemblyNode(BaseModel):
    """A grouping of components with shared function."""

    id: str
    name: str
    type: str = "assembly"
    function: str
    purpose: str = ""
    justification: str = ""
    children: list[str] = Field(default_factory=list)
    member_ids: list[str] = Field(default_factory=list)
    parent_id: str | None = None
    serves_functions: list[str] = Field(default_factory=list)
    constraints: list[Constraint] = Field(default_factory=list)
    requirements: list[Requirement] = Field(default_factory=list)
    interfaces: list[Interface] = Field(default_factory=list)
