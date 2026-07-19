"""Ollama HTTP client and deterministic test provider."""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from typing import Any

import requests

from knowledge.decomposition.component_templates import COMPONENT_TEMPLATES
from knowledge.functional.templates import resolve_functional_template


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
        if role == "functional":
            return json.dumps(_default_functional_response(user_prompt))
        if role == "architect":
            return json.dumps(_default_architect_response(user_prompt))
        if role == "critic":
            return json.dumps(_default_critic_response(user_prompt))
        if role == "engineer":
            return json.dumps(_default_engineer_response())
        return json.dumps({"error": "no deterministic response"})

    def register(self, role: str, response: dict[str, Any]) -> None:
        self._responses[role] = response


def _detect_role(system_prompt: str) -> str:
    lower = system_prompt.lower()
    if "functional architect" in lower or "functional decomposition" in lower:
        return "functional"
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

    if "gearbox" in lower or "transmission" in lower:
        return {
            "object_type": "gearbox",
            "design_goal": "multi-speed gearbox specification",
            "reference_objects": [],
            "constraints": [
                {"type": "torque_capacity", "description": "High torque transmission", "priority": "high"},
                {"type": "efficiency", "description": "Minimal power loss", "priority": "high"},
            ],
            "unknowns": ["gear_ratios", "input_speed", "lubrication_type"],
            "required_domains": ["mechanical_design", "materials", "tribology"],
        }

    if "aircraft" in lower or "turbofan" in lower or "jet engine" in lower:
        return {
            "object_type": "turbofan_engine",
            "design_goal": "commercial aircraft turbofan engine specification",
            "reference_objects": ["CFM56", "GE90"],
            "constraints": [
                {"type": "thrust", "description": "High takeoff thrust", "priority": "critical"},
                {"type": "fuel_efficiency", "description": "Low specific fuel consumption", "priority": "high"},
            ],
            "unknowns": ["bypass_ratio", "turbine_inlet_temperature", "overall_pressure_ratio"],
            "required_domains": ["thermodynamics", "fluid_dynamics", "materials", "structural_analysis"],
        }

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


def _default_functional_response(user_prompt: str) -> dict[str, Any]:
    lower = user_prompt.lower()
    object_type = "internal_combustion_engine"
    if "gearbox" in lower:
        object_type = "gearbox"
    elif "aircraft" in lower or "turbofan" in lower:
        object_type = "turbofan_engine"

    template = resolve_functional_template(object_type, lower)
    if template is None:
        return {"primary_function": "unknown", "functions": [], "flows": [], "required_assemblies": [], "required_domains": []}
    return template.model_dump()


def _default_architect_response(user_prompt: str) -> dict[str, Any]:
    lower = user_prompt.lower()
    for assembly_id, components in COMPONENT_TEMPLATES.items():
        if f"id={assembly_id}" in lower or f"id={assembly_id}," in lower:
            return {"nodes": components}
    return {"nodes": []}


def _default_critic_response(user_prompt: str) -> dict[str, Any]:
    return {
        "issues": [
            {
                "id": "critic_llm_1",
                "node_id": "root",
                "description": "Why aluminum block without quantified thermal margin?",
                "severity": "warning",
                "category": "assumption",
                "suggested_fix": "Add thermal constraint with maximum operating temperature",
            },
            {
                "id": "critic_llm_2",
                "node_id": "root",
                "description": "Displacement and cylinder count not specified",
                "severity": "warning",
                "category": "completeness",
                "suggested_fix": "Document displacement assumption or extract from requirements",
            },
        ]
    }


def _default_engineer_response() -> dict[str, Any]:
    return {"repairs": []}
