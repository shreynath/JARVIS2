"""Equation provenance must appear on computed calculations."""

from __future__ import annotations

from core.reasoning.pipeline import SemanticKernelPipeline
from llm.ollama_client import DeterministicProvider


def test_physics_calculations_carry_equation_provenance():
    result = SemanticKernelPipeline(provider=DeterministicProvider()).run(
        "Design a 9000 RPM naturally aspirated V12 producing 800 horsepower."
    )
    assert result.physics_analysis is not None
    computed = [c for c in result.physics_analysis.calculations if c.status == "computed"]
    assert computed
    for calc in computed:
        assert calc.equation_id, calc.id
        assert calc.validation_status, calc.id
        assert calc.equation_source is not None
