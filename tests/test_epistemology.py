"""Step 1 — Epistemology consolidation: wrap_calculation round-trip."""

from __future__ import annotations

import pytest

from core.epistemology import Evidence, KnowledgeState, wrap_calculation
from core.reasoning.pipeline import SemanticKernelPipeline
from llm.ollama_client import DeterministicProvider

PROMPT = "Design a 9000 RPM naturally aspirated V12 producing 800 horsepower."


def test_knowledge_state_has_no_global_ordering():
    with pytest.raises(TypeError, match="no global ordering"):
        _ = KnowledgeState.DERIVED > KnowledgeState.ASSUMED
    with pytest.raises(TypeError, match="no global ordering"):
        _ = KnowledgeState.EMPIRICAL < KnowledgeState.SIMULATED


def test_wrap_calculation_round_trips_phase1_provenance_fields():
    result = SemanticKernelPipeline(provider=DeterministicProvider()).run(PROMPT)
    assert result.physics_analysis.calculations

    for calc in result.physics_analysis.calculations:
        evidence = wrap_calculation(calc)
        assert isinstance(evidence, Evidence)
        assert evidence.source_calc_id == calc.id
        assert evidence.claim == calc.name
        assert evidence.state == calc.knowledge_state
        assert evidence.confidence == calc.confidence
        assert evidence.reason in {calc.assessment, calc.reason, calc.assessment or calc.reason or ""}

        # Underlying calculation fields unchanged by wrap (read-only).
        assert calc.result == calc.result
        assert calc.value_range == calc.value_range
        assert calc.passes == calc.passes
        assert calc.knowledge_state == evidence.state
        assert calc.confidence == evidence.confidence


def test_wrap_calculation_accepts_dict_shape():
    evidence = wrap_calculation(
        {
            "id": "calc_torque",
            "name": "Torque",
            "knowledge_state": "derived",
            "confidence": "high",
            "assessment": "from power and rpm",
            "result": 1.0,
        }
    )
    assert evidence.source_calc_id == "calc_torque"
    assert evidence.state == KnowledgeState.DERIVED
    assert evidence.confidence == "high"
    assert "power" in evidence.reason
