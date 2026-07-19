"""Design critic — attacks design for engineering violations."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from core.ir.constraint import CriticIssue, Severity
from core.ir.design_graph import EngineeringDesignGraph
from knowledge.decomposition.component_templates import GENERIC_COMPONENT_NAMES
from knowledge.engineering_rules.material_suitability import MATERIAL_SUITABILITY
from llm.ollama_client import LLMProvider
from llm.structured_output import StructuredOutput

_PROMPT_DIR = Path(__file__).resolve().parents[2] / "llm" / "prompts"


class _CriticResponse(BaseModel):
    issues: list[CriticIssue] = Field(default_factory=list)


class DesignCritic:
    """Review design graph for engineering problems — must always find issues."""

    def __init__(self, provider: LLMProvider) -> None:
        self._structured = StructuredOutput(provider)
        self._system_prompt = (_PROMPT_DIR / "critic.txt").read_text()

    def review(self, graph: EngineeringDesignGraph) -> list[CriticIssue]:
        rule_issues = self._rule_based_review(graph)
        llm_issues = self._llm_review(graph)
        combined = self._deduplicate(rule_issues + llm_issues)

        if not combined:
            combined.append(
                CriticIssue(
                    id="critic_baseline_1",
                    node_id=graph.root_id,
                    description=(
                        "Design lacks quantified performance targets — "
                        "displacement, power output, and operating envelope unspecified"
                    ),
                    severity=Severity.WARNING,
                    category="completeness",
                    suggested_fix="Add performance constraints with values and units",
                )
            )
        return combined

    def _llm_review(self, graph: EngineeringDesignGraph) -> list[CriticIssue]:
        user_prompt = f"Review this design graph:\n{graph.to_spec_dict()}"
        try:
            response = self._structured.generate(
                self._system_prompt,
                user_prompt,
                _CriticResponse,
            )
            return response.issues
        except (ValueError, RuntimeError):
            return []

    def _rule_based_review(self, graph: EngineeringDesignGraph) -> list[CriticIssue]:
        issues: list[CriticIssue] = []
        counter = 0

        if not graph.assemblies:
            counter += 1
            issues.append(
                CriticIssue(
                    id=f"critic_rule_{counter}",
                    node_id=graph.root_id,
                    description="Design has no assemblies — flat component list lacks engineering hierarchy",
                    severity=Severity.CRITICAL,
                    category="hierarchy",
                    suggested_fix="Organize components into functional assemblies",
                )
            )

        for comp in graph.components.values():
            if comp.name.lower() in GENERIC_COMPONENT_NAMES or comp.id.lower() in GENERIC_COMPONENT_NAMES:
                counter += 1
                issues.append(
                    CriticIssue(
                        id=f"critic_rule_{counter}",
                        node_id=comp.id,
                        description=f"Generic placeholder component '{comp.name}' — not a real engineering part",
                        severity=Severity.CRITICAL,
                        category="hierarchy",
                        suggested_fix="Replace with function-specific component from knowledge base",
                    )
                )

            if not comp.purpose:
                counter += 1
                issues.append(
                    CriticIssue(
                        id=f"critic_rule_{counter}",
                        node_id=comp.id,
                        description=f"Component '{comp.name}' missing purpose",
                        severity=Severity.WARNING,
                        category="completeness",
                        suggested_fix="Add purpose describing why this component exists",
                    )
                )

            if not comp.justification:
                counter += 1
                issues.append(
                    CriticIssue(
                        id=f"critic_rule_{counter}",
                        node_id=comp.id,
                        description=f"Component '{comp.name}' missing justification",
                        severity=Severity.WARNING,
                        category="completeness",
                        suggested_fix="Add justification linking component to system function",
                    )
                )

            if not comp.parent_assembly_id:
                counter += 1
                issues.append(
                    CriticIssue(
                        id=f"critic_rule_{counter}",
                        node_id=comp.id,
                        description=f"Component '{comp.name}' missing parent assembly",
                        severity=Severity.WARNING,
                        category="completeness",
                        suggested_fix="Assign component to a parent assembly",
                    )
                )

            if comp.material and not comp.material_spec:
                counter += 1
                issues.append(
                    CriticIssue(
                        id=f"critic_rule_{counter}",
                        node_id=comp.id,
                        description=(
                            f"Component '{comp.name}' has material name but no physics properties "
                            f"(density, yield strength, thermal conductivity)"
                        ),
                        severity=Severity.WARNING,
                        category="material",
                        suggested_fix="Assign MaterialSpec from catalog with physics properties",
                    )
                )

            if comp.material:
                self._check_material_suitability(comp.id, comp.material, comp.function, issues, counter)
                counter = len(issues)

        self._check_missing_systems(graph, issues)
        self._check_missing_constraints(graph, issues)
        self._check_unrealistic_assumptions(graph, issues)

        return issues

    @staticmethod
    def _check_material_suitability(
        node_id: str,
        material: str,
        function: str,
        issues: list[CriticIssue],
        counter: int,
    ) -> None:
        mat_lower = material.lower()
        func_lower = function.lower()
        for rule in MATERIAL_SUITABILITY:
            material_match = any(m in mat_lower for m in rule["materials"])
            context_match = any(c in func_lower for c in rule["unsuitable_contexts"])
            if material_match and context_match:
                counter += 1
                issues.append(
                    CriticIssue(
                        id=f"critic_rule_{counter}",
                        node_id=node_id,
                        description=rule["message"].format(material=material, function=function),
                        severity=Severity.CRITICAL,
                        category="material",
                        suggested_fix="Replace with appropriate high-temperature alloy or cast iron",
                    )
                )

    @staticmethod
    def _check_missing_systems(graph: EngineeringDesignGraph, issues: list[CriticIssue]) -> None:
        counter = len(issues)
        object_type = graph.type.lower()
        raw = graph.intent.raw_input.lower()

        if "engine" in object_type or "engine" in raw:
            expected = {"fuel", "cooling", "lubrication", "electrical", "combustor", "turbine", "compressor", "fan"}
            present = {a.name.lower() for a in graph.assemblies.values()}
            present.update(c.name.lower() for c in graph.components.values())

            if "aircraft" in raw or "turbofan" in raw:
                required = {"compressor", "combustor", "turbine", "fan"}
            else:
                required = {"fuel", "cooling", "lubrication"}

            for req in required:
                if not any(req in p for p in present):
                    counter += 1
                    issues.append(
                        CriticIssue(
                            id=f"critic_rule_{counter}",
                            node_id=graph.root_id,
                            description=f"Missing expected system: {req}",
                            severity=Severity.WARNING,
                            category="completeness",
                            suggested_fix=f"Add {req} assembly identified by functional analysis",
                        )
                    )

    @staticmethod
    def _check_missing_constraints(graph: EngineeringDesignGraph, issues: list[CriticIssue]) -> None:
        counter = len(issues)
        has_any_constraint = any(c.constraints for c in graph.components.values())
        has_any_constraint |= any(a.constraints for a in graph.assemblies.values())

        if not has_any_constraint:
            counter += 1
            issues.append(
                CriticIssue(
                    id=f"critic_rule_{counter}",
                    node_id=graph.root_id,
                    description="Design has no quantified constraints — simulation cannot proceed",
                    severity=Severity.CRITICAL,
                    category="constraint",
                    suggested_fix="Add constraints with type, value, unit, and severity",
                )
            )

        for spec in graph.intent.constraints:
            if spec.value is None:
                counter += 1
                issues.append(
                    CriticIssue(
                        id=f"critic_rule_{counter}",
                        node_id=graph.root_id,
                        description=f"Intent constraint '{spec.type}' has no quantified value",
                        severity=Severity.WARNING,
                        category="constraint",
                        suggested_fix=f"Quantify {spec.type} with value and unit",
                    )
                )

    @staticmethod
    def _check_unrealistic_assumptions(graph: EngineeringDesignGraph, issues: list[CriticIssue]) -> None:
        counter = len(issues)
        for assumption in graph.assumptions:
            if assumption.confidence < 0.3:
                counter += 1
                issues.append(
                    CriticIssue(
                        id=f"critic_rule_{counter}",
                        node_id=graph.root_id,
                        description=(
                            f"Low-confidence assumption for '{assumption.field}': "
                            f"{assumption.assumed_value} (confidence {assumption.confidence})"
                        ),
                        severity=Severity.WARNING,
                        category="assumption",
                        suggested_fix=f"Validate or specify {assumption.field} from requirements",
                    )
                )

    @staticmethod
    def _deduplicate(issues: list[CriticIssue]) -> list[CriticIssue]:
        seen: set[str] = set()
        unique: list[CriticIssue] = []
        for issue in issues:
            key = f"{issue.node_id}:{issue.description}"
            if key not in seen:
                seen.add(key)
                unique.append(issue)
        return unique
