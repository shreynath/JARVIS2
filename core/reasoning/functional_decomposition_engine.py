"""Functional decomposition — reasoning about what the system must do before parts."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from core.ir.design_graph import EngineeringIntent
from core.ir.functional import FlowEdge, FunctionalAnalysis, RequiredAssembly, SystemFunction
from core.ir.requirement_spec import RequirementSpecification
from knowledge.functional.templates import resolve_functional_template
from llm.ollama_client import LLMProvider
from llm.structured_output import StructuredOutput

_PROMPT_DIR = Path(__file__).resolve().parents[2] / "llm" / "prompts"


class _FunctionalResponse(BaseModel):
    primary_function: str
    functions: list[SystemFunction] = Field(default_factory=list)
    flows: list[FlowEdge] = Field(default_factory=list)
    required_assemblies: list[RequiredAssembly] = Field(default_factory=list)
    required_domains: list[str] = Field(default_factory=list)


class FunctionalDecompositionEngine:
    """Analyze required functions before generating components."""

    def __init__(self, provider: LLMProvider) -> None:
        self._structured = StructuredOutput(provider)
        self._system_prompt = (_PROMPT_DIR / "functional_architect.txt").read_text()

    def analyze(
        self,
        intent: EngineeringIntent,
        requirement_spec: RequirementSpecification | None = None,
    ) -> FunctionalAnalysis:
        req_context = ""
        if requirement_spec:
            req_context = (
                f"\nRequirement spec status: {requirement_spec.status.value}\n"
                f"Resolved parameters: {requirement_spec.resolved_parameters}\n"
                f"Requirements: {requirement_spec.model_dump_json(include={'requirements'})}"
            )

        user_prompt = (
            f"Analyze the engineering functions required for:\n"
            f"Object type: {intent.object_type}\n"
            f"Design goal: {intent.design_goal}\n"
            f"Constraints: {intent.model_dump_json(include={'constraints'})}\n"
            f"Required domains hint: {intent.required_domains}"
            f"{req_context}"
        )

        try:
            response = self._structured.generate(
                self._system_prompt,
                user_prompt,
                _FunctionalResponse,
            )
            analysis = FunctionalAnalysis(
                primary_function=response.primary_function,
                functions=response.functions,
                flows=response.flows,
                required_assemblies=response.required_assemblies,
                required_domains=response.required_domains or intent.required_domains,
            )
            if self._is_valid(analysis):
                return analysis
        except (ValueError, RuntimeError):
            pass

        template = resolve_functional_template(intent.object_type, intent.raw_input)
        if template is not None:
            return template

        return FunctionalAnalysis(
            primary_function=f"Perform {intent.object_type} function",
            required_domains=intent.required_domains,
        )

    @staticmethod
    def _is_valid(analysis: FunctionalAnalysis) -> bool:
        return bool(analysis.functions and analysis.required_assemblies)
