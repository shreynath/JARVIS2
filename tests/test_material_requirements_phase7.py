"""Phase 7 — material requirements require load evidence."""

from __future__ import annotations

import pytest

from core.materials.requirements import (
    MaterialRequirement,
    from_stress,
    unexplained_material_choice_error,
)
from core.reasoning.pipeline import SemanticKernelPipeline
from llm.ollama_client import DeterministicProvider


def test_material_requirement_without_dependencies_fails():
    req = MaterialRequirement(
        component="connecting_rods",
        required_properties={"yield_strength": 500.0},
        load_source="",
        calculation_dependencies=[],
        status="computed",
    )
    with pytest.raises(ValueError, match="calculation_dependencies"):
        req.assert_has_source()


def test_from_stress_has_auditable_source():
    req = from_stress(
        component="connecting_rods",
        stress_mpa=400.0,
        temperature_c=160.0,
        yield_factor=1.25,
        fatigue_factor=0.65,
        dependencies=["calc_rod_stress_requirement"],
        load_source="calc_rod_stress_requirement",
        density_sensitive=True,
    )
    assert req.required_properties["yield_strength"] == 500.0
    assert req.calculation_dependencies == ["calc_rod_stress_requirement"]
    req.assert_has_source()


def test_unexplained_material_message():
    msg = unexplained_material_choice_error("connecting_rods", "Titanium")
    assert "without" in msg.lower()
    assert "Titanium" in msg


def test_pipeline_material_evidence_answers_why_load_alternatives():
    result = SemanticKernelPipeline(provider=DeterministicProvider()).run(
        "Design a 9000 RPM naturally aspirated V12 producing 800 horsepower."
    )
    rods = result.graph.components["connecting_rods"]
    assert rods.material_spec is not None
    packet = rods.material_spec.selection_metrics["requirement_evidence"]
    assert packet["computed_from"]
    assert packet["reason_for_selection"]
    assert "yield" in packet["reason_for_selection"].lower()
    assert packet["alternatives_considered"]
    # At least one alternative records a rejected property when not selected.
    assert any(
        (not a.get("selected")) and ("rejected_property" in a)
        for a in packet["alternatives_considered"]
    )
