"""Tests for physics engine calculations."""

from core.reasoning.physics_engine import PhysicsEngine
from core.reasoning.requirement_compiler import RequirementCompiler
from core.reasoning.material_assigner import MaterialAssigner, MaterialRequirement
from core.ir.design_graph import EngineeringIntent


def test_mean_piston_speed_calculation():
    compiler = RequirementCompiler()
    intent = EngineeringIntent(
        object_type="internal_combustion_engine",
        design_goal="Ferrari V12",
        raw_input="Create a Ferrari-style V12 engine",
    )
    spec = compiler.compile(intent)
    analysis = PhysicsEngine().analyze(spec, stroke_mm=86.0)

    calc = next(c for c in analysis.calculations if c.name == "Mean piston speed")
    assert calc.result is not None
    assert calc.unit == "m/s"
    assert calc.formula == "Vp = 2 × stroke × RPM / 60"
    expected = round(2 * 0.086 * 8500 / 60, 2)
    assert calc.result == expected


def test_recprocating_load_dependency_chain_replaces_high_rpm_threshold():
    compiler = RequirementCompiler()
    intent = EngineeringIntent(
        object_type="internal_combustion_engine",
        design_goal="high rpm v8",
        raw_input="Design a 9000 RPM naturally aspirated V8 producing 600 hp under 180kg",
    )
    spec = compiler.compile(intent)
    analysis = PhysicsEngine().analyze(spec, stroke_mm=86.0)

    assert not any("High-RPM" in c.name for c in analysis.calculations)
    acceleration = next(c for c in analysis.calculations if c.id == "calc_piston_acceleration")
    rod_loading = next(c for c in analysis.calculations if c.id == "calc_rod_loading")
    rod_stress = next(c for c in analysis.calculations if c.id == "calc_rod_stress_requirement")

    assert acceleration.result is not None
    assert rod_loading.dependency_ids == ["calc_piston_acceleration", "calc_displacement"]
    assert rod_stress.dependency_ids == ["calc_rod_loading"]
    assert rod_stress.value_range is not None


def test_physics_computes_partial_results_and_records_skips():
    compiler = RequirementCompiler()
    intent = EngineeringIntent(
        object_type="internal_combustion_engine",
        design_goal="rpm-only v12",
        raw_input="Design a 9000 RPM naturally aspirated V12 engine.",
    )
    spec = compiler.compile(intent)
    analysis = PhysicsEngine().analyze(spec)

    torque = next(c for c in analysis.calculations if c.id == "calc_torque")
    mean_piston_speed = next(c for c in analysis.calculations if c.id == "calc_mean_piston_speed")
    heat_rejection = next(c for c in analysis.calculations if c.id == "calc_heat_rejection")

    assert torque.status == "skipped"
    assert "target_horsepower" in torque.missing_inputs
    assert mean_piston_speed.status == "computed"
    assert mean_piston_speed.value_range is not None
    assert mean_piston_speed.assumptions
    assert heat_rejection.status == "skipped"
    assert heat_rejection.reason


def test_rpm_sweep_changes_continuously():
    compiler = RequirementCompiler()
    stresses = []
    for rpm in range(5000, 13001, 500):
        intent = EngineeringIntent(
            object_type="internal_combustion_engine",
            design_goal="sweep engine",
            raw_input=f"Design a {rpm} RPM naturally aspirated V8 producing 600 hp",
        )
        spec = compiler.compile(intent)
        analysis = PhysicsEngine().analyze(spec)
        stress = next(c for c in analysis.calculations if c.id == "calc_rod_stress_requirement")
        assert stress.result is not None
        stresses.append(stress.result)

    deltas = [later - earlier for earlier, later in zip(stresses, stresses[1:])]
    assert all(delta != 0 for delta in deltas)
    assert max(abs(delta) for delta in deltas) < max(stresses)


def test_material_selection_is_deterministic_and_uses_derived_requirements():
    requirement = MaterialRequirement(
        role="structural_load_path",
        required_yield_mpa=620.0,
        required_fatigue_mpa=320.0,
        required_temperature_c=160.0,
        mass_sensitive=True,
        source="calc_rod_stress_requirement",
    )
    assigner = MaterialAssigner()

    first, _ = assigner.select_material(requirement, component_id="connecting_rods")
    second, _ = assigner.select_material(requirement, component_id="connecting_rods")

    assert first is not None
    assert second is not None
    assert first.name == second.name
    assert first.selection_metrics["source"] == "calc_rod_stress_requirement"
    assert len(first.candidate_rankings) >= 2
    assert all("yield_margin" in candidate for candidate in first.candidate_rankings)


def test_material_selection_uses_threshold_then_objective():
    assigner = MaterialAssigner()
    low_load = MaterialRequirement(
        role="structural_load_path",
        required_yield_mpa=585.0,
        required_fatigue_mpa=304.0,
        required_temperature_c=160.0,
        mass_sensitive=False,
        source="calc_rod_stress_requirement",
    )
    high_load = MaterialRequirement(
        role="structural_load_path",
        required_yield_mpa=645.0,
        required_fatigue_mpa=335.0,
        required_temperature_c=160.0,
        mass_sensitive=True,
        source="calc_rod_stress_requirement",
    )

    assert assigner.select_material(low_load, component_id="connecting_rods")[0].name == "Forged Steel 4340"
    assert assigner.select_material(high_load, component_id="connecting_rods")[0].name == "Titanium 6Al-4V"
