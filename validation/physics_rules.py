"""Physics rules validation — material presence only.

**self_consistency_check** — warning-only for missing materials. Hard-limit
engineering constraints are evaluated exclusively via ``ConstraintEvaluator``.
Adversarial tests: ``tests/validator_adversarial/test_physics_rules_engine.py``.
"""

from __future__ import annotations

from core.ir.design_graph import EngineeringDesignGraph
from validation.integrity import stamp_validator
from validation.schema_validator import ValidationReport


class PhysicsRulesEngine:
    """Check physics-based engineering rules that are not ConstraintEvaluations."""

    VALIDATOR_ID = "PhysicsRulesEngine"

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

        # Warning-only — rejected=False unless paired with critical issues elsewhere.
        stamp_validator(report, self.VALIDATOR_ID, rejected=False)
        return report
