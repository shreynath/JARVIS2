"""Semantic kernel pipeline — orchestrates the full Phase 1 flow."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from core.ir.constraint import CriticIssue
from core.ir.design_graph import EngineeringDesignGraph, EngineeringIntent
from core.reasoning.assumption_manager import AssumptionManager
from core.reasoning.critic import DesignCritic
from core.reasoning.decomposition_engine import DecompositionEngine
from core.reasoning.intent_parser import IntentParser
from llm.ollama_client import DeterministicProvider, LLMProvider, OllamaClient
from validation.consistency import ConsistencyChecker
from validation.physics_rules import PhysicsRulesEngine
from validation.schema_validator import SchemaValidator, ValidationReport


@dataclass
class PipelineResult:
    """Complete output of the semantic kernel pipeline."""

    intent: EngineeringIntent
    graph: EngineeringDesignGraph
    critic_issues: list[CriticIssue] = field(default_factory=list)
    validation_report: ValidationReport | None = None


class SemanticKernelPipeline:
    """Phase 1 pipeline: NL request → validated engineering design graph."""

    def __init__(self, provider: LLMProvider | None = None) -> None:
        self.provider = provider or self._default_provider()
        self.intent_parser = IntentParser(self.provider)
        self.decomposition_engine = DecompositionEngine(self.provider)
        self.assumption_manager = AssumptionManager()
        self.critic = DesignCritic(self.provider)
        self.schema_validator = SchemaValidator()
        self.consistency_checker = ConsistencyChecker()
        self.physics_rules = PhysicsRulesEngine()

    @staticmethod
    def _default_provider() -> LLMProvider:
        ollama = OllamaClient()
        if ollama.is_available():
            return ollama
        return DeterministicProvider()

    def run(self, user_input: str) -> PipelineResult:
        intent = self.intent_parser.parse(user_input)
        graph = self.decomposition_engine.decompose(intent)
        graph = self.assumption_manager.fill_unknowns(graph, intent)
        critic_issues = self.critic.review(graph)

        validation_report = self._validate(graph)

        return PipelineResult(
            intent=intent,
            graph=graph,
            critic_issues=critic_issues,
            validation_report=validation_report,
        )

    def _validate(self, graph: EngineeringDesignGraph) -> ValidationReport:
        report = ValidationReport()
        report.merge(self.schema_validator.validate(graph))
        report.merge(self.consistency_checker.validate(graph))
        report.merge(self.physics_rules.validate(graph))
        return report

    def write_outputs(self, result: PipelineResult, output_dir: Path | str = "output") -> Path:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        graph_path = out / "engine_design_graph.json"
        graph_path.write_text(json.dumps(result.graph.to_spec_dict(), indent=2))

        assumptions_path = out / "assumptions.json"
        assumptions_path.write_text(
            json.dumps([a.model_dump() for a in result.graph.assumptions], indent=2)
        )

        report_data = result.validation_report.model_dump() if result.validation_report else {"passed": False}
        if result.critic_issues:
            report_data["critic_issues"] = [i.model_dump() for i in result.critic_issues]

        report_path = out / "validation_report.json"
        report_path.write_text(json.dumps(report_data, indent=2))

        return out
