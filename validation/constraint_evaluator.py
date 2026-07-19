"""Canonical ConstraintEvaluation collection — single source for hard violations.

Inventory of hard-constraint sources (every one must emit ConstraintEvaluation):

1. physics_engine.PhysicsCalculation.passes
   — e.g. calc_mean_piston_speed with passes=False → HARD_LIMIT evaluation
2. physics_engine.PhysicsAnalysis.constraints
   — minimum_yield_strength / minimum_temperature_limit vs material_spec
3. component Constraints of type maximum_temperature (material thermal limits)
   — compared against estimated operating temperature when available
4. MATERIAL_SUITABILITY keyword rules
   — unsuitable material for function → HARD_LIMIT evaluation

The validator never inspects these collections directly for hard_violations;
it only aggregates ConstraintEvaluation objects where severity=hard_limit and
passes=False.
"""

from __future__ import annotations

from core.ir.constraint import ConstraintEvaluation, ConstraintSeverity
from core.ir.design_graph import EngineeringDesignGraph
from core.reasoning.physics_engine import PhysicsAnalysis
from knowledge.engineering_rules.material_suitability import MATERIAL_SUITABILITY
from validation.schema_validator import ValidationReport


class ConstraintEvaluator:
    """Collect ConstraintEvaluation from every hard-constraint producer."""

    MEAN_PISTON_SPEED_HARD_LIMIT_M_S = 26.0

    def collect(
        self,
        graph: EngineeringDesignGraph,
        physics_analysis: PhysicsAnalysis | None = None,
        extra: list[ConstraintEvaluation] | None = None,
    ) -> list[ConstraintEvaluation]:
        evaluations: list[ConstraintEvaluation] = []
        if physics_analysis is not None:
            evaluations.extend(self._from_physics_calculations(physics_analysis))
            evaluations.extend(self._from_physics_constraints(graph, physics_analysis))
        evaluations.extend(self._from_component_thermal_limits(graph, physics_analysis))
        evaluations.extend(self._from_material_suitability(graph))
        if extra:
            evaluations.extend(extra)
        return evaluations

    def apply_to_report(
        self,
        report: ValidationReport,
        evaluations: list[ConstraintEvaluation],
    ) -> ValidationReport:
        """Aggregate hard/soft evaluations into ValidationReport.

        Hard violations come ONLY from ConstraintEvaluation — not from
        ad-hoc inspection of physics_analysis or constraint_graph storage.
        Unvalidated hard limits (source=unvalidated_hard_limit) emit warnings.
        """
        report.constraint_evaluations = list(evaluations)
        for evaluation in evaluations:
            if evaluation.source == "unvalidated_hard_limit":
                report.add_issue(
                    "warning",
                    "unvalidated_hard_limit",
                    evaluation.description or f"Unvalidated hard-limit constraint {evaluation.id}",
                    node_id=evaluation.component_id or evaluation.id,
                )
                continue
            if evaluation.severity != ConstraintSeverity.HARD_LIMIT:
                continue
            if evaluation.passes:
                continue
            report.add_issue(
                "critical",
                "constraint_evaluation",
                self._failure_message(evaluation),
                node_id=evaluation.component_id or evaluation.id,
            )
        return report

    @staticmethod
    def _failure_message(evaluation: ConstraintEvaluation) -> str:
        if evaluation.description:
            base = evaluation.description
        else:
            base = f"Hard-limit constraint '{evaluation.id}' failed"
        limit_text = f" (limit={evaluation.limit})" if evaluation.limit is not None else ""
        return (
            f"{base}: value={evaluation.value}{limit_text} "
            f"[source={evaluation.source}, dependencies={evaluation.dependency_ids}]"
        )

    def _from_physics_calculations(self, physics: PhysicsAnalysis) -> list[ConstraintEvaluation]:
        evaluations: list[ConstraintEvaluation] = []
        for calc in physics.calculations:
            if calc.passes is None:
                continue
            # Failed calculations are hard limits; passing calcs are soft assessments.
            severity = ConstraintSeverity.HARD_LIMIT if calc.passes is False else ConstraintSeverity.SOFT_LIMIT
            limit: float | str | None = None
            if calc.id == "calc_mean_piston_speed":
                limit = self.MEAN_PISTON_SPEED_HARD_LIMIT_M_S
            value: float | str
            if calc.value_range is not None:
                value = max(calc.value_range)
            elif calc.result is not None:
                value = calc.result
            else:
                value = "unknown"
            evaluations.append(
                ConstraintEvaluation(
                    id=f"eval_{calc.id}",
                    severity=severity,
                    value=value,
                    limit=limit,
                    passes=bool(calc.passes),
                    source="physics_engine",
                    component_id=None,
                    dependency_ids=[calc.id, *calc.dependency_ids],
                    description=(
                        calc.assessment
                        or f"Physics calculation {calc.id} {'passed' if calc.passes else 'failed'}"
                    ),
                )
            )
        return evaluations

    def _from_physics_constraints(
        self,
        graph: EngineeringDesignGraph,
        physics: PhysicsAnalysis,
    ) -> list[ConstraintEvaluation]:
        evaluations: list[ConstraintEvaluation] = []
        for constraint in physics.constraints:
            if constraint.severity != ConstraintSeverity.HARD_LIMIT:
                continue
            if constraint.value is None:
                continue
            component_id = constraint.component_id
            if not component_id or component_id not in graph.components:
                continue
            comp = graph.components[component_id]
            if not comp.material_spec:
                continue
            try:
                required = float(constraint.value)
            except (TypeError, ValueError):
                continue

            if constraint.type == "minimum_temperature_limit":
                actual = comp.material_spec.temperature_limit_c
                if actual is None:
                    continue
                passes = actual >= required
                evaluations.append(
                    ConstraintEvaluation(
                        id=f"eval_{constraint.id}",
                        severity=ConstraintSeverity.HARD_LIMIT,
                        value=actual,
                        limit=required,
                        passes=passes,
                        source="physics_engine",
                        component_id=component_id,
                        dependency_ids=[constraint.id],
                        description=(
                            f"{component_id} material temperature rating {actual:g} C "
                            f"{'meets' if passes else 'below'} required operating temperature {required:g} C"
                        ),
                    )
                )
            elif constraint.type == "minimum_yield_strength":
                actual = comp.material_spec.yield_strength_mpa
                if actual is None:
                    continue
                passes = actual >= required
                evaluations.append(
                    ConstraintEvaluation(
                        id=f"eval_{constraint.id}",
                        severity=ConstraintSeverity.HARD_LIMIT,
                        value=actual,
                        limit=required,
                        passes=passes,
                        source="physics_engine",
                        component_id=component_id,
                        dependency_ids=[constraint.id, "calc_rod_stress_requirement"],
                        description=(
                            f"{component_id} yield strength {actual:g} MPa "
                            f"{'meets' if passes else 'below'} required {required:g} MPa"
                        ),
                    )
                )
        return evaluations

    def _from_component_thermal_limits(
        self,
        graph: EngineeringDesignGraph,
        physics: PhysicsAnalysis | None,
    ) -> list[ConstraintEvaluation]:
        """Evaluate material maximum_temperature hard limits when an operating temp exists.

        Every maximum_temperature hard_limit MUST produce a ConstraintEvaluation.
        When no component-specific operating temperature calculation exists, emit an
        explicit unvalidated marker rather than silently omitting the constraint.
        """
        evaluations: list[ConstraintEvaluation] = []
        combustion_temp = None
        if physics is not None:
            if physics.by_id("calc_combustion_side_temperature") is not None:
                combustion_temp = physics.resolve_operating("combustion_side_temperature_c")

        for comp in graph.components.values():
            for constraint in comp.constraints:
                if constraint.severity != ConstraintSeverity.HARD_LIMIT:
                    continue
                if constraint.type != "maximum_temperature":
                    continue

                text = f"{comp.id} {comp.name} {comp.function}".lower()
                combustion_exposed = (
                    "camshaft" not in text
                    and "oil" not in text
                    and "cooling jet" not in text
                    and (
                        any(
                            token in text
                            for token in (
                                "piston",
                                "cylinder head",
                                "cylinder_head",
                                "exhaust",
                                "valve",
                                "combustion",
                            )
                        )
                        or "cylinder_bore" in text
                        or "cylinder bore" in text
                    )
                )

                try:
                    material_limit = float(constraint.value) if constraint.value is not None else None
                except (TypeError, ValueError):
                    material_limit = None

                if combustion_exposed and combustion_temp is not None and material_limit is not None:
                    passes = material_limit >= float(combustion_temp)
                    evaluations.append(
                        ConstraintEvaluation(
                            id=f"eval_{constraint.id}",
                            severity=ConstraintSeverity.HARD_LIMIT,
                            value=float(combustion_temp),
                            limit=material_limit,
                            passes=passes,
                            source="material_spec",
                            component_id=comp.id,
                            dependency_ids=[constraint.id, "calc_combustion_side_temperature"],
                            description=(
                                f"{comp.id} operating temperature {float(combustion_temp):g} C "
                                f"{'within' if passes else 'exceeds'} material limit {material_limit:g} C"
                            ),
                        )
                    )
                    continue

                reason = (
                    "no component-specific operating-temperature calculation exists yet "
                    "(causal traces alone are not temperatures)"
                    if combustion_temp is None or not combustion_exposed
                    else "material temperature limit value is missing or non-numeric"
                )
                evaluations.append(
                    ConstraintEvaluation(
                        id=f"eval_{constraint.id}",
                        severity=ConstraintSeverity.SOFT_LIMIT,
                        value=material_limit if material_limit is not None else "unknown",
                        limit=None,
                        passes=True,
                        source="unvalidated_hard_limit",
                        component_id=comp.id,
                        dependency_ids=[constraint.id],
                        description=(
                            f"UNVALIDATED hard_limit maximum_temperature on {comp.id}: {reason}. "
                            f"Declared material limit={constraint.value} {constraint.unit or 'C'}."
                        ),
                    )
                )
        return evaluations

    def _from_material_suitability(self, graph: EngineeringDesignGraph) -> list[ConstraintEvaluation]:
        evaluations: list[ConstraintEvaluation] = []
        counter = 0
        for comp in graph.components.values():
            if not comp.material:
                continue
            mat_lower = comp.material.lower()
            func_lower = comp.function.lower()
            for rule in MATERIAL_SUITABILITY:
                material_match = any(m in mat_lower for m in rule["materials"])
                context_match = any(c in func_lower for c in rule["unsuitable_contexts"])
                if not (material_match and context_match):
                    continue
                counter += 1
                severity = (
                    ConstraintSeverity.HARD_LIMIT
                    if rule["severity"] == "critical"
                    else ConstraintSeverity.SOFT_LIMIT
                )
                message = rule["message"].format(material=comp.material, function=comp.function)
                evaluations.append(
                    ConstraintEvaluation(
                        id=f"eval_material_suitability_{counter}_{comp.id}",
                        severity=severity,
                        value=comp.material,
                        limit="suitable_material",
                        passes=False,
                        source="material_suitability",
                        component_id=comp.id,
                        dependency_ids=[],
                        description=message,
                    )
                )
        return evaluations
