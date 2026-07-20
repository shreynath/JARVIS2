"""Phase 2 evaluator parity — EngineeringEvaluator must be externally invisible."""

from __future__ import annotations

from pathlib import Path

from core.candidates import CandidateDesign
from core.evaluation import EngineeringEvaluator, Phase1Provider
from core.ir.material import MaterialSpec
from core.reasoning.pipeline import SemanticKernelPipeline
from llm.ollama_client import DeterministicProvider

PROMPT_9000_800 = "Design a 9000 RPM naturally aspirated V12 producing 800 horsepower."
ROOT = Path(__file__).resolve().parents[1]


def _pipeline(prompt: str):
    return SemanticKernelPipeline(provider=DeterministicProvider()).run(prompt)


def _evaluator(prompt: str):
    provider = Phase1Provider(llm_provider=DeterministicProvider())
    return EngineeringEvaluator(provider=provider).evaluate(CandidateDesign.from_prompt(prompt))


def _assert_calc_parity(pipeline_result, eval_result) -> None:
    pipeline_calcs = {c.id: c for c in pipeline_result.physics_analysis.calculations}
    assert set(pipeline_calcs) == {c.id for c in eval_result.physics.calculations}
    for calc in eval_result.physics.calculations:
        ref = pipeline_calcs[calc.id]
        assert calc.result == ref.result, calc.id
        assert calc.value_range == ref.value_range, calc.id
        assert calc.passes == ref.passes, calc.id
        assert calc.knowledge_state == ref.knowledge_state, calc.id
        assert calc.confidence == ref.confidence, calc.id


def test_evaluator_matches_pipeline_v12_800hp():
    pipeline_result = _pipeline(PROMPT_9000_800)
    eval_result = _evaluator(PROMPT_9000_800)

    _assert_calc_parity(pipeline_result, eval_result)

    pipeline_materials = {
        cid: comp.material_spec
        for cid, comp in pipeline_result.graph.components.items()
        if comp.material_spec is not None
    }
    assert set(eval_result.materials) == set(pipeline_materials)
    for cid, spec in eval_result.materials.items():
        assert isinstance(spec, MaterialSpec)
        assert spec.name == pipeline_materials[cid].name
        assert spec.density_kg_m3 == pipeline_materials[cid].density_kg_m3

    assert pipeline_result.validation_report is not None
    assert eval_result.hard_violations == pipeline_result.validation_report.hard_violations
    assert eval_result.passed == pipeline_result.validation_report.passed
    assert eval_result.completeness.evaluation_complete is True
    # Unevaluated thermal hard limits only exist for evidence-gated materials without operating temps.
    pipeline_unvalidated = sum(
        1
        for e in pipeline_result.validation_report.constraint_evaluations
        if e.source == "unvalidated_hard_limit"
    )
    assert eval_result.completeness.unevaluated_hard_limits == pipeline_unvalidated
    assert eval_result.completeness.unevaluated_hard_limits >= 1
    assert len(eval_result.evidence) == len(pipeline_result.physics_analysis.calculations)


def test_parity_adversarial_a_unknown_concepts():
    prompt = (
        "Design a 9000 RPM naturally aspirated V12 producing 800 horsepower "
        "with unobtainium connecting rods and lava-cooled cylinders."
    )
    pipeline_result = _pipeline(prompt)
    eval_result = _evaluator(prompt)
    _assert_calc_parity(pipeline_result, eval_result)

    assert pipeline_result.validation_report is not None
    assert eval_result.hard_violations == pipeline_result.validation_report.hard_violations == 1
    assert "connecting_rods" not in eval_result.materials
    terms = {t["term"] for t in eval_result.requirement_spec.unrecognized_terms}
    assert "unobtainium" in terms
    assert "lava-cooled" in terms


