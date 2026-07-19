"""Tests for functional decomposition."""

from core.reasoning.functional_decomposition_engine import FunctionalDecompositionEngine
from core.reasoning.intent_parser import IntentParser
from core.reasoning.pipeline import SemanticKernelPipeline
from llm.ollama_client import DeterministicProvider


def test_functional_decomposition_vehicle_engine():
    provider = DeterministicProvider()
    intent = IntentParser(provider).parse("Create a vehicle engine specification")
    analysis = FunctionalDecompositionEngine(provider).analyze(intent)

    assert analysis.primary_function
    assert len(analysis.functions) >= 5
    assert len(analysis.flows) >= 3
    assert len(analysis.required_assemblies) >= 4

    function_ids = {f.id for f in analysis.functions}
    for flow in analysis.flows:
        assert flow.source_function_id in function_ids
        assert flow.target_function_id in function_ids


def test_functional_decomposition_aircraft_engine():
    provider = DeterministicProvider()
    intent = IntentParser(provider).parse("Create a commercial aircraft engine specification")
    analysis = FunctionalDecompositionEngine(provider).analyze(intent)

    assert "thrust" in analysis.primary_function.lower() or any(
        "thrust" in f.name.lower() for f in analysis.functions
    )
    assembly_names = {a.name.lower() for a in analysis.required_assemblies}
    assert any("compressor" in n or "turbine" in n or "combustor" in n for n in assembly_names)


def test_functional_decomposition_gearbox():
    provider = DeterministicProvider()
    intent = IntentParser(provider).parse("Create a gearbox specification")
    analysis = FunctionalDecompositionEngine(provider).analyze(intent)

    assert any("torque" in f.name.lower() for f in analysis.functions)
    assembly_names = {a.id for a in analysis.required_assemblies}
    assert "gear_train" in assembly_names
    assert "input_shaft_assembly" in assembly_names
