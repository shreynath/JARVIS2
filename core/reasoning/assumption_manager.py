"""Assumption manager — records unknowns without inventing constraints."""

from __future__ import annotations

from core.ir.constraint import Assumption
from core.ir.design_graph import EngineeringDesignGraph, EngineeringIntent
from core.ir.requirement_spec import RequirementSpecification, SpecificationStatus


class AssumptionManager:
    """Fill unknowns from intent — only document assumptions when spec is complete."""

    def fill_unknowns(
        self,
        graph: EngineeringDesignGraph,
        intent: EngineeringIntent,
        requirement_spec: RequirementSpecification | None = None,
    ) -> EngineeringDesignGraph:
        if requirement_spec and requirement_spec.status == SpecificationStatus.INCOMPLETE:
            graph.assumptions = [
                Assumption(
                    id=f"assumption_{i + 1}",
                    field=decision.id,
                    assumed_value="UNRESOLVED",
                    rationale=decision.question,
                    confidence=0.0,
                    source="requirement_compiler",
                )
                for i, decision in enumerate(requirement_spec.unresolved_decisions())
            ]
            return graph

        assumptions: list[Assumption] = []
        resolved = requirement_spec.resolved_parameters if requirement_spec else {}

        for i, unknown in enumerate(intent.unknowns):
            if unknown in resolved:
                assumptions.append(
                    Assumption(
                        id=f"assumption_{i + 1}",
                        field=unknown,
                        assumed_value=str(resolved[unknown]),
                        rationale="Resolved from requirement specification",
                        confidence=0.8,
                        source="requirement_compiler",
                    )
                )
            else:
                assumptions.append(
                    Assumption(
                        id=f"assumption_{i + 1}",
                        field=unknown,
                        assumed_value="to be determined",
                        rationale=f"No value available for {unknown}",
                        confidence=0.2,
                    )
                )

        graph.assumptions = assumptions
        return graph
