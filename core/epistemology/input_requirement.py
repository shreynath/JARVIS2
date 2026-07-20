"""Physics input epistemology — known / assumed / unknown, never silent default."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class InputState(Enum):
    KNOWN = "known"
    ASSUMED = "assumed"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class InputRequirement:
    """A single physics input with explicit provenance."""

    name: str
    value: str | float | int | None
    state: InputState
    source: str

    def as_dict(self) -> dict[str, str | float | int | None]:
        return {
            "name": self.name,
            "value": self.value,
            "state": self.state.value,
            "source": self.source,
        }


class MissingEngineeringInputError(ValueError):
    """Raised when a required physics input is absent — never silently defaulted."""

    def __init__(self, input_name: str, reason: str = "") -> None:
        self.input_name = input_name
        message = reason or f"Required engineering input {input_name!r} is missing and must not be defaulted."
        super().__init__(message)
