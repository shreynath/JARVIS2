"""Phase F — truss bridge physics at ICE rigor standard."""

from __future__ import annotations

from core.engineering.truss_bridge_model import TrussBridgeModel
from core.ir.design_graph import EngineeringIntent
from core.reasoning.bridge_physics_engine import analyze_bridge
from core.reasoning.domain_dispatch import physics_handler_for
from core.reasoning.requirement_compiler import RequirementCompiler
from knowledge.equations.catalog import provenance_for_calc


def test_span_extraction_and_bridge_physics_calculations():
    compiler = RequirementCompiler()
    intent = EngineeringIntent(
        object_type="steel_truss_bridge",
        design_goal="40 m truss",
        raw_input="design a steel truss bridge spanning 40 meters",
    )
    spec = compiler.compile(intent)
    analysis = analyze_bridge(spec)

    deck = analysis.by_id("calc_bridge_deck_moment")
    truss = analysis.by_id("calc_truss_member_stress")
    assert deck is not None
    assert truss is not None
    assert deck.result is not None
    assert truss.result is not None
    assert deck.unit == "N·m"
    assert truss.unit == "MPa"
    assert truss.value_range is not None
    assert deck.assumptions
    assert truss.dependency_ids == ["calc_bridge_deck_moment"]


def test_bridge_handler_registered():
    handler = physics_handler_for("steel_truss_bridge")
    assert handler is not None
    assert handler.__name__ == "analyze_bridge"


def test_equation_provenance_for_bridge_calcs():
    deck_prov = provenance_for_calc("calc_bridge_deck_moment")
    truss_prov = provenance_for_calc("calc_truss_member_stress")
    assert deck_prov["equation_id"] == "eq_bridge_deck_moment"
    assert truss_prov["equation_id"] == "eq_truss_member_stress"
    assert deck_prov.get("engineering_reference", {}).get("citation")
    assert truss_prov.get("engineering_reference", {}).get("citation")


def test_truss_bridge_model_records_assumptions():
    result = TrussBridgeModel().estimate(span_m=40.0)
    assert result.estimate is not None
    assert result.estimate.span_m == 40.0
    assert result.estimate.max_member_stress_mpa > 0
    assert result.assumption_records
