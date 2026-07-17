"""Physics rules validation — material suitability and contradictions."""

from __future__ import annotations

from core.ir.design_graph import EngineeringDesignGraph
from knowledge.engineering_rules.material_suitability import MATERIAL_SUITABILITY
from validation.schema_validator import ValidationReport


class PhysicsRulesEngine:
    """Check physics-based engineering rules."""

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
                continue

            self._check_material_suitability(comp.id, comp.material, comp.function, report)

        return report

    @staticmethod
    def _check_material_suitability(
        node_id: str,
        material: str,
        function: str,
        report: ValidationReport,
    ) -> None:
        mat_lower = material.lower()
        func_lower = function.lower()

        for rule in MATERIAL_SUITABILITY:
            material_match = any(m in mat_lower for m in rule["materials"])
            context_match = any(c in func_lower for c in rule["unsuitable_contexts"])
            if material_match and context_match:
                report.add_issue(
                    rule["severity"],
                    "physics",
                    rule["message"].format(material=material, function=function),
                    node_id=node_id,
                )
