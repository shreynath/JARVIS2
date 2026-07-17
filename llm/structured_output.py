"""Structured JSON extraction with validation and repair loop."""

from __future__ import annotations

import json
import re
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from llm.ollama_client import LLMProvider

T = TypeVar("T", bound=BaseModel)


class StructuredOutput:
    """Extract and validate JSON from LLM responses with repair."""

    REPAIR_PROMPT = (
        "Your previous response was invalid JSON or failed schema validation.\n"
        "Errors:\n{errors}\n\n"
        "Return ONLY valid JSON matching the required schema. No markdown, no explanation."
    )

    def __init__(self, provider: LLMProvider, max_repairs: int = 2) -> None:
        self.provider = provider
        self.max_repairs = max_repairs

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: type[T],
    ) -> T:
        raw = self.provider.complete(system_prompt, user_prompt)
        parsed = self._extract_json(raw)

        for attempt in range(self.max_repairs + 1):
            try:
                return schema.model_validate(parsed)
            except ValidationError as exc:
                if attempt >= self.max_repairs:
                    raise
                repair_prompt = self.REPAIR_PROMPT.format(errors=exc.errors())
                raw = self.provider.complete(system_prompt, repair_prompt)
                parsed = self._extract_json(raw)

        raise RuntimeError("Structured output failed after repairs")

    def generate_dict(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> dict:
        raw = self.provider.complete(system_prompt, user_prompt)
        return self._extract_json(raw)

    @staticmethod
    def _extract_json(text: str) -> dict:
        text = text.strip()
        try:
            result = json.loads(text)
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass

        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            result = json.loads(match.group())
            if isinstance(result, dict):
                return result

        raise ValueError(f"Could not extract JSON from LLM response: {text[:200]}")
