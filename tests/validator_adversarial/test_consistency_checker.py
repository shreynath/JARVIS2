"""Adversarial rejection tests — ConsistencyChecker (≥3 broken fixtures)."""

from validation.integrity import VerificationKind
from validation.consistency import ConsistencyChecker

from adversarial_fixtures import (
    graph_cycle,
    graph_undefined_assembly_member,
    graph_undefined_child,
    graph_undefined_parent,
    minimal_graph,
)


def test_rejects_undefined_child_reference():
    report = ConsistencyChecker().validate(graph_undefined_child())
    assert not report.passed
    assert any("undefined child" in i.message for i in report.issues)
    assert report.verification_checks[0].verification_kind == VerificationKind.SELF_CONSISTENCY_CHECK.value


def test_rejects_undefined_parent_reference():
    report = ConsistencyChecker().validate(graph_undefined_parent())
    assert not report.passed
    assert any("undefined parent" in i.message for i in report.issues)


def test_rejects_hierarchy_cycle():
    report = ConsistencyChecker().validate(graph_cycle())
    assert not report.passed
    assert any("cycle" in i.message.lower() for i in report.issues)


def test_rejects_undefined_assembly_member():
    report = ConsistencyChecker().validate(graph_undefined_assembly_member())
    assert not report.passed
    assert any("undefined member" in i.message for i in report.issues)


def test_accepts_consistent_graph():
    report = ConsistencyChecker().validate(minimal_graph())
    assert report.passed