def test_parity_adversarial_b_impossible_rpm():
    prompt = "Design a naturally aspirated 500000 RPM V12 engine producing 800 horsepower."
    pipeline_result = _pipeline(prompt)
    eval_result = _evaluator(prompt)
    _assert_calc_parity(pipeline_result, eval_result)

    assert pipeline_result.validation_report is not None
    assert eval_result.hard_violations == pipeline_result.validation_report.hard_violations
    assert eval_result.hard_violations >= 1
    assert eval_result.passed is False
    assert eval_result.requirement_spec.implausible_parameters == []
    no_material = [
        e for e in eval_result.constraints if e.id.startswith("eval_no_qualifying_material_")
    ]
    assert len(no_material) >= 1
    mps = eval_result.physics.by_id("calc_mean_piston_speed")
    assert mps is not None and mps.passes is False


def test_parity_adversarial_c_contradictory_incomplete():
    prompt = "Design a naturally aspirated turbocharged diesel engine using spark ignition."
    pipeline_result = _pipeline(prompt)
    eval_result = _evaluator(prompt)

    assert pipeline_result.validation_report is not None
    assert pipeline_result.validation_report.status == "incomplete"
    assert eval_result.validation_status == "incomplete"
    # Independent signals — do not collapse into one assertion.
    assert eval_result.completeness.evaluation_complete is False
    assert eval_result.passed is False
    assert eval_result.physics is None
    assert eval_result.materials is None
    assert pipeline_result.physics_analysis is None
    assert len(eval_result.blocking_issues) > 0
    # Blocking conflicts are incompleteness, not hard physics violations.
    assert eval_result.hard_violations == 0
    assert pipeline_result.validation_report.hard_violations == 0


def test_phase2_no_direct_engine_access():
    """Search must not exist yet; candidates must not import engines directly."""
    assert not (ROOT / "core" / "search").exists()
    assert not (ROOT / "core" / "optimization").exists()
    assert not (ROOT / "core" / "mutation").exists()

    candidates_init = (ROOT / "core" / "candidates" / "__init__.py").read_text()
    candidates_design = (ROOT / "core" / "candidates" / "candidate_design.py").read_text()
    forbidden = ("PhysicsEngine", "MaterialAssigner", "ConstraintEvaluator", "physics_engine")
    for blob in (candidates_init, candidates_design):
        for token in forbidden:
            assert token not in blob, f"candidates must not import/reference {token}"


def test_candidate_design_has_no_engineering_truth_fields():
    """CandidateDesign must never re-acquire fields EvaluationResult owns."""
    forbidden_fields = {"design_graph", "requirement_spec", "fixed_parameters"}
    model_fields = set(CandidateDesign.model_fields.keys())
    assert not (forbidden_fields & model_fields), (
        f"CandidateDesign has forbidden fields: {forbidden_fields & model_fields}"
    )


def test_candidate_mutation_is_data_only():
    """Setting variables on a candidate must not trigger evaluation or
    produce any engineering conclusion — CandidateDesign has no behavior."""
    candidate = CandidateDesign.from_prompt(PROMPT_9000_800)
    candidate.variables["max_rpm"] = 9500.0
    # No physics, no materials, no validation state exists on the candidate
    # itself — mutating it is inert until something calls EngineeringEvaluator.
    assert not hasattr(candidate, "design_graph")
    assert not hasattr(candidate, "requirement_spec")


def test_evaluator_does_not_mutate_candidate():
    """EngineeringEvaluator is a pure observer of CandidateDesign."""
    candidate = CandidateDesign.from_prompt(PROMPT_9000_800)
    candidate.variables["max_rpm"] = 9500.0
    before = candidate.model_dump()

    provider = Phase1Provider(llm_provider=DeterministicProvider())
    EngineeringEvaluator(provider=provider).evaluate(candidate)

    after = candidate.model_dump()
    assert before == after


def test_evaluation_module_has_no_engineering_formulas():
    """Manual-style audit helpers: forbid torque/BMEP formula tokens in evaluation/."""
    eval_dir = ROOT / "core" / "evaluation"
    banned = (
        "bmep",
        "torque_nm",
        "piston_speed",
        "yield_margin",
        "fatigue_margin",
        "HP_TO_KW",
        "MATERIAL_CATALOG",
    )
    for path in eval_dir.glob("*.py"):
        text = path.read_text().lower()
        for token in banned:
            assert token not in text, f"{path.name} contains engineering token {token!r}"
