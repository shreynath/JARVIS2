"""Semantic kernel pipeline — orchestrates the full Phase 1 flow."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from core.evaluation.issue import Issue
from core.evaluation.evaluation_status import EvaluationStatus
from core.evaluation.requirement_integrity import blocking_issues_from_spec
from core.epistemology.input_requirement import MissingEngineeringInputError
from core.ir.constraint import CriticIssue
from core.ir.constraint_graph import ConstraintGraph
from core.ir.design_graph import EngineeringDesignGraph, EngineeringIntent
from core.ir.functional import FunctionalAnalysis
from core.ir.requirement_spec import RequirementSpecification
from core.reasoning.domain_dispatch import (
    is_bridge_object_type,
    is_ice_request,
    physics_handler_for,
)
from core.materials.structural_completeness import unassigned_structural_components
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

DEGRADED_WARNING = (
    "⚠ Ollama unavailable — this is a template-derived stub answer, not a real analysis."
)

EXPLICIT_DETERMINISTIC_WARNING = (
    "⚠ DeterministicProvider in use — template-derived stub answer, not a real analysis."
)


class PipelineError(Exception):
    """Clean, typed failure from the semantic kernel (never a raw traceback to users)."""

    def __init__(self, message: str, *, code: str = "pipeline_error") -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class PipelineResult:
    """Complete output of the semantic kernel pipeline."""

    intent: EngineeringIntent
    requirement_spec: RequirementSpecification
    constraint_graph: ConstraintGraph
    functional_analysis: FunctionalAnalysis
    physics_analysis: PhysicsAnalysis | None
    graph: EngineeringDesignGraph
    critic_issues: list[CriticIssue] = field(default_factory=list)
    validation_report: ValidationReport | None = None
    evaluation_status: EvaluationStatus = EvaluationStatus.COMPLETE
    blocking_issues: list[Issue] = field(default_factory=list)
    # Option-1 transparent degraded mode — never silent about provider choice.
    provider_used: str = "unknown"
    degraded: bool = False
    warning: str | None = None


class SemanticKernelPipeline:
    """Phase 1 pipeline: NL request → validated engineering design graph.

    Provider policy (Option 1 — transparent degraded mode):
    If no provider is passed and Ollama is unreachable, the pipeline falls back
    to ``DeterministicProvider`` but every ``PipelineResult``, CLI print, and
    JSON artifact records ``provider_used``, ``degraded=True``, and a plain-
    language ``warning``. ``DeterministicProvider`` is a test fixture; see its
    module docstring and ARCHITECTURE.md.
    """

    def __init__(self, provider: LLMProvider | None = None) -> None:
        if provider is None:
            self.provider, self.provider_used, self.degraded, self.warning = (
                self._default_provider()
            )
        else:
            self.provider = provider
            self.provider_used = provider.provider_label()
            self.degraded = isinstance(provider, DeterministicProvider)
            self.warning = EXPLICIT_DETERMINISTIC_WARNING if self.degraded else None

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
    def _default_provider() -> tuple[LLMProvider, str, bool, str | None]:
        ollama = OllamaClient()
        if ollama.is_available():
            return ollama, ollama.provider_label(), False, None
        return (
            DeterministicProvider(),
            "deterministic_fallback",
            True,
            DEGRADED_WARNING,
        )

    def _attach_provider_meta(self, result: PipelineResult) -> PipelineResult:
        result.provider_used = self.provider_used
        result.degraded = self.degraded
        result.warning = self.warning
        return result

    def provider_status_dict(self) -> dict[str, str | bool | None]:
        return {
            "provider_used": self.provider_used,
            "degraded": self.degraded,
            "warning": self.warning,
        }

    def run(self, user_input: str) -> PipelineResult:
        """NL entry: parse → compile → structured evaluation. Same truth path as run_from_spec."""
        if user_input is None or not str(user_input).strip():
            raise PipelineError("No input provided.", code="empty_input")
        try:
            intent = self.intent_parser.parse(user_input)
            requirement_spec = self.requirement_compiler.compile(intent)
            return self.run_from_spec(requirement_spec, intent)
        except PipelineError:
            raise
        except Exception as exc:  # noqa: BLE001 — convert to typed surface error
            raise PipelineError(
                f"Pipeline failed for input: {exc}",
                code="unhandled_pipeline_failure",
            ) from exc

    def run_from_spec(
        self,
        requirement_spec: RequirementSpecification,
        intent: EngineeringIntent,
    ) -> PipelineResult:
        """Structured engineering entry — single truth path after RequirementSpecification exists.

        Intent remains required for functional decomposition / assumption fill; it is not
        re-derived from the spec. Callers that patch resolved_parameters must pass a
        derived (copied) specification — never mutate a shared original.

        Contradictions block evaluation: no physics, materials, or validation conclusions.
        """
        blocking = blocking_issues_from_spec(requirement_spec)
        if blocking:
            empty_graph = EngineeringDesignGraph(
                name="blocked_evaluation",
                type=intent.object_type or "unknown",
                intent=intent,
                root_id="root",
            )
            report = ValidationReport()
            report.mark_incomplete(
                "Requirement contradictions block engineering evaluation — "
                "physics and materials were not computed."
            )
            for issue in blocking:
                report.add_issue(
                    "warning",
                    "requirement_conflict",
                    issue.message,
                    node_id="root",
                )
            return self._attach_provider_meta(
                PipelineResult(
                    intent=intent,
                    requirement_spec=requirement_spec,
                    constraint_graph=ConstraintGraph(),
                    functional_analysis=FunctionalAnalysis(
                        primary_function="blocked_by_requirement_conflict",
                    ),
                    physics_analysis=None,
                    graph=empty_graph,
                    critic_issues=[],
                    validation_report=report,
                    evaluation_status=EvaluationStatus.INCOMPLETE,
                    blocking_issues=blocking,
                )
            )

        constraint_graph = self.constraint_generator.build_graph(requirement_spec)
        functional_analysis = self.functional_engine.analyze(intent, requirement_spec)
        graph = self.decomposition_engine.decompose(intent, functional_analysis, requirement_spec)
        physics_analysis = self._run_physics(intent, requirement_spec)
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

        status = EvaluationStatus.COMPLETE
        if validation_report is not None and not validation_report.evaluation_complete:
            status = EvaluationStatus.INCOMPLETE
        elif validation_report is not None and validation_report.hard_violations > 0:
            status = EvaluationStatus.FAILED

        return self._attach_provider_meta(
            PipelineResult(
                intent=intent,
                requirement_spec=requirement_spec,
                constraint_graph=constraint_graph,
                functional_analysis=functional_analysis,
                physics_analysis=physics_analysis,
                graph=graph,
                critic_issues=critic_issues,
                validation_report=validation_report,
                evaluation_status=status,
                blocking_issues=[],
            )
        )

    def _run_physics(
        self,
        intent: EngineeringIntent,
        requirement_spec: RequirementSpecification,
    ) -> PhysicsAnalysis:
        """Domain-conditional physics — ICE engine is not assumed for every request."""
        handler = physics_handler_for(intent.object_type)
        if handler is not None:
            try:
                return handler(requirement_spec)
            except MissingEngineeringInputError as exc:
                analysis = PhysicsAnalysis()
                analysis.unresolved_inputs = ["resolved_parameters"]
                analysis.warnings.append(str(exc))
                return analysis

        if is_ice_request(intent.object_type, intent.raw_input):
            try:
                return self.physics_engine.analyze(requirement_spec)
            except MissingEngineeringInputError as exc:
                analysis = PhysicsAnalysis()
                analysis.unresolved_inputs = ["resolved_parameters"]
                analysis.warnings.append(str(exc))
                return analysis

        analysis = PhysicsAnalysis()
        analysis.warnings.append(
            f"No physics module registered for object_type={intent.object_type!r}; "
            "ICE PhysicsEngine was not invoked."
        )
        return analysis

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
        for calculation in physics_analysis.calculations:
            if calculation.assumptions:
                report.add_issue(
                    "warning",
                    "assumption",
                    f"{calculation.name} depends on assumptions: {'; '.join(calculation.assumptions)}",
                    node_id="root",
                )

        if self._physics_chain_unevaluated(physics_analysis, requirement_spec):
            missing = ", ".join(physics_analysis.unresolved_inputs) or "core operating inputs"
            report.mark_incomplete(
                f"Physics chain did not evaluate quantitatively — unresolved: {missing}. "
                "Status is incomplete (neither pass nor fail)."
            )

        missing_structural = unassigned_structural_components(graph)
        if missing_structural:
            ids = ", ".join(missing_structural)
            report.mark_incomplete(
                f"Structural/load-bearing components lack assigned materials: {ids}. "
                "Evaluation cannot be COMPLETE until all structural members have evidence-gated materials."
            )
        return report

    @staticmethod
    def _physics_chain_unevaluated(
        physics_analysis: PhysicsAnalysis,
        requirement_spec: RequirementSpecification | None = None,
    ) -> bool:
        """True when ICE powertrain inputs never resolved so derived thresholds cannot exist.

        Non-ICE domains do not use the rod-stress chain; skipping ICE physics is not
        treated as an incomplete ICE evaluation.
        """
        object_type = requirement_spec.object_type if requirement_spec is not None else None
        if object_type and is_bridge_object_type(object_type):
            if physics_analysis.unresolved_inputs:
                return True
            truss = physics_analysis.by_id("calc_truss_member_stress")
            truss_computed = (
                truss is not None
                and truss.status != "skipped"
                and (truss.result is not None or truss.value_range is not None)
            )
            return not truss_computed

        if object_type and not is_ice_request(object_type, None):
            # Domain without ICE physics — incomplete only if a registered handler failed.
            return False

        # If ICE physics was never attempted (empty analysis with skip warning), still
        # only apply rod-chain incompleteness when this is an ICE object.
        if object_type is None and not physics_analysis.calculations:
            # Conservative: if we have no object type and no calcs, don't force ICE incompleteness
            # unless unresolved ICE inputs were recorded.
            if not physics_analysis.unresolved_inputs:
                return False

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

    def _inject_provider_meta(self, payload: dict) -> dict:
        """Ensure every written JSON artifact surfaces provider / degradation status."""
        meta = self.provider_status_dict()
        # Prefer result-level fields already on PipelineResult when present on payload.
        payload.setdefault("provider_used", meta["provider_used"])
        payload.setdefault("degraded", meta["degraded"])
        payload.setdefault("warning", meta["warning"])
        return payload

    def write_outputs(self, result: PipelineResult, output_dir: Path | str = "output") -> Path:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        status = {
            "provider_used": result.provider_used,
            "degraded": result.degraded,
            "warning": result.warning,
            "evaluation_status": result.evaluation_status.value,
        }
        (out / "pipeline_status.json").write_text(json.dumps(status, indent=2))

        graph_payload = result.graph.to_spec_dict(
            requirement_spec=result.requirement_spec,
            physics_analysis=result.physics_analysis,
            constraint_graph=result.constraint_graph,
        )
        graph_path = out / "engine_design_graph.json"
        graph_path.write_text(json.dumps(self._inject_provider_meta(graph_payload), indent=2))

        spec_payload = result.requirement_spec.model_dump()
        spec_path = out / "requirement_specification.json"
        spec_path.write_text(json.dumps(self._inject_provider_meta(spec_payload), indent=2))

        physics_payload = (
            result.physics_analysis.model_dump()
            if result.physics_analysis is not None
            else {"status": "blocked", "reason": "evaluation incomplete — physics not run"}
        )
        physics_path = out / "physics_analysis.json"
        physics_path.write_text(json.dumps(self._inject_provider_meta(physics_payload), indent=2))

        assumptions_payload = {
            "assumptions": [a.model_dump() for a in result.graph.assumptions],
        }
        assumptions_path = out / "assumptions.json"
        assumptions_path.write_text(
            json.dumps(self._inject_provider_meta(assumptions_payload), indent=2)
        )

        report_data = result.validation_report.model_dump() if result.validation_report else {"passed": False}
        report_data["evaluation_status"] = result.evaluation_status.value
        report_data["blocking_issues"] = [
            {"code": i.code, "message": i.message, "severity": i.severity, "field": i.field}
            for i in result.blocking_issues
        ]
        if result.critic_issues:
            report_data["critic_issues"] = [i.model_dump() for i in result.critic_issues]

        report_path = out / "validation_report.json"
        report_path.write_text(json.dumps(self._inject_provider_meta(report_data), indent=2))

        return out
