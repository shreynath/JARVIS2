"""Phase B domain generality suite — live LLM path only.

These requests span domains the architecture claims to support. They must NOT be
run against DeterministicProvider for pass/fail reporting (that fixture defaults
to ICE by design).

Usage:
  JARVIS_LIVE_LLM=1 pytest tests/domain_generality_suite.py -v
  python scripts/run_domain_generality.py
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

import pytest

from core.reasoning.domain_dispatch import is_ice_object_type
from core.reasoning.pipeline import SemanticKernelPipeline
from llm.env_loader import load_dotenv
from llm.ollama_client import OllamaClient

# Phase B1 fixed domain set (10) + audit regression markers (2).
DOMAIN_REQUESTS: list[tuple[str, str]] = [
    ("steel_truss_bridge", "design a steel truss bridge spanning 40 meters"),
    ("bicycle_frame", "design a bicycle frame for a road racing bike"),
    ("quadcopter_frame", "design a quadcopter drone frame"),
    ("hvac_ductwork", "design a residential HVAC ductwork system"),
    ("battery_pack_enclosure", "design a lithium-ion battery pack enclosure"),
    ("dining_chair", "design a wooden dining chair"),
    ("centrifugal_pump", "design a centrifugal water pump"),
    ("robotic_arm_gripper", "design a robotic arm gripper"),
    ("pressure_vessel", "design a pressure vessel for compressed nitrogen storage"),
    ("solar_panel_mounting_rack", "design a solar panel mounting rack"),
]

REGRESSION_MARKERS: list[tuple[str, str]] = [
    ("bicycle_frame", "design a bicycle frame"),
    ("dining_chair", "design a chair"),
]

# Component name substrings that indicate a reskinned ICE part list.
_ICE_COMPONENT_MARKERS = re.compile(
    r"piston|crankshaft|cylinder|combustion|connecting.?rod|camshaft|spark.?plug|engine.?block",
    re.I,
)

# Acceptable object_type substrings per expected family (LLM may vary wording).
_ACCEPTABLE_TYPE_FRAGMENTS: dict[str, tuple[str, ...]] = {
    "steel_truss_bridge": ("truss", "bridge"),
    "bicycle_frame": ("bicycle", "bike", "frame"),
    "quadcopter_frame": ("quadcopter", "drone", "multirotor", "frame"),
    "hvac_ductwork": ("hvac", "duct"),
    "battery_pack_enclosure": ("battery", "enclosure", "pack"),
    "dining_chair": ("chair", "furniture", "seat"),
    "centrifugal_pump": ("pump", "centrifugal"),
    "robotic_arm_gripper": ("gripper", "robot", "end_effector", "endeffector"),
    "pressure_vessel": ("pressure", "vessel", "tank"),
    "solar_panel_mounting_rack": ("solar", "mount", "rack", "panel"),
}


def _live_llm_ready() -> bool:
    load_dotenv()
    if os.environ.get("JARVIS_LIVE_LLM", "").strip() not in {"1", "true", "yes"}:
        return False
    return OllamaClient().is_available()


requires_live_llm = pytest.mark.skipif(
    not _live_llm_ready(),
    reason="Set JARVIS_LIVE_LLM=1 and ensure Ollama is reachable for Phase B live tests",
)


@dataclass
class DomainCaseResult:
    prompt: str
    expected_family: str
    object_type: str
    domains: list[str]
    component_ids: list[str]
    component_names: list[str]
    physics_skipped_ice: bool
    physics_warnings: list[str]
    requirement_decision_ids: list[str]
    provider_used: str
    degraded: bool
    object_type_ok: bool
    components_ok: bool
    intent_structure_ok: bool
    not_ice: bool
    evidence_path: str = ""
    notes: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return (
            self.not_ice
            and self.object_type_ok
            and self.components_ok
            and self.intent_structure_ok
            and not self.degraded
        )


def _object_type_matches(expected_family: str, object_type: str) -> bool:
    if is_ice_object_type(object_type):
        return False
    norm = object_type.lower().replace("-", "_")
    fragments = _ACCEPTABLE_TYPE_FRAGMENTS.get(expected_family, (expected_family,))
    return any(f in norm for f in fragments)


def _components_plausible(expected_family: str, ids: list[str], names: list[str]) -> bool:
    if not ids and not names:
        return False
    blob = " ".join(ids + names)
    if _ICE_COMPONENT_MARKERS.search(blob):
        return False
    # Family-specific positive cues (at least one).
    cues: dict[str, tuple[str, ...]] = {
        "dining_chair": ("seat", "leg", "back", "rail", "stretcher"),
        "bicycle_frame": ("tube", "dropout", "head", "stay", "bracket", "frame"),
        "steel_truss_bridge": ("truss", "chord", "deck", "abutment", "diagonal", "vertical"),
        "quadcopter_frame": ("arm", "motor", "plate", "landing", "avionics"),
        "hvac_ductwork": ("duct", "damper", "trunk", "grille", "branch"),
        "battery_pack_enclosure": ("enclosure", "cell", "battery", "thermal", "tray", "case"),
        "centrifugal_pump": ("impeller", "volute", "casing", "shaft", "seal"),
        "robotic_arm_gripper": ("finger", "gripper", "actuator", "sensor", "jaw"),
        "pressure_vessel": ("shell", "head", "nozzle", "relief", "vessel"),
        "solar_panel_mounting_rack": ("rail", "anchor", "leg", "clamp", "purlin", "mount"),
    }
    for cue in cues.get(expected_family, ()):
        if cue in blob.lower():
            return True
    # If LLM invented reasonable non-ICE parts without our cues, still OK if no ICE markers
    # and we have several components.
    return len(ids) >= 3


def evaluate_case(
    pipeline: SemanticKernelPipeline,
    expected_family: str,
    prompt: str,
    evidence_dir: Path | None = None,
) -> DomainCaseResult:
    result = pipeline.run(prompt)
    ids = list(result.graph.components.keys())
    names = [c.name for c in result.graph.components.values()]
    physics_warnings = list(result.physics_analysis.warnings) if result.physics_analysis else []
    physics_skipped = any("ICE PhysicsEngine was not invoked" in w for w in physics_warnings)
    decision_ids = [d.id for d in result.requirement_spec.required_decisions]

    ice_decisions = {"engine_architecture", "aspiration", "target_horsepower", "fuel_type"}
    has_ice_decisions = bool(ice_decisions.intersection(decision_ids))

    object_type_ok = _object_type_matches(expected_family, result.intent.object_type)
    components_ok = _components_plausible(expected_family, ids, names)
    not_ice = not is_ice_object_type(result.intent.object_type)
    intent_structure_ok = (
        not has_ice_decisions
        and bool(result.intent.object_type)
        and (bool(result.intent.required_domains) or bool(result.functional_analysis.required_domains))
    )

    notes: list[str] = []
    if not object_type_ok:
        notes.append(f"object_type mismatch: got {result.intent.object_type!r}")
    if not components_ok:
        notes.append(f"components implausible or ICE-like: {ids[:12]}")
    if has_ice_decisions:
        notes.append(f"ICE decisions present: {sorted(ice_decisions.intersection(decision_ids))}")
    if result.degraded:
        notes.append("degraded provider — not a live LLM result")

    evidence_path = ""
    if evidence_dir is not None:
        evidence_dir.mkdir(parents=True, exist_ok=True)
        safe = re.sub(r"[^a-z0-9]+", "_", expected_family.lower()).strip("_")
        path = evidence_dir / f"{safe}.json"
        payload = {
            "prompt": prompt,
            "expected_family": expected_family,
            "intent": result.intent.model_dump(),
            "requirement_spec": result.requirement_spec.model_dump(),
            "functional_analysis": result.functional_analysis.model_dump(),
            "component_ids": ids,
            "component_names": names,
            "physics_warnings": physics_warnings,
            "provider_used": result.provider_used,
            "degraded": result.degraded,
        }
        path.write_text(json.dumps(payload, indent=2))
        evidence_path = str(path)

    return DomainCaseResult(
        prompt=prompt,
        expected_family=expected_family,
        object_type=result.intent.object_type,
        domains=list(result.intent.required_domains),
        component_ids=ids,
        component_names=names,
        physics_skipped_ice=physics_skipped,
        physics_warnings=physics_warnings,
        requirement_decision_ids=decision_ids,
        provider_used=result.provider_used,
        degraded=result.degraded,
        object_type_ok=object_type_ok,
        components_ok=components_ok,
        intent_structure_ok=intent_structure_ok,
        not_ice=not_ice,
        evidence_path=evidence_path,
        notes=notes,
    )


@requires_live_llm
@pytest.mark.parametrize(
    "expected_family,prompt",
    DOMAIN_REQUESTS + REGRESSION_MARKERS,
    ids=[p for _, p in DOMAIN_REQUESTS + REGRESSION_MARKERS],
)
def test_domain_generality_live(expected_family: str, prompt: str, tmp_path: Path) -> None:
    load_dotenv()
    client = OllamaClient()
    assert client.is_available(), "Ollama must be reachable for live domain tests"
    pipeline = SemanticKernelPipeline(provider=client)
    case = evaluate_case(pipeline, expected_family, prompt, evidence_dir=tmp_path)
    assert case.passed, f"{prompt!r} failed: {case.notes} object_type={case.object_type} components={case.component_ids}"


def test_domain_dispatch_skips_ice_physics_for_chair() -> None:
    """Offline unit check: non-ICE object types must not invoke ICE physics."""
    from core.ir.design_graph import EngineeringIntent
    from core.reasoning.pipeline import SemanticKernelPipeline
    from llm.ollama_client import DeterministicProvider

    # Force chair via taxonomy safety net even if deterministic intent says ICE.
    pipeline = SemanticKernelPipeline(provider=DeterministicProvider())
    # Monkeypatch intent by running through taxonomy path
    from core.reasoning.intent_parser import IntentParser

    intent = EngineeringIntent(
        object_type="dining_chair",
        design_goal="wooden dining chair",
        raw_input="design a wooden dining chair",
        required_domains=["structural_analysis", "materials"],
    )
    spec = pipeline.requirement_compiler.compile(intent)
    physics = pipeline._run_physics(intent, spec)
    assert any("ICE PhysicsEngine was not invoked" in w for w in physics.warnings)
    assert not any(c.id.startswith("calc_rod") for c in physics.calculations)
    assert not any(d.id == "engine_architecture" for d in spec.required_decisions)
