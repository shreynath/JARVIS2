"""Tests for Phase 1.1 reasoning quality."""

from core.reasoning.pipeline import SemanticKernelPipeline
from knowledge.decomposition.component_templates import GENERIC_COMPONENT_NAMES
from llm.ollama_client import DeterministicProvider


def _run_pipeline(prompt: str):
    return SemanticKernelPipeline(provider=DeterministicProvider()).run(prompt)


def test_vehicle_engine_has_assemblies_and_functions():
    result = _run_pipeline("Create a vehicle engine specification")

    assert result.functional_analysis is not None
    assert len(result.functional_analysis.functions) >= 5
    assert len(result.graph.assemblies) >= 4
    assert len(result.graph.components) >= 10

    for comp in result.graph.components.values():
        assert comp.purpose, f"{comp.id} missing purpose"
        assert comp.justification, f"{comp.id} missing justification"
        assert comp.parent_assembly_id, f"{comp.id} missing parent assembly"
        assert comp.function, f"{comp.id} missing function"
        assert comp.name.lower() not in GENERIC_COMPONENT_NAMES


def test_vehicle_engine_no_sub_component_fallback():
    result = _run_pipeline("Create a vehicle engine specification")

    for comp in result.graph.components.values():
        assert "sub component" not in comp.name.lower()
        assert comp.id != "sub_component"


def test_vehicle_engine_without_targets_is_incomplete_unevaluated():
    """No RPM/HP → physics chain skipped → incomplete, not a false pass; no invented materials."""
    result = _run_pipeline("Create a vehicle engine specification")

    assert result.validation_report is not None
    assert result.validation_report.status == "incomplete"
    assert result.validation_report.passed is False
    assert "target_horsepower" in result.physics_analysis.unresolved_inputs
    assert "max_rpm" in result.physics_analysis.unresolved_inputs
    assert all(c.material_spec is None for c in result.graph.components.values())
    assert all(c.material is None for c in result.graph.components.values() if _is_engine_role(c))


def _is_engine_role(comp) -> bool:
    text = f"{comp.id} {comp.name} {comp.function}".lower()
    return any(
        token in text
        for token in ("rod", "piston", "crank", "bearing", "camshaft", "block", "head", "housing", "radiator", "oil")
    )


def test_vehicle_engine_with_targets_materials_have_physics():
    result = _run_pipeline(
        "Design a 7000 RPM naturally aspirated V8 producing 500 horsepower."
    )

    specs = [c for c in result.graph.components.values() if c.material_spec]
    assert len(specs) >= 3
    for comp in specs:
        assert comp.material_spec.density_kg_m3 > 0
        assert comp.material_spec.name


def test_vehicle_engine_with_targets_has_constraints():
    result = _run_pipeline(
        "Design a 7000 RPM naturally aspirated V8 producing 500 horsepower."
    )

    all_constraints = []
    for comp in result.graph.components.values():
        all_constraints.extend(comp.constraints)
    for asm in result.graph.assemblies.values():
        all_constraints.extend(asm.constraints)

    assert len(all_constraints) >= 2
    typed = [c for c in all_constraints if c.value is not None and c.unit]
    assert len(typed) >= 1


def test_vehicle_engine_critic_finds_issues():
    result = _run_pipeline("Create a vehicle engine specification")
    assert len(result.critic_issues) > 0


def test_aircraft_engine_has_turbine_components():
    result = _run_pipeline("Create a commercial aircraft engine specification")

    assert result.intent.object_type == "turbofan_engine"
    assert len(result.graph.assemblies) >= 4

    component_names = {c.name.lower() for c in result.graph.components.values()}
    assert any("turbine" in n for n in component_names)
    assert any("compressor" in n or "combustor" in n for n in component_names)


def test_aircraft_engine_critic_finds_issues():
    result = _run_pipeline("Create a commercial aircraft engine specification")
    assert len(result.critic_issues) > 0


def test_gearbox_has_gear_train():
    result = _run_pipeline("Create a gearbox specification")

    assert result.intent.object_type == "gearbox"
    assembly_ids = set(result.graph.assemblies.keys())
    assert "gear_train" in assembly_ids

    component_names = {c.name.lower() for c in result.graph.components.values()}
    assert any("gear" in n for n in component_names)
    assert any("shaft" in n for n in component_names)


def test_gearbox_components_linked_to_functions():
    result = _run_pipeline("Create a gearbox specification")

    for comp in result.graph.components.values():
        assert comp.serves_function_id
        assert comp.parent_assembly_id in result.graph.assemblies


def test_gearbox_critic_finds_issues():
    result = _run_pipeline("Create a gearbox specification")
    assert len(result.critic_issues) > 0
