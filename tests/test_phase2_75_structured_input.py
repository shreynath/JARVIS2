"""Phase 2.75 — structured engineering input boundary via RequirementSpecification."""

from __future__ import annotations

from pathlib import Path

from core.candidates import CandidateDesign
from core.evaluation import EngineeringEvaluator, Phase1Provider
from core.ir.material import MaterialSpec
from core.reasoning.pipeline import SemanticKernelPipeline
from llm.ollama_client import DeterministicProvider

PROMPT_9000_800 = "Design a 9000 RPM naturally aspirated V12 producing 800 horsepower."
ROOT = Path(__file__).resolve().parents[1]


def _materials_from_graph(graph) -> dict[str, MaterialSpec]:
    return {
        cid: comp.material_spec
        for cid, comp in graph.components.items()
        if comp.material_spec is not None
    }


def test_run_from_spec_matches_run_prompt_v12():
    """prompt path and structured path must converge at the same engineering truth."""
    pipeline = SemanticKernelPipeline(provider=DeterministicProvider())
    prompt_result = pipeline.run(PROMPT_9000_800)

    intent = pipeline.intent_parser.parse(PROMPT_9000_800)
    spec = pipeline.requirement_compiler.compile(intent)
    spec_result = pipeline.run_from_spec(spec, intent)

    assert prompt_result.physics_analysis.model_dump() == spec_result.physics_analysis.model_dump()
    assert prompt_result.requirement_spec.model_dump() == spec_result.requirement_spec.model_dump()
    assert prompt_result.validation_report is not None
    assert spec_result.validation_report is not None
    assert prompt_result.validation_report.model_dump() == spec_result.validation_report.model_dump()

    prompt_materials = _materials_from_graph(prompt_result.graph)
    spec_materials = _materials_from_graph(spec_result.graph)
    assert set(prompt_materials) == set(spec_materials)
    for cid, material in prompt_materials.items():
        assert material.name == spec_materials[cid].name
        assert material.density_kg_m3 == spec_materials[cid].density_kg_m3


def test_run_from_spec_does_not_mutate_input_spec():
    pipeline = SemanticKernelPipeline(provider=DeterministicProvider())
    intent = pipeline.intent_parser.parse(PROMPT_9000_800)
    spec = pipeline.requirement_compiler.compile(intent)
    before = spec.model_dump()

    pipeline.run_from_spec(spec, intent)

    assert spec.model_dump() == before


def test_evaluator_empty_variables_matches_pipeline():
    """Variables absent ⇒ evaluator == pipeline.run(prompt) (single truth path)."""
    pipeline_result = SemanticKernelPipeline(provider=DeterministicProvider()).run(PROMPT_9000_800)
    eval_result = EngineeringEvaluator(
        provider=Phase1Provider(llm_provider=DeterministicProvider())
    ).evaluate(CandidateDesign.from_prompt(PROMPT_9000_800))

    pipeline_calcs = {c.id: c for c in pipeline_result.physics_analysis.calculations}
    for calc in eval_result.physics.calculations:
        assert calc.result == pipeline_calcs[calc.id].result
    assert eval_result.hard_violations == pipeline_result.validation_report.hard_violations
    assert eval_result.passed == pipeline_result.validation_report.passed


def test_evaluator_honors_structured_variables():
    """candidate.variables patch resolved_parameters without prompt synthesis."""
    provider = Phase1Provider(llm_provider=DeterministicProvider())
    evaluator = EngineeringEvaluator(provider=provider)

    baseline = evaluator.evaluate(CandidateDesign.from_prompt(PROMPT_9000_800))
    patched = evaluator.evaluate(
        CandidateDesign(
            prompt=PROMPT_9000_800,
            variables={"max_rpm": 9500.0},
        )
    )

    assert baseline.requirement_spec.resolved_parameters.get("max_rpm") == 9000
    assert patched.requirement_spec.resolved_parameters.get("max_rpm") == 9500.0

    baseline_torque = next(c for c in baseline.physics.calculations if c.id == "calc_torque")
    patched_torque = next(c for c in patched.physics.calculations if c.id == "calc_torque")
    assert patched_torque.result != baseline_torque.result
    assert patched_torque.inputs["rpm"] == 9500.0


def test_evaluator_variable_override_does_not_mutate_base_compile():
    """Patched evaluation derives a copy; compile output for the same prompt is unchanged."""
    pipeline = SemanticKernelPipeline(provider=DeterministicProvider())
    intent = pipeline.intent_parser.parse(PROMPT_9000_800)
    base_spec = pipeline.requirement_compiler.compile(intent)
    base_before = base_spec.model_dump()

    EngineeringEvaluator(provider=Phase1Provider(llm_provider=DeterministicProvider())).evaluate(
        CandidateDesign(prompt=PROMPT_9000_800, variables={"max_rpm": 9500.0})
    )

    # Fresh compile of the same prompt must still match the pre-eval base dump shape for max_rpm.
    recompiled = pipeline.requirement_compiler.compile(intent)
    assert recompiled.resolved_parameters.get("max_rpm") == base_before["resolved_parameters"].get(
        "max_rpm"
    )
    assert base_spec.model_dump() == base_before


def test_phase275_no_search_or_prompt_synthesis():
    assert not (ROOT / "core" / "search").exists()
    assert not (ROOT / "core" / "optimization").exists()
    assert not (ROOT / "core" / "mutation").exists()

    evaluator_src = (ROOT / "core" / "evaluation" / "engineering_evaluator.py").read_text()
    assert "f\"Design" not in evaluator_src
    assert "pipeline.run(candidate.prompt)" not in evaluator_src
    assert "run_from_spec" in evaluator_src
