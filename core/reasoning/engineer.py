"""Design engineer — repair critic issues in the design graph."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from core.ir.constraint import Constraint, ConstraintSeverity, CriticIssue, Severity
from core.ir.design_graph import EngineeringDesignGraph
from llm.ollama_client import LLMProvider
from llm.structured_output import StructuredOutput

_PROMPT_DIR = Path(__file__).resolve().parents[2] / "llm" / "prompts"


class _Repair(BaseModel):
    issue_id: str
    node_id: str
    field: str
    new_value: str
    rationale: str = ""


class _EngineerResponse(BaseModel):
    repairs: list[_Repair] = Field(default_factory=list)


class DesignEngineer:
    """Apply repairs to design graph based on critic issues."""

    def __init__(self, provider: LLMProvider) -> None:
        self._structured = StructuredOutput(provider)
        self._system_prompt = (_PROMPT_DIR / "engineer.txt").read_text()

    def repair(
        self,
        graph: EngineeringDesignGraph,
        issues: list[CriticIssue],
    ) -> EngineeringDesignGraph:
        if not issues:
            return graph

        rule_repairs = self._apply_rule_repairs(graph, issues)
        remaining = [i for i in issues if i.id not in rule_repairs]

        if remaining:
            self._apply_llm_repairs(graph, remaining)

        return graph

    def _apply_rule_repairs(
        self,
        graph: EngineeringDesignGraph,
        issues: list[CriticIssue],
    ) -> set[str]:
        repaired: set[str] = set()

        for issue in issues:
            if issue.category == "completeness" and "missing purpose" in issue.description.lower():
                comp = graph.components.get(issue.node_id)
                if comp and not comp.purpose:
                    comp.purpose = f"Serve {comp.function}"
                    repaired.add(issue.id)

            elif issue.category == "completeness" and "missing justification" in issue.description.lower():
                comp = graph.components.get(issue.node_id)
                if comp and not comp.justification:
                    comp.justification = f"Required for {comp.function}"
                    repaired.add(issue.id)

            elif issue.category == "completeness" and "missing parent assembly" in issue.description.lower():
                comp = graph.components.get(issue.node_id)
                if comp and not comp.parent_assembly_id:
                    for asm in graph.assemblies.values():
                        if issue.node_id in asm.member_ids:
                            comp.parent_assembly_id = asm.id
                            repaired.add(issue.id)
                            break

            elif issue.category == "material" and "missing material" in issue.description.lower():
                # Never invent a catalog MaterialSpec. Leave unassigned until a computed
                # physics requirement exists for MaterialAssigner to evaluate.
                continue

            elif issue.category == "constraint" and "missing constraint" in issue.description.lower():
                comp = graph.components.get(issue.node_id)
                if comp and not comp.constraints:
                    comp.constraints.append(
                        Constraint(
                            id=f"repair_{issue.id}",
                            type="operating_condition",
                            description="Constraint added by engineer repair",
                            component_id=comp.id,
                            severity=ConstraintSeverity.SOFT_LIMIT,
                            source="engineer_repair",
                        )
                    )
                    repaired.add(issue.id)

            elif issue.category == "hierarchy" and "generic" in issue.description.lower():
                comp = graph.components.get(issue.node_id)
                if comp and comp.name.lower() in ("sub component", "sub_component"):
                    comp.name = f"{comp.parent_assembly_id or 'system'}_part"
                    comp.function = f"Functional element of {comp.parent_assembly_id or 'system'}"
                    comp.purpose = comp.function
                    comp.justification = "Replaced generic placeholder during repair"
                    repaired.add(issue.id)

        return repaired

    def _apply_llm_repairs(
        self,
        graph: EngineeringDesignGraph,
        issues: list[CriticIssue],
    ) -> None:
        user_prompt = (
            f"Issues:\n{[i.model_dump() for i in issues]}\n\n"
            f"Graph fragment:\n{graph.to_spec_dict()}"
        )
        try:
            response = self._structured.generate(
                self._system_prompt,
                user_prompt,
                _EngineerResponse,
            )
        except (ValueError, RuntimeError):
            return

        for repair in response.repairs:
            node = graph.components.get(repair.node_id)
            if node is None:
                continue
            if repair.field == "material" and hasattr(node, "material"):
                # Do not invent materials via LLM — MaterialAssigner owns material_spec.
                continue
            elif repair.field == "function" and hasattr(node, "function"):
                node.function = repair.new_value
            elif repair.field == "purpose" and hasattr(node, "purpose"):
                node.purpose = repair.new_value
            elif repair.field == "justification" and hasattr(node, "justification"):
                node.justification = repair.new_value
