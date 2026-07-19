"""Tests for Engineering Requirement Compiler."""

from core.reasoning.requirement_compiler import RequirementCompiler
from core.ir.design_graph import EngineeringIntent
from core.ir.constraint import ConstraintSpec
from core.ir.requirement_spec import SpecificationStatus, DecisionStatus


def test_vague_prompt_marks_incomplete():
    compiler = RequirementCompiler()
    intent = EngineeringIntent(
        object_type="internal_combustion_engine",
        design_goal="vehicle engine specification",
        constraints=[
            ConstraintSpec(type="performance", description="High power output"),
            ConstraintSpec(type="reliability", description="Track-capable durability"),
        ],
        unknowns=["displacement", "compression_ratio"],
        raw_input="Create a vehicle engine specification",
    )
    spec = compiler.compile(intent)

    assert spec.status == SpecificationStatus.INCOMPLETE
    assert len(spec.unresolved_decisions()) >= 4
    assert any(r.id == "req_object_type" for r in spec.requirements)
    assert any(r.id.startswith("req_unresolved_") for r in spec.requirements)
    assert all(r.originating_text for r in spec.requirements)


def test_ferrari_v12_compiles_full_spec():
    compiler = RequirementCompiler()
    intent = EngineeringIntent(
        object_type="internal_combustion_engine",
        design_goal="high performance naturally aspirated sports engine",
        reference_objects=["Ferrari V12 engines"],
        raw_input="Create a Ferrari-style V12 engine",
    )
    spec = compiler.compile(intent)

    assert spec.status == SpecificationStatus.COMPLETE
    assert spec.reference_profile == "ferrari_v12"
    assert spec.resolved_parameters["engine_architecture"] == "V12"
    assert spec.resolved_parameters["max_rpm"] == 8500
    assert spec.resolved_parameters["target_horsepower"] == 800
    assert len(spec.requirements) >= 5


def test_explicit_parameters_extracted():
    compiler = RequirementCompiler()
    intent = EngineeringIntent(
        object_type="internal_combustion_engine",
        design_goal="high rpm v8",
        raw_input="Design a 9000 RPM naturally aspirated V8 under 180kg",
    )
    spec = compiler.compile(intent)

    assert spec.resolved_parameters["max_rpm"] == 9000
    assert spec.resolved_parameters["engine_architecture"] == "V8"
    assert spec.resolved_parameters["mass_kg"] == 180
    assert any(r.metric == "max_rpm" for r in spec.requirements)


def test_horsepower_word_and_hp_units_share_extraction_path():
    compiler = RequirementCompiler()
    specs = []
    for raw_input in [
        "Design a 9000 RPM naturally aspirated V12 producing 800 horsepower.",
        "Design a 9000 RPM naturally aspirated V12 producing 800 hp",
        "Design a 9000 RPM naturally aspirated V12 producing 800 bhp",
    ]:
        specs.append(
            compiler.compile(
                EngineeringIntent(
                    object_type="internal_combustion_engine",
                    design_goal="high rpm v12",
                    raw_input=raw_input,
                )
            )
        )

    for spec in specs:
        decision = next(d for d in spec.required_decisions if d.id == "target_horsepower")
        assert spec.resolved_parameters["target_horsepower"] == 800
        assert spec.resolved_parameters["max_rpm"] == 9000
        assert decision.resolved_value == "800"


def test_unresolved_decisions_have_options():
    compiler = RequirementCompiler()
    intent = EngineeringIntent(
        object_type="internal_combustion_engine",
        design_goal="vehicle engine specification",
        raw_input="Create a vehicle engine specification",
    )
    spec = compiler.compile(intent)

    arch_decision = next(d for d in spec.required_decisions if d.id == "engine_architecture")
    assert arch_decision.status == DecisionStatus.UNRESOLVED
    assert "V8" in arch_decision.options
    assert "V12" in arch_decision.options
