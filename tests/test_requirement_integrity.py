"""Phase 3.1 — requirement integrity: contradictions block engineering."""

from __future__ import annotations

from core.candidates import CandidateDesign
from core.evaluation.engineering_evaluator import EngineeringEvaluator
from core.evaluation.evaluation_status import EvaluationStatus
from core.evaluation.provider import Phase1Provider
from core.reasoning.pipeline import SemanticKernelPipeline
from llm.ollama_client import DeterministicProvider


def evaluate(prompt: str):
    provider = Phase1Provider(DeterministicProvider())
    return EngineeringEvaluator(provider).evaluate(CandidateDesign.from_prompt(prompt))


def test_contradictory_requirements_block_engineering():
    result = evaluate(
        """
        Design a naturally aspirated turbocharged
        diesel spark ignition V12 engine.
        """
    )
    assert result.evaluation_status == EvaluationStatus.INCOMPLETE
    assert result.physics is None
    assert result.materials is None
    assert len(result.blocking_issues) > 0


def test_pipeline_contradiction_blocks_physics_and_materials():
    result = SemanticKernelPipeline(provider=DeterministicProvider()).run(
        "Design a naturally aspirated turbocharged diesel spark ignition V12 engine."
    )
    assert result.evaluation_status == EvaluationStatus.INCOMPLETE
    assert result.physics_analysis is None
    assert len(result.blocking_issues) > 0
    assert all(c.material is None for c in result.graph.components.values())
