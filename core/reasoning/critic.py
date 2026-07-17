"""Design critic — attacks design for engineering violations."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from core.ir.constraint import CriticIssue
from core.ir.design_graph import EngineeringDesignGraph
from llm.ollama_client import LLMProvider
from llm.structured_output import StructuredOutput

_PROMPT_DIR = Path(__file__).resolve().parents[2] / "llm" / "prompts"


class _CriticResponse(BaseModel):
    issues: list[CriticIssue] = Field(default_factory=list)


class DesignCritic:
    """Review design graph for engineering problems."""

    def __init__(self, provider: LLMProvider) -> None:
        self._structured = StructuredOutput(provider)
        self._system_prompt = (_PROMPT_DIR / "critic.txt").read_text()

    def review(self, graph: EngineeringDesignGraph) -> list[CriticIssue]:
        llm_issues = self._llm_review(graph)
        rule_issues = self._rule_based_review(graph)
        return self._deduplicate(llm_issues + rule_issues)

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
        """Deterministic checks that always run, even without LLM."""
        issues: list[CriticIssue] = []
        issue_counter = 0

        unsuitable_materials = {
            "carbon fiber": ("cylinder", "combustion", "bore", "block"),
            "wood": ("engine", "cylinder", "crankshaft", "combustion"),
            "glass": ("crankshaft", "block", "bearing"),
        }

        for comp in graph.components.values():
            if not comp.material:
                continue
            mat_lower = comp.material.lower()
            for material, bad_contexts in unsuitable_materials.items():
                if material in mat_lower:
                    context = f"{comp.name} {comp.function}".lower()
                    if any(ctx in context for ctx in bad_contexts):
                        issue_counter += 1
                        issues.append(
                            CriticIssue(
                                id=f"critic_rule_{issue_counter}",
                                node_id=comp.id,
                                description=(
                                    f"{comp.material} is unsuitable for {comp.name} "
                                    f"given its function: {comp.function}"
                                ),
                                severity="critical",
                                category="material",
                                suggested_fix="Replace with appropriate high-temperature alloy or cast iron",
                            )
                        )

        return issues

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
