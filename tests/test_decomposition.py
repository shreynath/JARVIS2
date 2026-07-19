"""Tests for recursive decomposition."""

from core.reasoning.decomposition_engine import DecompositionEngine
from core.reasoning.functional_decomposition_engine import FunctionalDecompositionEngine
from core.reasoning.intent_parser import IntentParser
from llm.ollama_client import DeterministicProvider


def _decompose(prompt: str):
    provider = DeterministicProvider()
    intent = IntentParser(provider).parse(prompt)
    analysis = FunctionalDecompositionEngine(provider).analyze(intent)
    return DecompositionEngine(provider).decompose(intent, analysis)


def test_decomposition_produces_hierarchy():
    graph = _decompose("Create a vehicle engine specification")

    assert graph.root_id == "root"
    assert "root" in graph.assemblies
    assert len(graph.assemblies) > 1
    assert len(graph.components) > 1


def test_decomposition_all_children_exist():
    graph = _decompose("Create a vehicle engine specification")

    all_ids = graph.all_node_ids()
    for assembly in graph.assemblies.values():
        for child_id in assembly.children:
            assert child_id in all_ids, f"Undefined assembly child: {child_id}"
        for member_id in assembly.member_ids:
            assert member_id in all_ids, f"Undefined member: {member_id}"


def test_decomposition_has_leaf_nodes():
    graph = _decompose("Create a vehicle engine specification")

    leaves = [c for c in graph.components.values() if c.is_leaf]
    assert len(leaves) > 0


def test_decomposition_no_generic_components():
    graph = _decompose("Create a vehicle engine specification")

    for comp in graph.components.values():
        assert comp.name.lower() != "sub component"
        assert comp.parent_assembly_id is not None
