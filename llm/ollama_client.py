"""Ollama HTTP client and deterministic test provider."""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from typing import Any

import requests


class LLMProvider(ABC):
    """Abstract LLM transport."""

    @abstractmethod
    def complete(self, system_prompt: str, user_prompt: str) -> str:
        """Return raw text completion."""


class OllamaClient(LLMProvider):
    """HTTP client for local Ollama API."""

    def __init__(
        self,
        host: str | None = None,
        model: str | None = None,
        timeout: float = 120.0,
    ) -> None:
        self.host = (host or os.environ.get("OLLAMA_HOST", "http://localhost:11434")).rstrip("/")
        self.model = model or os.environ.get("OLLAMA_MODEL", "llama3.2")
        self.timeout = timeout

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        url = f"{self.host}/api/chat"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "format": "json",
        }
        response = requests.post(url, json=payload, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()
        return data["message"]["content"]

    def is_available(self) -> bool:
        try:
            response = requests.get(f"{self.host}/api/tags", timeout=3.0)
            return response.status_code == 200
        except requests.RequestException:
            return False


class DeterministicProvider(LLMProvider):
    """Rule-based provider for tests and offline use without Ollama."""

    def __init__(self, responses: dict[str, Any] | None = None) -> None:
        self._responses = responses or {}

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        role = _detect_role(system_prompt)
        if role in self._responses:
            return json.dumps(self._responses[role])

        if role == "intent":
            return json.dumps(_default_intent_response(user_prompt))
        if role == "architect":
            return json.dumps(_default_architect_response(user_prompt))
        if role == "critic":
            return json.dumps(_default_critic_response())
        if role == "engineer":
            return json.dumps(_default_engineer_response())
        return json.dumps({"error": "no deterministic response"})

    def register(self, role: str, response: dict[str, Any]) -> None:
        self._responses[role] = response


def _detect_role(system_prompt: str) -> str:
    lower = system_prompt.lower()
    if "intent" in lower and "extract" in lower:
        return "intent"
    if "architect" in lower or "decompose" in lower:
        return "architect"
    if "critic" in lower or "review" in lower:
        return "critic"
    if "engineer" in lower or "repair" in lower:
        return "engineer"
    return "unknown"


def _default_intent_response(user_prompt: str) -> dict[str, Any]:
    lower = user_prompt.lower()
    object_type = "internal_combustion_engine"
    if "ferrari" in lower:
        reference = ["Ferrari V12 engines"]
        goal = "high performance naturally aspirated sports engine"
    elif "pagani" in lower:
        reference = ["Pagani Huayra R engine"]
        goal = "extreme performance naturally aspirated engine"
    else:
        reference = []
        goal = "vehicle engine specification"

    return {
        "object_type": object_type,
        "design_goal": goal,
        "reference_objects": reference,
        "constraints": [
            {"type": "performance", "description": "High power output", "priority": "high"},
            {"type": "reliability", "description": "Track-capable durability", "priority": "medium"},
        ],
        "unknowns": ["displacement", "compression_ratio", "fuel_system", "cooling_capacity"],
        "required_domains": ["thermodynamics", "mechanical_design", "materials", "fluid_dynamics"],
    }


def _default_architect_response(user_prompt: str) -> dict[str, Any]:
    lower = user_prompt.lower()
    if "root" in lower or "engine" in lower and "expand" not in lower:
        return {
            "nodes": [
                {"id": "block_assembly", "name": "Block Assembly", "function": "Houses cylinders and crankshaft", "material": "Aluminum alloy", "complexity_score": 3.0},
                {"id": "crankshaft_assembly", "name": "Crankshaft Assembly", "function": "Converts reciprocating to rotational motion", "material": "Forged steel", "complexity_score": 2.5},
                {"id": "cylinder_head_assembly", "name": "Cylinder Head Assembly", "function": "Seals combustion chambers and houses valves", "material": "Aluminum alloy", "complexity_score": 3.0},
                {"id": "fuel_system", "name": "Fuel System", "function": "Delivers fuel to combustion chambers", "material": None, "complexity_score": 2.0},
                {"id": "cooling_system", "name": "Cooling System", "function": "Maintains operating temperature", "material": None, "complexity_score": 2.0},
                {"id": "lubrication_system", "name": "Lubrication System", "function": "Reduces friction and removes heat", "material": None, "complexity_score": 1.5},
                {"id": "electrical_system", "name": "Electrical System", "function": "Ignition and engine management", "material": None, "complexity_score": 1.5},
            ]
        }
    if "block_assembly" in lower:
        return {
            "nodes": [
                {"id": "engine_block", "name": "Engine Block", "function": "Structural housing for combustion cylinders", "material": "Aluminum alloy", "complexity_score": 1.0, "is_leaf": True},
                {"id": "cylinder_bores", "name": "Cylinder Bores", "function": "Guides piston motion", "material": "Cast iron liners", "complexity_score": 0.8, "is_leaf": True},
                {"id": "water_jackets", "name": "Water Jackets", "function": "Coolant flow passages", "material": "Aluminum alloy", "complexity_score": 0.8, "is_leaf": True},
                {"id": "main_bearing_supports", "name": "Main Bearing Supports", "function": "Support crankshaft rotation", "material": "Aluminum alloy", "complexity_score": 0.8, "is_leaf": True},
            ]
        }
    return {"nodes": [{"id": "sub_component", "name": "Sub Component", "function": "Generic sub-component", "material": "Steel", "complexity_score": 0.5, "is_leaf": True}]}


def _default_critic_response() -> dict[str, Any]:
    return {"issues": []}


def _default_engineer_response() -> dict[str, Any]:
    return {"repairs": []}
