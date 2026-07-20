"""Phase 5.0 — material requirement evidence packets."""

from __future__ import annotations

from core.materials.material_requirement import (
    build_structural_rod_requirement,
    unknown_requirement,
)
from core.reasoning.pipeline import SemanticKernelPipeline
from llm.ollama_client import DeterministicProvider


def test_structural_requirement_packet_shape():
    pkt = build_structural_rod_requirement(
        component="connecting_rods",
        stress_mpa=400.0,
    )
    d = pkt.to_dict()
    assert d["component"] == "connecting_rods"
    assert "yield_mpa" in d["required_properties"]
    assert d["computed_from"]
    assert d["load_case"]
    assert d["safety_factor"]["yield"] == 1.25
    assert d["status"] == "computed"


def test_unknown_requirement_explicit():
    unk = unknown_requirement("radiator", "no pathway")
    assert unk.status == "UNKNOWN"
    assert unk.required_properties == {}


def test_pipeline_material_decisions_include_evidence_packet():
    result = SemanticKernelPipeline(provider=DeterministicProvider()).run(
        "Design a 9000 RPM naturally aspirated V12 producing 800 horsepower."
    )
    rods = result.graph.components["connecting_rods"]
    assert rods.material_spec is not None
    metrics = rods.material_spec.selection_metrics or {}
    assert "requirement_evidence" in metrics
    packet = metrics["requirement_evidence"]
    assert packet["component"] == "connecting_rods"
    assert packet["status"] == "computed"
    assert packet["computed_from"]
    assert "alternatives_considered" in packet
    assert "safety_factor" in packet

    radiator = result.graph.components["radiator"]
    assert radiator.material is None
