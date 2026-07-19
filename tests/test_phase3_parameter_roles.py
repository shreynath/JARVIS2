"""Phase 3.0 — parameter role registry / candidate variable semantics."""

from __future__ import annotations

import pytest

from core.candidates import CandidateDesign, ParameterProvenance, ParameterRole
from core.evaluation import (
    EngineeringEvaluator,
    IllegalCandidateVariablesError,
    Phase1Provider,
    validate_candidate_variables,
)
from core.reasoning.pipeline import SemanticKernelPipeline
from llm.ollama_client import DeterministicProvider

PROMPT_9000_800 = "Design a 9000 RPM naturally aspirated V12 producing 800 horsepower."
PROMPT_5_5L_V12 = "Design a 5.5L naturally aspirated V12 producing 800 horsepower."
PROMPT_800HP_V12 = "Design an 800hp naturally aspirated V12."


def _evaluator() -> EngineeringEvaluator:
    return EngineeringEvaluator(provider=Phase1Provider(llm_provider=DeterministicProvider()))


def _compile(prompt: str):
    pipeline = SemanticKernelPipeline(provider=DeterministicProvider())
    intent = pipeline.intent_parser.parse(prompt)
    return pipeline.requirement_compiler.compile(intent)


def test_valid_knob_max_rpm_accepted():
    candidate = CandidateDesign(prompt=PROMPT_9000_800, variables={"max_rpm": 12000.0})
    result = _evaluator().evaluate(candidate)
    assert result.requirement_spec.resolved_parameters["max_rpm"] == 12000.0
    torque = next(c for c in result.physics.calculations if c.id == "calc_torque")
    assert torque.inputs["rpm"] == 12000.0


def test_derived_output_rejected():
    candidate = CandidateDesign(prompt=PROMPT_9000_800, variables={"torque_nm": 1000.0})
    with pytest.raises(IllegalCandidateVariablesError) as exc_info:
        _evaluator().evaluate(candidate)
    assert "torque_nm" in exc_info.value.result.illegal_variables
    claim = next(c for c in exc_info.value.result.claims if c.name == "torque_nm")
    assert claim.role == ParameterRole.DERIVED_OUTPUT


def test_assumption_internal_rejected():
    candidate = CandidateDesign(
        prompt=PROMPT_9000_800,
        variables={"bore_stroke_ratio": 1.2},
    )
    with pytest.raises(IllegalCandidateVariablesError) as exc_info:
        _evaluator().evaluate(candidate)
    assert "bore_stroke_ratio" in exc_info.value.result.illegal_variables
    claim = next(c for c in exc_info.value.result.claims if c.name == "bore_stroke_ratio")
    assert claim.role == ParameterRole.ASSUMPTION_INTERNAL


def test_out_of_model_compression_ratio_rejected():
    candidate = CandidateDesign(
        prompt=PROMPT_9000_800,
        variables={"compression_ratio": 13.0},
    )
    with pytest.raises(IllegalCandidateVariablesError) as exc_info:
        _evaluator().evaluate(candidate)
    assert "compression_ratio" in exc_info.value.result.illegal_variables
    claim = next(c for c in exc_info.value.result.claims if c.name == "compression_ratio")
    assert claim.role == ParameterRole.OUT_OF_MODEL


def test_dual_role_displacement_known_fixed_rejects_mutation():
    """Case A: explicit 5.5L → FIXED_REQUIREMENT; mutation rejected."""
    spec = _compile(PROMPT_5_5L_V12)
    assert "displacement_l" in spec.resolved_parameters

    result = validate_candidate_variables(
        {"displacement_l": 6.0},
        spec,
        declared_knobs=[],
    )
    assert result.valid is False
    claim = result.claims[0]
    assert claim.role == ParameterRole.FIXED_REQUIREMENT
    assert claim.provenance == ParameterProvenance.KNOWN

    with pytest.raises(IllegalCandidateVariablesError):
        _evaluator().evaluate(
            CandidateDesign(prompt=PROMPT_5_5L_V12, variables={"displacement_l": 6.0})
        )


def test_dual_role_displacement_absent_assumed_rejects_mutation():
    """Case B: no displacement in prompt → ASSUMPTION_INTERNAL; mutation rejected."""
    spec = _compile(PROMPT_800HP_V12)
    assert "displacement_l" not in spec.resolved_parameters

    result = validate_candidate_variables(
        {"displacement_l": 5.5},
        spec,
        declared_knobs=[],
    )
    assert result.valid is False
    claim = result.claims[0]
    assert claim.role == ParameterRole.ASSUMPTION_INTERNAL
    assert claim.provenance == ParameterProvenance.ASSUMED

    with pytest.raises(IllegalCandidateVariablesError):
        _evaluator().evaluate(
            CandidateDesign(prompt=PROMPT_800HP_V12, variables={"displacement_l": 5.5})
        )


def test_dual_role_displacement_declared_knob_allowed():
    """Case C: study declares optimize displacement → OPTIMIZATION_KNOB."""
    candidate = CandidateDesign(
        prompt=PROMPT_800HP_V12,
        variables={"displacement_l": 5.5},
        declared_knobs=["displacement_l"],
    )
    result = _evaluator().evaluate(candidate)
    assert result.requirement_spec.resolved_parameters["displacement_l"] == 5.5


def test_candidate_design_still_has_no_engineering_truth_fields():
    forbidden = {"design_graph", "requirement_spec", "fixed_parameters"}
    assert not (forbidden & set(CandidateDesign.model_fields.keys()))


def test_empty_variables_still_valid():
    assert validate_candidate_variables({}, _compile(PROMPT_9000_800)).valid is True
    result = _evaluator().evaluate(CandidateDesign.from_prompt(PROMPT_9000_800))
    assert result.requirement_spec is not None
