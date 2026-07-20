"""Adversarial detection tests — PhysicsRulesEngine (warning-only, ≥3 fixtures)."""

from core.ir.component import ComponentNode

from validation.integrity import VerificationKind
from validation.physics_rules import PhysicsRulesEngine

from adversarial_fixtures import minimal_graph


def test_flags_unassigned_material():
    graph = minimal_graph()
    graph.components["block"].material = None
    report = PhysicsRulesEngine().validate(graph)
    assert any("no material" in i.message.lower() for i in report.issues)
    assert report.verification_checks[0].verification_kind == VerificationKind.SELF_CONSISTENCY_CHECK.value
    # Warning-only validator — rejected stays False
    assert report.verification_checks[0].rejected is False


def test_flags_multiple_unassigned_materials():
    graph = minimal_graph()
    graph.components["block"].material = None
    graph.add_component(
        ComponentNode(
            id="rod",
            name="Rod",
            function="Connecting rod",
            parent_id="root",
            is_leaf=True,
        )
    )
    report = PhysicsRulesEngine().validate(graph)
    material_issues = [i for i in report.issues if "no material" in i.message.lower()]
    assert len(material_issues) >= 2


def test_no_warning_when_all_materials_assigned():
    graph = minimal_graph()
    graph.components["root"].material = "Steel"
    graph.add_component(
        ComponentNode(
            id="rod",
            name="Rod",
            function="Connecting rod",
            material="Forged Steel 4340",
            parent_id="root",
            is_leaf=True,
        )
    )
    report = PhysicsRulesEngine().validate(graph)
    assert not any("no material" in i.message.lower() for i in report.issues)
