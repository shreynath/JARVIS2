"""Phase A acceptance: crash-free corpus + transparent degradation.

Corpus spans Phase B domains, known audit regressions, and edge cases.
Runs with DeterministicProvider (Ollama unavailable path) and asserts:
- zero unhandled exceptions (PipelineError is the only allowed typed failure)
- every PipelineResult and every written JSON artifact surfaces degradation
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from core.reasoning.pipeline import PipelineError, SemanticKernelPipeline
from llm.ollama_client import DeterministicProvider

# ≥25 varied natural-language requests (Phase B domains + edge cases).
CORPUS: list[str] = [
    # Phase B domain set
    "design a steel truss bridge spanning 40 meters",
    "design a bicycle frame for a road racing bike",
    "design a quadcopter drone frame",
    "design a residential HVAC ductwork system",
    "design a lithium-ion battery pack enclosure",
    "design a wooden dining chair",
    "design a centrifugal water pump",
    "design a robotic arm gripper",
    "design a pressure vessel for compressed nitrogen storage",
    "design a solar panel mounting rack",
    # Known audit regressions
    "design a bicycle frame",
    "design a chair",
    # Engine / crash cases from audit
    "design a v8 engine",
    "design a V-12",
    "twelve cylinder",
    "design a ferrari v12",
    "make a car",
    "design a v8 engine producing 600 hp at 9000 RPM",
    # Additional variety
    "Create a vehicle engine specification",
    "gearbox for a truck",
    "aircraft turbofan engine",
    "pagani style engine",
    "v8",
    "V-12",
    # Edge cases
    "   ",  # whitespace-only → typed PipelineError
    "x",  # minimal
    (
        "Please design something vaguely mechanical that somehow involves "
        "wheels and maybe seats but also perhaps a cooling system and I am "
        "not sure whether this is an engine or a chair or a bridge and I keep "
        "talking for a very long time about requirements that are not really "
        "requirements at all just rambling text to exercise the parser with a "
        "long input that exceeds typical prompt length while remaining under "
        "a few hundred words so the pipeline must not crash on verbosity. "
        * 3
    ),
]

DEGRADED_PATTERN = re.compile(r"degraded|provider_used|Ollama unavailable|DeterministicProvider|template-derived", re.I)


def _assert_provider_fields(payload: dict) -> None:
    assert "provider_used" in payload
    assert payload["provider_used"] in {
        "deterministic_fallback",
        "DeterministicProvider",
    } or str(payload["provider_used"]).startswith("deterministic")
    assert payload.get("degraded") is True
    assert payload.get("warning")
    assert DEGRADED_PATTERN.search(str(payload["warning"]))


@pytest.mark.parametrize("prompt", CORPUS, ids=lambda p: (p[:48] + "…") if len(p) > 48 else p)
def test_corpus_no_unhandled_exceptions(prompt: str, tmp_path: Path) -> None:
    pipeline = SemanticKernelPipeline(provider=DeterministicProvider())
    stripped = prompt.strip()
    if not stripped:
        with pytest.raises(PipelineError) as exc_info:
            pipeline.run(prompt)
        assert exc_info.value.code == "empty_input"
        return

    try:
        result = pipeline.run(prompt)
    except PipelineError:
        # Typed failure is acceptable; raw tracebacks are not.
        return

    assert result.provider_used == "deterministic_fallback"
    assert result.degraded is True
    assert result.warning
    assert result.intent is not None
    assert result.graph is not None

    out = pipeline.write_outputs(result, tmp_path / "out")
    json_files = list(out.glob("*.json"))
    assert json_files, "expected JSON artifacts"
    for path in json_files:
        data = json.loads(path.read_text())
        assert isinstance(data, dict), f"{path.name} must be an object so provider meta can attach"
        _assert_provider_fields(data)
        blob = path.read_text()
        assert DEGRADED_PATTERN.search(blob), f"no degradation marker in {path.name}"


def test_v8_engine_no_longer_crashes() -> None:
    """Specific audit regression: bmep_source=None must not raise ValidationError."""
    pipeline = SemanticKernelPipeline(provider=DeterministicProvider())
    result = pipeline.run("design a v8 engine")
    assert result.physics_analysis is not None
    disp = result.physics_analysis.by_id("calc_displacement")
    assert disp is not None
    assert disp.inputs.get("bmep_source") in {"unknown", "empirical"} or isinstance(
        disp.inputs.get("bmep_source"), str
    )


def test_default_provider_marks_degraded_when_ollama_down(monkeypatch: pytest.MonkeyPatch) -> None:
    from llm import ollama_client

    monkeypatch.setattr(
        ollama_client.OllamaClient,
        "is_available",
        lambda self: False,
    )
    pipeline = SemanticKernelPipeline()  # no explicit provider
    assert pipeline.degraded is True
    assert pipeline.provider_used == "deterministic_fallback"
    assert pipeline.warning
    assert "Ollama unavailable" in pipeline.warning

    result = pipeline.run("design a chair")
    assert result.degraded is True
    assert result.provider_used == "deterministic_fallback"


def test_sanitize_none_inputs_in_physics_calculation() -> None:
    from core.reasoning.physics_engine import make_physics_calculation

    calc = make_physics_calculation(
        id="calc_displacement",
        name="Displacement estimate",
        formula="test",
        inputs={"bmep_source": None, "rpm": 9000, "flag": True},
        result=1.0,
        unit="L",
    )
    assert calc.inputs["bmep_source"] == "unknown"
    assert calc.inputs["rpm"] == 9000
    assert calc.inputs["flag"] == 1
