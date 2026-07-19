"""Phase 1 provider — bundles unmodified engines for EngineeringEvaluator."""

from __future__ import annotations

from core.reasoning.pipeline import SemanticKernelPipeline
from llm.ollama_client import DeterministicProvider, LLMProvider


class Phase1Provider:
    """References to existing Phase 1 modules. No new engineering logic."""

    def __init__(self, llm_provider: LLMProvider | None = None) -> None:
        self.pipeline = SemanticKernelPipeline(provider=llm_provider or DeterministicProvider())
        self.physics_engine = self.pipeline.physics_engine
        self.material_assigner = self.pipeline.material_assigner
        self.constraint_evaluator = self.pipeline.constraint_evaluator
