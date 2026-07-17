"""Intent parser — converts NL to EngineeringIntent."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from core.ir.constraint import ConstraintSpec
from core.ir.design_graph import EngineeringIntent
from core.ontology.taxonomy import EngineeringTaxonomy
from llm.ollama_client import LLMProvider
from llm.structured_output import StructuredOutput

_PROMPT_DIR = Path(__file__).resolve().parents[2] / "llm" / "prompts"


class _IntentResponse(BaseModel):
    object_type: str
    design_goal: str
    reference_objects: list[str] = Field(default_factory=list)
    constraints: list[ConstraintSpec] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    required_domains: list[str] = Field(default_factory=list)


class IntentParser:
    """Extract EngineeringIntent from natural language — not domain classification."""

    def __init__(self, provider: LLMProvider) -> None:
        self._structured = StructuredOutput(provider)
        self._system_prompt = (_PROMPT_DIR / "intent.txt").read_text()

    def parse(self, text: str) -> EngineeringIntent:
        response = self._structured.generate(
            self._system_prompt,
            text,
            _IntentResponse,
        )

        domains = list(response.required_domains)
        taxonomy = EngineeringTaxonomy.resolve_from_text(text)
        if taxonomy:
            for domain in EngineeringTaxonomy.required_domains_for(taxonomy.id):
                if domain not in domains:
                    domains.append(domain)

        return EngineeringIntent(
            object_type=response.object_type,
            design_goal=response.design_goal,
            reference_objects=response.reference_objects,
            constraints=response.constraints,
            unknowns=response.unknowns,
            required_domains=domains,
            raw_input=text,
        )
