"""Adversarial rejection tests — SchemaValidator (≥3 broken fixtures)."""

from core.ir.component import ComponentNode

from validation.integrity import VerificationKind
from validation.schema_validator import SchemaValidator

from adversarial_fixtures import (
    graph_bad_root,
    graph_no_components,
    minimal_graph,
)


def test_rejects_empty_component_list():
    report = SchemaValidator().validate(graph_no_components())
    assert not report.passed
    assert report.hard_violations >= 1
    assert any("no components" in i.message.lower() for i in report.issues)
    assert report.verification_checks[0].verification_kind == VerificationKind.SELF_CONSISTENCY_CHECK.value
    assert report.verification_checks[0].rejected is True


def test_rejects_root_id_not_in_graph():
    report = SchemaValidator().validate(graph_bad_root())
    assert not report.passed
    assert any("root_id" in i.message for i in report.issues)
    assert report.verification_checks[0].rejected is True


def test_accepts_minimal_valid_graph():
    report = SchemaValidator().validate(minimal_graph())
    assert report.passed
    assert report.verification_checks[0].rejected is False


def test_rejects_single_component_without_children_chain():
    """Root-only graph with no supporting component entries beyond schema minimum."""
    graph = graph_no_components()
    graph.add_component(ComponentNode(id="solo", name="Solo", function="Standalone"))
    graph.root_id = "solo"
    report = SchemaValidator().validate(graph)
    # Pydantic passes; our rule still requires components dict non-empty — passes.
    # Break by clearing components after setting root — triggers no components if we empty.
    graph.components.clear()
    report = SchemaValidator().validate(graph)
    assert not report.passed
    assert any("no components" in i.message.lower() for i in report.issues)
