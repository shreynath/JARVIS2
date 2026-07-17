"""EngineeringDesignGraph — the central object of JARVIS 2.0."""

from __future__ import annotations

from pydantic import BaseModel, Field

from core.ir.assembly import AssemblyNode
from core.ir.component import ComponentNode
from core.ir.constraint import Assumption, ConstraintSpec


class EngineeringIntent(BaseModel):
    """Parsed engineering question — not domain classification."""

    object_type: str
    design_goal: str
    reference_objects: list[str] = Field(default_factory=list)
    constraints: list[ConstraintSpec] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    required_domains: list[str] = Field(default_factory=list)
    raw_input: str = ""


class EngineeringDesignGraph(BaseModel):
    """The central object: a validated engineering design graph."""

    name: str
    type: str
    intent: EngineeringIntent
    components: dict[str, ComponentNode] = Field(default_factory=dict)
    assemblies: dict[str, AssemblyNode] = Field(default_factory=dict)
    assumptions: list[Assumption] = Field(default_factory=list)
    root_id: str = ""
    metadata: dict[str, str | float | int | bool] = Field(default_factory=dict)

    def all_node_ids(self) -> set[str]:
        return set(self.components.keys()) | set(self.assemblies.keys())

    def get_node(self, node_id: str) -> ComponentNode | AssemblyNode | None:
        if node_id in self.components:
            return self.components[node_id]
        return self.assemblies.get(node_id)

    def add_component(self, component: ComponentNode) -> None:
        self.components[component.id] = component

    def add_assembly(self, assembly: AssemblyNode) -> None:
        self.assemblies[assembly.id] = assembly

    def to_spec_dict(self) -> dict:
        """Serialize to the Phase 1 output format."""

        def _serialize_component(comp: ComponentNode) -> dict:
            entry: dict = {
                "id": comp.id,
                "name": comp.name,
                "type": comp.type,
                "function": comp.function,
            }
            if comp.material:
                entry["material"] = comp.material
            if comp.children:
                entry["children"] = comp.children
            if comp.is_leaf:
                entry["is_leaf"] = True
            return entry

        root = self.components.get(self.root_id) or self.assemblies.get(self.root_id)
        return {
            "name": self.name,
            "type": self.type,
            "root_id": self.root_id,
            "components": [_serialize_component(c) for c in self.components.values()],
            "assemblies": [a.model_dump() for a in self.assemblies.values()],
            "assumption_count": len(self.assumptions),
            "intent": self.intent.model_dump(),
        }
