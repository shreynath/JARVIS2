"""Semantic kernel pipeline — orchestrates the full Phase 1 flow."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from core.ir.constraint import CriticIssue
from core.ir.constraint_graph import ConstraintGraph
from core.ir.design_graph import EngineeringDesignGraph, EngineeringIntent
from core.ir.functional import FunctionalAnalysis
from core.ir.requirement_spec import RequirementSpecification
from core.reasoning.assumption_manager import AssumptionManager
from core.reasoning.constraint_generator import ConstraintGenerator
from core.reasoning.critic import DesignCritic
from core.reasoning.decomposition_engine import DecompositionEngine
from core.reasoning.engineer import DesignEngineer
from core.reasoning.functional_decomposition_engine import FunctionalDecompositionEngine
from core.reasoning.intent_parser import IntentParser
from core.reasoning.material_assigner import MaterialAssigner
from core.reasoning.physics_engine import PhysicsAnalysis, PhysicsEngine
from core.reasoning.requirement_compiler import RequirementCompiler
from llm.ollama_client import DeterministicProvider, LLMProvider, OllamaClient
from validation.consistency import ConsistencyChecker
from validation.constraint_evaluator import ConstraintEvaluator
from validation.physics_rules import PhysicsRulesEngine
from validation.schema_validator import SchemaValidator, ValidationReport


@dataclass
class PipelineResult:
    """Complete output of the semantic kernel pipeline."""

    intent: EngineeringIntent
    requirement_spec: RequirementSpecification
    constraint_graph: ConstraintGraph
    functional_analysis: FunctionalAnalysis
    physics_analysis: PhysicsAnalysis
    graph: EngineeringDesignGraph
    critic_issues: list[CriticIssue] = field(default_factory=list)
    validation_report: ValidationReport | None = None


class SemanticKernelPipeline:
    """Phase 1 pipeline: NL request → validated engineering design graph."""

    def __init__(self, provider: LLMProvider | None = None) -> None:
        self.provider = provider or self._default_provider()
        self.intent_parser = IntentParser(self.provider)
        self.requirement_compiler = RequirementCompiler()
        self.functional_engine = FunctionalDecompositionEngine(self.provider)
        self.decomposition_engine = DecompositionEngine(self.provider)
        self.material_assigner = MaterialAssigner()
        self.constraint_generator = ConstraintGenerator()
        self.physics_engine = PhysicsEngine()
        self.assumption_manager = AssumptionManager()
        self.critic = DesignCritic(self.provider)
        self.engineer = DesignEngineer(self.provider)
        self.schema_validator = SchemaValidator()
        self.consistency_checker = ConsistencyChecker()
        self.physics_rules = PhysicsRulesEngine()
        self.constraint_evaluator = ConstraintEvaluator()

    @staticmethod
    def _default_provider() -> LLMProvider:
        ollama = OllamaClient()
        if ollama.is_available():
            return ollama
        return DeterministicProvider()

    def run(self, user_input: str) -> PipelineResult:
        """NL entry: parse → compile → structured evaluation. Same truth path as run_from_spec."""
        intent = self.intent_parser.parse(user_input)
        requirement_spec = self.requirement_compiler.compile(intent)
        return self.run_from_spec(requirement_spec, intent)

    def run_from_spec(
        self,
        requirement_spec: RequirementSpecification,
        intent: EngineeringIntent,
    ) -> PipelineResult:
        """Structured engineering entry — single truth path after RequirementSpecification exists.

        Intent remains required for functional decomposition / assumption fill; it is not
        re-derived from the spec. Callers that patch resolved_parameters must pass a
        derived (copied) specification — never mutate a shared original.
        """
        constraint_graph = self.constraint_generator.build_graph(requirement_spec)
        functional_analysis = self.functional_engine.analyze(intent, requirement_spec)
        graph = self.decomposition_engine.decompose(intent, functional_analysis, requirement_spec)
        physics_analysis = self.physics_engine.analyze(requirement_spec)
        graph = self.material_assigner.assign(graph, requirement_spec, physics_analysis)
        material_failures = list(self.material_assigner.selection_failures)
        self.constraint_generator.add_design_nodes(constraint_graph, graph)
        self.constraint_generator.add_physics_analysis(constraint_graph, physics_analysis, requirement_spec)
        graph = self.constraint_generator.apply_to_graph(
            graph, requirement_spec, constraint_graph, functional_analysis, physics_analysis
        )
        graph = self.assumption_manager.fill_unknowns(graph, intent, requirement_spec)
        critic_issues = self.critic.review(graph)
        graph = self.engineer.repair(graph, critic_issues)
        validation_report = self._validate(
            graph, requirement_spec, physics_analysis, material_failures=material_failures
        )

        return PipelineResult(
            intent=intent,
            requirement_spec=requirement_spec,
            constraint_graph=constraint_graph,
            functional_analysis=functional_analysis,
            physics_analysis=physics_analysis,
            graph=graph,
            critic_issues=critic_issues,
            validation_report=validation_report,
        )

    def _validate(
        self,
        graph: EngineeringDesignGraph,
        requirement_spec: RequirementSpecification,
        physics_analysis: PhysicsAnalysis,
        extra_evaluations: list | None = None,
        material_failures: list | None = None,
    ) -> ValidationReport:
        report = ValidationReport()
        report.merge(self.schema_validator.validate(graph))
        report.merge(self.consistency_checker.validate(graph))
        report.merge(self.physics_rules.validate(graph))

        premise_evaluations = self._premise_evaluations(requirement_spec)
        material_evaluations = self._material_failure_evaluations(material_failures or [])
        extras = list(extra_evaluations or []) + premise_evaluations + material_evaluations

        # Hard engineering violations come ONLY from ConstraintEvaluation.
        evaluations = self.constraint_evaluator.collect(
            graph,
            physics_analysis,
            extra=extras,
        )
        self.constraint_evaluator.apply_to_report(report, evaluations)

        for decision in requirement_spec.unresolved_decisions():
            report.add_issue(
                "warning",
                "missing_decision",
                f"Missing engineering decision: {decision.question}",
                node_id="root",
            )
        for term in requirement_spec.unrecognized_terms:
            report.add_issue(
                "warning",
                "missing_decision",
                f"Unrecognized {term.get('category', 'term')}: {term.get('term')} — {term.get('reason')}",
                node_id="root",
            )
        for conflict in requirement_spec.conflicts:
            report.add_issue(
                "warning",
                "missing_decision",
                f"Requirement conflict ({conflict.get('inputs')}): {conflict.get('description')}",
                node_id="root",
            )
        for calculation in physics_analysis.calculations:
            if calculation.assumptions:
                report.add_issue(
                    "warning",
                    "assumption",
                    f"{calculation.name} depends on assumptions: {'; '.join(calculation.assumptions)}",
                    node_id="root",
                )

        if self._physics_chain_unevaluated(physics_analysis):
            missing = ", ".join(physics_analysis.unresolved_inputs) or "core operating inputs"
            report.mark_incomplete(
                f"Physics chain did not evaluate quantitatively — unresolved: {missing}. "
                "Status is incomplete (neither pass nor fail)."
            )
        return report

    @staticmethod
    def _physics_chain_unevaluated(physics_analysis: PhysicsAnalysis) -> bool:
        """True when core powertrain inputs never resolved, so derived thresholds cannot exist."""
        core_missing = any(
            key in physics_analysis.unresolved_inputs for key in ("max_rpm", "target_horsepower")
        )
        rod = physics_analysis.by_id("calc_rod_stress_requirement")
        rod_computed = (
            rod is not None
            and rod.status != "skipped"
            and (rod.result is not None or rod.value_range is not None)
        )
        return core_missing or not rod_computed

    @staticmethod
    def _material_failure_evaluations(failures: list) -> list:
        from core.ir.constraint import ConstraintEvaluation, ConstraintSeverity

        evaluations: list[ConstraintEvaluation] = []
        for failure in failures:
            best_margin = failure.get("best_limiting_margin")
            evaluations.append(
                ConstraintEvaluation(
                    id=f"eval_no_qualifying_material_{failure.get('component_id')}",
                    severity=ConstraintSeverity.HARD_LIMIT,
                    value=best_margin if best_margin is not None else "none",
                    limit=1.0,
                    passes=False,
                    source="material_assigner",
                    component_id=str(failure.get("component_id")),
                    dependency_ids=[str(failure.get("source") or "calc_rod_stress_requirement")],
                    description=str(failure.get("reason")),
                )
            )
        return evaluations

    @staticmethod
    def _premise_evaluations(requirement_spec: RequirementSpecification) -> list:
        from core.ir.constraint import ConstraintEvaluation, ConstraintSeverity

        evaluations: list[ConstraintEvaluation] = []
        for item in requirement_spec.implausible_parameters:
            evaluations.append(
                ConstraintEvaluation(
                    id=f"eval_implausible_{item.get('parameter')}",
                    severity=ConstraintSeverity.HARD_LIMIT,
                    value=item.get("value", "unknown"),
                    limit=item.get("limit"),
                    passes=False,
                    source="requirement_compiler",
                    component_id=None,
                    dependency_ids=[],
                    description=str(item.get("reason", "Implausible engineering parameter")),
                )
            )
        return evaluations

    def write_outputs(self, result: PipelineResult, output_dir: Path | str = "output") -> Path:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        graph_path = out / "engine_design_graph.json"
        graph_path.write_text(
            json.dumps(
                result.graph.to_spec_dict(
                    requirement_spec=result.requirement_spec,
                    physics_analysis=result.physics_analysis,
                    constraint_graph=result.constraint_graph,
                ),
                indent=2,
            )
        )

        spec_path = out / "requirement_specification.json"
        spec_path.write_text(json.dumps(result.requirement_spec.model_dump(), indent=2))

        physics_path = out / "physics_analysis.json"
        physics_path.write_text(json.dumps(result.physics_analysis.model_dump(), indent=2))

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
