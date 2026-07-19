"""EngineeringDesignGraph — the central object of JARVIS 2.0."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from core.ir.assembly import AssemblyNode
from core.ir.component import ComponentNode
from core.ir.constraint import Assumption, ConstraintSpec
from core.ir.constraint_graph import ConstraintGraph
from core.ir.functional import FunctionalAnalysis

if TYPE_CHECKING:
    from core.ir.requirement_spec import RequirementSpecification
    from core.reasoning.physics_engine import PhysicsAnalysis


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
    functional_analysis: FunctionalAnalysis | None = None
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

    def to_spec_dict(
        self,
        requirement_spec: RequirementSpecification | None = None,
        physics_analysis: PhysicsAnalysis | None = None,
        constraint_graph: ConstraintGraph | None = None,
    ) -> dict:

        def _serialize_component(comp: ComponentNode) -> dict:
            entry: dict = {
                "id": comp.id,
                "name": comp.name,
                "type": comp.type,
                "function": comp.function,
                "purpose": comp.purpose,
                "justification": comp.justification,
            }
            if comp.material:
                entry["material"] = comp.material
            if comp.material_spec:
                entry["material_spec"] = comp.material_spec.model_dump()
            if comp.parent_assembly_id:
                entry["parent_assembly_id"] = comp.parent_assembly_id
            if comp.serves_function_id:
                entry["serves_function_id"] = comp.serves_function_id
            if comp.constraints:
                entry["constraints"] = [c.model_dump() for c in comp.constraints]
            if comp.is_leaf:
                entry["is_leaf"] = True
            return entry

        result: dict = {
            "name": self.name,
            "type": self.type,
            "root_id": self.root_id,
            "components": [_serialize_component(c) for c in self.components.values()],
            "assemblies": [a.model_dump() for a in self.assemblies.values()],
            "assumption_count": len(self.assumptions),
            "intent": self.intent.model_dump(),
        }

        if self.functional_analysis:
            result["functional_analysis"] = self.functional_analysis.model_dump()

        if requirement_spec:
            result["requirement_specification"] = requirement_spec.model_dump()

        if physics_analysis:
            result["physics_analysis"] = physics_analysis.model_dump()

        if constraint_graph:
            result["constraint_graph"] = {
                "nodes": [n.model_dump() for n in constraint_graph.nodes.values()],
                "edges": [e.model_dump() for e in constraint_graph.edges],
            }

        return result
