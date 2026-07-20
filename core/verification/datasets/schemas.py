"""Validation case schemas — structural checks only (no engineering predictions)."""

from __future__ import annotations

from typing import Any


REQUIRED_TOP_LEVEL = (
    "id",
    "system_type",
    "reference_source",
    "inputs",
    "measured_outputs",
    "validation_quality",
)

ALLOWED_SYSTEM_TYPES = {"engine", "structure", "material", "thermal"}
ALLOWED_QUALITIES = {"experimental", "manufacturer", "literature", "estimated"}
ALLOWED_SOURCES = {"manufacturer", "publication", "paper", "test_data"}


class ValidationSchemaError(ValueError):
    """Raised when an external validation case fails structural checks."""


def validate_case_dict(payload: dict[str, Any]) -> None:
    """Validate a raw ValidationCase dict. Does not invent missing measurements."""
    missing = [k for k in REQUIRED_TOP_LEVEL if k not in payload]
    if missing:
        raise ValidationSchemaError(f"Missing keys: {missing}")

    if payload["system_type"] not in ALLOWED_SYSTEM_TYPES:
        raise ValidationSchemaError(f"Invalid system_type: {payload['system_type']!r}")
    if payload["validation_quality"] not in ALLOWED_QUALITIES:
        raise ValidationSchemaError(
            f"Invalid validation_quality: {payload['validation_quality']!r}"
        )
    src = payload["reference_source"]
    if not isinstance(src, dict) or src.get("kind") not in ALLOWED_SOURCES:
        raise ValidationSchemaError(
            f"reference_source.kind must be one of {sorted(ALLOWED_SOURCES)}"
        )
    if not isinstance(payload["inputs"], dict):
        raise ValidationSchemaError("inputs must be a dict")
    if not isinstance(payload["measured_outputs"], dict):
        raise ValidationSchemaError("measured_outputs must be a dict")
    uncertainty = payload.get("uncertainty") or {}
    if not isinstance(uncertainty, dict):
        raise ValidationSchemaError("uncertainty must be a dict when present")

    # Explicit integrity: measured outputs must not silently invent unknown fields.
    for key, value in payload["measured_outputs"].items():
        if value is None:
            continue  # unknown stays unknown
        if not isinstance(value, (int, float)):
            raise ValidationSchemaError(
                f"measured_outputs[{key!r}] must be numeric or null, got {type(value).__name__}"
            )
