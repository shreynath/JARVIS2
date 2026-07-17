"""Tests for recursive decomposition."""

from core.reasoning.decomposition_engine import DecompositionEngine
from core.reasoning.intent_parser import IntentParser
from llm.ollama_client import DeterministicProvider


def test_decomposition_produces_hierarchy():
    provider = DeterministicProvider()
    intent = IntentParser(provider).parse("Create a vehicle engine specification")
    graph = DecompositionEngine(provider).decompose(intent)

    assert graph.root_id == "root"
    assert "root" in graph.components
    assert len(graph.components) > 1

    root = graph.components["root"]
    assert len(root.children) > 0


def test_decomposition_all_children_exist():
    provider = DeterministicProvider()
    intent = IntentParser(provider).parse("Create a vehicle engine specification")
    graph = DecompositionEngine(provider).decompose(intent)

    all_ids = graph.all_node_ids()
    for comp in graph.components.values():
        for child_id in comp.children:
            assert child_id in all_ids, f"Undefined reference: {child_id}"


def test_decomposition_has_leaf_nodes():
    provider = DeterministicProvider()
    intent = IntentParser(provider).parse("Create a vehicle engine specification")
    graph = DecompositionEngine(provider).decompose(intent)

    leaves = [c for c in graph.components.values() if c.is_leaf]
    assert len(leaves) > 0
