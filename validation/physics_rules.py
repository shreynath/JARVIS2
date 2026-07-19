"""Physics rules validation — material presence only.

Hard-limit engineering constraints are evaluated exclusively via
ConstraintEvaluation (see validation/constraint_evaluator.py). This module
emits warnings for missing materials; suitability failures also flow through
ConstraintEvaluator so hard_violations have a single aggregation path.
"""

from __future__ import annotations

from core.ir.design_graph import EngineeringDesignGraph
from validation.schema_validator import ValidationReport


class PhysicsRulesEngine:
    """Check physics-based engineering rules that are not ConstraintEvaluations."""

    def validate(self, graph: EngineeringDesignGraph) -> ValidationReport:
        report = ValidationReport()

        for comp in graph.components.values():
            if not comp.material:
                report.add_issue(
                    "warning",
                    "physics",
                    f"Component '{comp.id}' has no material assigned",
                    node_id=comp.id,
                )

        return report
