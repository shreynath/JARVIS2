"""Domain dispatch — which capabilities apply to which engineered object types.

ICE physics, ICE decision sets, and ICE material roles are *reference-domain*
implementations. Non-ICE requests must not silently inherit them.

Extension: register additional physics handlers via ``register_physics_handler``
or add functional/component templates under ``knowledge/`` without changing the
pipeline orchestration (see ARCHITECTURE.md / Phase B).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

# Object types that use the ICE physics / decision / material stack.
ICE_OBJECT_TYPES: frozenset[str] = frozenset(
    {
        "internal_combustion_engine",
        "reciprocating_engine",
        "v12_engine",
        "v8_engine",
        "engine",
    }
)

# Substrings that mark ICE even when the LLM invents a nearby label.
_ICE_TYPE_HINTS: tuple[str, ...] = (
    "internal_combustion",
    "reciprocating_engine",
    "combustion_engine",
    "petrol_engine",
    "gasoline_engine",
    "diesel_engine",
    "v8_engine",
    "v12_engine",
    "v10_engine",
    "v6_engine",
)

# Phrases that look like "engine" but are not ICE.
_NON_ICE_ENGINE_PHRASES: tuple[str, ...] = (
    "jet engine",
    "turbofan",
    "turbojet",
    "turboprop",
    "rocket engine",
    "steam engine",  # out of ICE stack for now
    "search engine",
)


def normalize_object_type(object_type: str | None) -> str:
    return (object_type or "").strip().lower().replace("-", "_").replace(" ", "_")


def is_ice_object_type(object_type: str | None) -> bool:
    """True when the declared object type belongs to the ICE reference domain."""
    norm = normalize_object_type(object_type)
    if not norm:
        return False
    if norm in ICE_OBJECT_TYPES:
        return True
    if any(hint in norm for hint in _ICE_TYPE_HINTS):
        return True
    # Bare "...engine" that is not an explicit non-ICE engine phrase
    if norm.endswith("_engine") or norm == "engine":
        joined = norm.replace("_", " ")
        if any(p.replace(" ", "_") in norm or p in joined for p in _NON_ICE_ENGINE_PHRASES):
            return False
        if "turbofan" in norm or "jet" in norm or "rocket" in norm:
            return False
        return True
    return False


def is_ice_request(object_type: str | None, raw_input: str | None = None) -> bool:
    """Whether ICE physics/decisions should run for this request."""
    if is_ice_object_type(object_type):
        # Override if the user clearly asked for a non-ICE engine family.
        lower = (raw_input or "").lower()
        if any(p in lower for p in _NON_ICE_ENGINE_PHRASES):
            return False
        return True
    return False


# Object types that use the bridge/civil physics stack.
BRIDGE_OBJECT_TYPES: frozenset[str] = frozenset(
    {
        "steel_truss_bridge",
        "truss_bridge",
        "bridge",
    }
)


def is_bridge_object_type(object_type: str | None) -> bool:
    norm = normalize_object_type(object_type)
    if norm in BRIDGE_OBJECT_TYPES:
        return True
    return "truss" in norm and "bridge" in norm


# Optional pluggable physics analyzers: object_type → callable(spec, **kwargs) -> PhysicsAnalysis
_PHYSICS_HANDLERS: dict[str, Callable[..., Any]] = {}


def register_physics_handler(object_type: str, handler: Callable[..., Any]) -> None:
    """Register a domain physics analyzer (knowledge/plugins may call this at import)."""
    _PHYSICS_HANDLERS[normalize_object_type(object_type)] = handler


def physics_handler_for(object_type: str | None) -> Callable[..., Any] | None:
    _ensure_default_handlers()
    norm = normalize_object_type(object_type)
    if norm in _PHYSICS_HANDLERS:
        return _PHYSICS_HANDLERS[norm]
    if is_bridge_object_type(norm):
        return _PHYSICS_HANDLERS.get("steel_truss_bridge")
    return None


def _ensure_default_handlers() -> None:
    if "steel_truss_bridge" in _PHYSICS_HANDLERS:
        return
    from core.reasoning.bridge_physics_engine import analyze_bridge

    for key in BRIDGE_OBJECT_TYPES:
        register_physics_handler(key, analyze_bridge)
