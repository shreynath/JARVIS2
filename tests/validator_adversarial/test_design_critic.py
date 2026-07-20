"""Adversarial rejection tests — DesignCritic rule path (≥3 broken fixtures)."""

from core.ir.constraint import Severity
from core.reasoning.critic import DesignCritic
from llm.ollama_client import DeterministicProvider
from validation.integrity import VerificationKind

from adversarial_fixtures import (
    graph_carbon_fiber_combustion,
    graph_generic_placeholder,
    graph_no_assemblies,
    graph_no_constraints,
)


def _critic():
    return DesignCritic(DeterministicProvider())


def test_finds_missing_assemblies():
    issues = _critic().review_rules_only(graph_no_assemblies())
    assert any("no assemblies" in i.description.lower() for i in issues)
    assert _critic().verification_metadata().verification_kind == VerificationKind.SELF_CONSISTENCY_CHECK.value


def test_finds_generic_placeholder_component():
    issues = _critic().review_rules_only(graph_generic_placeholder())
    assert any("generic" in i.description.lower() for i in issues)
    assert any(i.severity == Severity.CRITICAL for i in issues)


def test_finds_unsuitable_material_via_rules():
    issues = _critic().review_rules_only(graph_carbon_fiber_combustion())
    assert any("carbon fiber" in i.description.lower() for i in issues)
    assert any(i.category == "material" for i in issues)


def test_finds_missing_quantified_constraints():
    issues = _critic().review_rules_only(graph_no_constraints())
    assert any("no quantified constraints" in i.description.lower() for i in issues)
