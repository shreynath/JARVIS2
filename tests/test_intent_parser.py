"""Tests for intent parser."""

from core.reasoning.intent_parser import IntentParser
from llm.ollama_client import DeterministicProvider


def test_intent_parser_not_just_classification():
    parser = IntentParser(DeterministicProvider())
    intent = parser.parse("Create a Ferrari inspired V12 engine")

    assert intent.object_type == "internal_combustion_engine"
    assert intent.design_goal
    assert len(intent.unknowns) > 0
    assert len(intent.required_domains) > 0
    assert intent.raw_input == "Create a Ferrari inspired V12 engine"


def test_intent_parser_has_constraints():
    parser = IntentParser(DeterministicProvider())
    intent = parser.parse("Create a vehicle engine specification")

    assert len(intent.constraints) > 0
    assert intent.constraints[0].type


def test_intent_parser_reference_objects():
    parser = IntentParser(DeterministicProvider())
    intent = parser.parse("Make me a Pagani Huayra R engine specification")

    assert len(intent.reference_objects) > 0
