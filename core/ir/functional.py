"""Functional decomposition models — reasoning before parts."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class FlowType(StrEnum):
    ENERGY = "energy"
    MATERIAL = "material"
    INFORMATION = "information"


class SystemFunction(BaseModel):
    """A function the system must perform."""

    id: str
    name: str
    description: str
    requires: list[str] = Field(default_factory=list)
    domain: str = "mechanical_design"


class FlowEdge(BaseModel):
    """Energy, material, or information flow between functions."""

    id: str
    flow_type: FlowType
    source_function_id: str
    target_function_id: str
    description: str = ""


class RequiredAssembly(BaseModel):
    """An assembly identified by functional analysis before parts exist."""

    id: str
    name: str
    function: str
    purpose: str
    serves_functions: list[str] = Field(default_factory=list)
    parent_assembly_id: str | None = None


class FunctionalAnalysis(BaseModel):
    """Output of functional decomposition — the engineering question structured."""

    primary_function: str
    functions: list[SystemFunction] = Field(default_factory=list)
    flows: list[FlowEdge] = Field(default_factory=list)
    required_assemblies: list[RequiredAssembly] = Field(default_factory=list)
    required_domains: list[str] = Field(default_factory=list)

    def function_map(self) -> dict[str, SystemFunction]:
        return {f.id: f for f in self.functions}

    def get_function(self, function_id: str) -> SystemFunction | None:
        return self.function_map().get(function_id)
