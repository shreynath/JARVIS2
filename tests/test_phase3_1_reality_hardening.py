"""Phase 3.1 — no silent physics defaults; evidence-gated materials; role rename attack."""

from __future__ import annotations

import pytest

from core.candidates import CandidateDesign
from core.epistemology.input_requirement import MissingEngineeringInputError
from core.evaluation.variable_validator import (
    IllegalCandidateVariablesError,
    validate_candidate_variables,
)
from core.ir.requirement_spec import RequirementSpecification, SpecificationStatus
from core.materials.component_role import ComponentRole, role_for_component
from core.reasoning.material_assigner import MaterialAssigner, MaterialRequirement
from core.reasoning.physics_engine import PhysicsEngine
from core.reasoning.pipeline import SemanticKernelPipeline
from llm.ollama_client import DeterministicProvider


def test_missing_physics_inputs_are_not_defaulted():
    spec = RequirementSpecification(
        status=SpecificationStatus.INCOMPLETE,
        object_type="internal_combustion_engine",
        design_goal="test",
        resolved_parameters={},
    )
    with pytest.raises(MissingEngineeringInputError):
        PhysicsEngine().analyze(spec)


def test_aspiration_is_not_silently_defaulted():
    """Power+RPM without aspiration must not invent Naturally aspirated BMEP."""
    spec = RequirementSpecification(
        status=SpecificationStatus.INCOMPLETE,
        object_type="internal_combustion_engine",
        design_goal="test",
        resolved_parameters={
            "target_horsepower": 800,
            "max_rpm": 9000,
            "cylinder_count": 12,
        },
    )
    analysis = PhysicsEngine().analyze(spec)
    aspiration = next(r for r in analysis.input_requirements if r["name"] == "aspiration")
    assert aspiration["state"] == "unknown"
    disp = analysis.by_id("calc_displacement")
    assert disp is not None
    assert disp.status == "skipped"
    assert "aspiration" in disp.missing_inputs


def test_sweep_declares_comparison_mode():
    from scripts.run_continuity_sweeps import chain

    pipeline = SemanticKernelPipeline(provider=DeterministicProvider())
    result = pipeline.run("Design a 7000 RPM naturally aspirated V8 producing 500 horsepower.")
    row = chain(result, comparison_mode="constant_power_resized_design")
    assert "comparison_mode" in row
    assert row["comparison_mode"] == "constant_power_resized_design"


def test_material_role_not_inferred_from_name_substring():
    """thermal_fluid_nozzle must not become a piston/Titanium via the word 'piston'."""
    assert role_for_component("thermal_fluid_nozzle") == ComponentRole.THERMAL_SYSTEM
    result = SemanticKernelPipeline(provider=DeterministicProvider()).run(
        "Design a 9000 RPM naturally aspirated V12 producing 800 horsepower."
    )
    nozzle = result.graph.components.get("thermal_fluid_nozzle")
    assert nozzle is not None
    assert nozzle.material is None
    assert nozzle.material_spec is None
    # No piston-keyword role leak onto cylinder bores either.
    bores = result.graph.components["cylinder_bores"]
    assert bores.material is None


def test_material_rename_attack_preserves_decision():
    """Identical roles → identical selection regardless of component_id alias."""
    assigner = MaterialAssigner()
    requirement = MaterialRequirement(
        role=ComponentRole.STRUCTURAL_LOAD_PATH.value,
        required_yield_mpa=645.0,
        required_fatigue_mpa=335.0,
        required_temperature_c=160.0,
        mass_sensitive=True,
        source="calc_rod_stress_requirement",
        evidence_calc_ids=("calc_rod_stress_requirement",),
    )
    materials = []
    for cid in ("connecting_rods", "rod_primary", "rotating_link", "rod_piece_xyz"):
        assert role_for_component(cid) == ComponentRole.STRUCTURAL_LOAD_PATH
        selected, _ = assigner.select_material(requirement, component_id=cid)
        assert selected is not None
        materials.append(selected.name)
    assert len(set(materials)) == 1


def test_housing_without_computed_requirement_gets_no_material():
    result = SemanticKernelPipeline(provider=DeterministicProvider()).run(
        "Design a 9000 RPM naturally aspirated V12 producing 800 horsepower."
    )
    for cid in ("radiator", "oil_pan", "engine_block", "cylinder_head"):
        assert result.graph.components[cid].material is None
        assert result.graph.components[cid].material_spec is None


def test_variable_integrity_rejects_compression_ratio_accepts_max_rpm():
    pipeline = SemanticKernelPipeline(provider=DeterministicProvider())
    intent = pipeline.intent_parser.parse(
        "Design a 9000 RPM naturally aspirated V12 producing 800 horsepower."
    )
    spec = pipeline.requirement_compiler.compile(intent)

    bad = validate_candidate_variables({"compression_ratio": 20.0}, spec)
    assert bad.valid is False

    good = validate_candidate_variables({"max_rpm": 9500.0}, spec)
    assert good.valid is True

    with pytest.raises(IllegalCandidateVariablesError):
        from core.evaluation.engineering_evaluator import EngineeringEvaluator
        from core.evaluation.provider import Phase1Provider

        EngineeringEvaluator(Phase1Provider(DeterministicProvider())).evaluate(
            CandidateDesign(
                prompt="Design a 9000 RPM naturally aspirated V12 producing 800 horsepower.",
                variables={"compression_ratio": 20.0},
            )
        )
