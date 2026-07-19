"""Constraint graph — linked requirements, constraints, and design nodes."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from core.ir.constraint import Constraint
from core.ir.requirement_spec import CompiledRequirement


class GraphNodeType(StrEnum):
    REQUIREMENT = "requirement"
    CONSTRAINT = "constraint"
    FUNCTION = "function"
    COMPONENT = "component"
    ASSEMBLY = "assembly"


class GraphEdgeType(StrEnum):
    DERIVED_FROM = "derived_from"
    CONSTRAINT_APPLIES_TO = "constraint_applies_to"
    SATISFIES = "satisfies"
    TRACES_TO = "traces_to"


class ConstraintGraphNode(BaseModel):
    id: str
    node_type: GraphNodeType
    label: str
    data: dict[str, str | float | int | bool | None] = Field(default_factory=dict)


class ConstraintGraphEdge(BaseModel):
    id: str
    source_id: str
    target_id: str
    edge_type: GraphEdgeType
    description: str = ""


class ConstraintGraph(BaseModel):
    """First-class constraint graph linking requirements to constraints and design nodes."""

    nodes: dict[str, ConstraintGraphNode] = Field(default_factory=dict)
    edges: list[ConstraintGraphEdge] = Field(default_factory=list)

    def add_node(self, node: ConstraintGraphNode) -> None:
        self.nodes[node.id] = node

    def add_edge(
        self,
        edge_id: str,
        source_id: str,
        target_id: str,
        edge_type: GraphEdgeType,
        description: str = "",
    ) -> None:
        self.edges.append(
            ConstraintGraphEdge(
                id=edge_id,
                source_id=source_id,
                target_id=target_id,
                edge_type=edge_type,
                description=description,
            )
        )

    def add_requirement(self, req: CompiledRequirement) -> None:
        self.add_node(
            ConstraintGraphNode(
                id=req.id,
                node_type=GraphNodeType.REQUIREMENT,
                label=req.description,
                data={
                    "metric": req.metric,
                    "target_value": req.target_value,
                    "unit": req.unit,
                    "priority": req.priority.value,
                    "source": req.source,
                },
            )
        )
        for parent_id in req.derived_from:
            if parent_id in self.nodes:
                self.add_edge(
                    f"edge_{req.id}_from_{parent_id}",
                    req.id,
                    parent_id,
                    GraphEdgeType.DERIVED_FROM,
                )

    def add_constraint(self, constraint: Constraint, applies_to: str | None = None) -> None:
        self.add_node(
            ConstraintGraphNode(
                id=constraint.id,
                node_type=GraphNodeType.CONSTRAINT,
                label=constraint.description,
                data={
                    "type": constraint.type,
                    "value": constraint.value,
                    "unit": constraint.unit,
                    "severity": constraint.severity.value,
                    "source": constraint.source,
                },
            )
        )
        target = applies_to or constraint.component_id or "root"
        if target in self.nodes or target == "root":
            self.add_edge(
                f"edge_{constraint.id}_applies_{target}",
                constraint.id,
                target,
                GraphEdgeType.CONSTRAINT_APPLIES_TO,
            )

    def constraints_for_node(self, node_id: str) -> list[str]:
        return [
            e.source_id
            for e in self.edges
            if e.target_id == node_id and e.edge_type == GraphEdgeType.CONSTRAINT_APPLIES_TO
        ]

    def requirements_tracing_to(self, node_id: str) -> list[str]:
        result: list[str] = []
        visited: set[str] = set()

        def _walk(current: str) -> None:
            for edge in self.edges:
                if edge.target_id == current and edge.edge_type == GraphEdgeType.TRACES_TO:
                    if edge.source_id not in visited:
                        visited.add(edge.source_id)
                        node = self.nodes.get(edge.source_id)
                        if node and node.node_type == GraphNodeType.REQUIREMENT:
                            result.append(edge.source_id)
                        _walk(edge.source_id)

        _walk(node_id)
        return result
