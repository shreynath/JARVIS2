"""EngineeringEvaluator — Phase 2 firewall. Pure orchestration; zero engineering logic."""

from __future__ import annotations

from core.candidates import CandidateDesign
from core.epistemology import wrap_calculation
from core.evaluation.evaluation_result import Completeness, EvaluationResult
from core.evaluation.provider import Phase1Provider
from core.evaluation.variable_validator import (
    IllegalCandidateVariablesError,
    validate_candidate_variables,
)
from core.ir.material import MaterialSpec
from core.ir.requirement_spec import RequirementSpecification


def _derive_completeness(constraint_evaluations, evaluation_complete: bool) -> Completeness:
    """Count existing validator labels only — no new validity judgments."""
    unevaluated = [e for e in constraint_evaluations if getattr(e, "source", None) == "unvalidated_hard_limit"]
    evaluated = [e for e in constraint_evaluations if getattr(e, "source", None) != "unvalidated_hard_limit"]
    component_ids = sorted(
        {e.component_id for e in unevaluated if getattr(e, "component_id", None)}
    )
    return Completeness(
        evaluation_complete=evaluation_complete,
        evaluated_constraints=len(evaluated),
        unevaluated_hard_limits=len(unevaluated),
        unevaluated_component_ids=component_ids,
    )


def _spec_with_variable_overrides(
    spec: RequirementSpecification,
    variables: dict[str, float],
) -> RequirementSpecification:
    """Derive a new RequirementSpecification; never mutate the original."""
    if not variables:
        return spec
    return spec.model_copy(
        update={
            "resolved_parameters": {
                **spec.resolved_parameters,
                **variables,
            }
        }
    )


class EngineeringEvaluator:
    """Single entry: CandidateDesign → EvaluationResult via Phase 1 engines only."""

    def __init__(self, provider: Phase1Provider) -> None:
        self.provider = provider

    def evaluate(self, candidate: CandidateDesign) -> EvaluationResult:
        if not candidate.prompt:
            raise ValueError("CandidateDesign.from_prompt(...) required for this directive")

        # Compile from prompt, validate variable roles, then derive a patched
        # RequirementSpecification. Never synthesize a new prompt; never write
        # conclusions back onto the candidate.
        pipeline = self.provider.pipeline
        intent = pipeline.intent_parser.parse(candidate.prompt)
        base_spec = pipeline.requirement_compiler.compile(intent)

        variable_check = validate_candidate_variables(
            candidate.variables,
            base_spec,
            declared_knobs=candidate.declared_knobs,
        )
        if not variable_check.valid:
            raise IllegalCandidateVariablesError(variable_check)

        requirement_spec = _spec_with_variable_overrides(base_spec, candidate.variables)
        pipeline_result = pipeline.run_from_spec(requirement_spec, intent)

        report = pipeline_result.validation_report
        if report is None:
            raise RuntimeError("Phase 1 pipeline returned no validation_report")

        materials: dict[str, MaterialSpec] = {
            cid: comp.material_spec
            for cid, comp in pipeline_result.graph.components.items()
            if comp.material_spec is not None
        }

        constraints = list(report.constraint_evaluations)
        evidence = [wrap_calculation(calc) for calc in pipeline_result.physics_analysis.calculations]
        completeness = _derive_completeness(constraints, report.evaluation_complete)

        # Preserve Phase 1 passed semantics (incomplete ⇒ passed False even with 0 hard_violations).
        return EvaluationResult(
            physics=pipeline_result.physics_analysis,
            materials=materials,
            constraints=constraints,
            completeness=completeness,
            evidence=evidence,
            passed=report.passed,
            hard_violations=report.hard_violations,
            requirement_spec=pipeline_result.requirement_spec,
            validation_status=report.status,
        )
