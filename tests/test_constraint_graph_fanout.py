"""Regression: constraint graph must fan out all PhysicsCalculation.dependency_ids."""

from __future__ import annotations

from core.ir.constraint_graph import ConstraintGraph
from core.reasoning.physics_engine import PhysicsAnalysis
from core.reasoning.pipeline import SemanticKernelPipeline
from llm.ollama_client import DeterministicProvider


def incoming_dep_sources(constraint_graph: ConstraintGraph, calc_id: str) -> set[str]:
    """Incoming traces_to sources as calc_* IDs (ignores req_* requirement fallbacks)."""
    target = f"constraint_{calc_id}"
    sources: set[str] = set()
    for edge in constraint_graph.edges:
        if edge.edge_type.value != "traces_to" or edge.target_id != target:
            continue
        src = edge.source_id
        if src.startswith("constraint_"):
            remainder = src[len("constraint_") :]
            if remainder.startswith("calc_"):
                sources.add(remainder)
    return sources


def test_constraint_graph_dependency_fanout_complete():
    result = SemanticKernelPipeline(provider=DeterministicProvider()).run(
        "Design a 9000 RPM naturally aspirated V12 producing 800 horsepower."
    )
    physics_analysis: PhysicsAnalysis = result.physics_analysis
    constraint_graph = result.constraint_graph

    for calc in physics_analysis.calculations:
        declared = set(calc.dependency_ids)
        actual = incoming_dep_sources(constraint_graph, calc.id)
        assert declared == actual, f"{calc.id}: declared {declared} != graph {actual}"

    # Explicit multi-dep case that previously regressed.
    rod = physics_analysis.by_id("calc_rod_loading")
    assert rod is not None
    assert set(rod.dependency_ids) == {"calc_piston_acceleration", "calc_displacement"}
    assert incoming_dep_sources(constraint_graph, "calc_rod_loading") == {
        "calc_piston_acceleration",
        "calc_displacement",
    }
