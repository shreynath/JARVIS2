"""Registry of external validation cases (adapters over reference engine JSON).

Loads published datasets only — never invents missing measurements.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.verification.datasets.sources import manufacturer_source
from core.verification.datasets.validation_case import (
    SystemType,
    ValidationCase,
    ValidationQuality,
)

ROOT = Path(__file__).resolve().parents[3]
REFERENCE_ENGINES = ROOT / "datasets" / "reference_engines"


def _optional_float(payload: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        if key in payload and payload[key] is not None:
            try:
                return float(payload[key])
            except (TypeError, ValueError):
                return None
    return None


def engine_json_to_validation_case(raw: dict[str, Any]) -> ValidationCase:
    """Adapt a reference-engine JSON into a ValidationCase.

    Unknown fields stay None — never back-filled from JARVIS or heuristics.
    """
    pub = dict(raw.get("published") or {})
    quality = ValidationQuality.MANUFACTURER
    dq = str(raw.get("data_quality") or "")
    if "literature" in dq:
        quality = ValidationQuality.LITERATURE
    elif "estimated" in dq:
        quality = ValidationQuality.ESTIMATED
    elif "experimental" in dq or "test" in dq:
        quality = ValidationQuality.EXPERIMENTAL

    manufacturer = raw.get("manufacturer") or (raw.get("name") or raw.get("id"))
    year = raw.get("year")
    sources = raw.get("verified_sources") or []
    citation = sources[0] if sources else pub.get("published_source")

    inputs: dict[str, float | int | None] = {
        "horsepower": _optional_float(pub, "horsepower"),
        "max_rpm": _optional_float(pub, "max_rpm"),
        "cylinder_count": _optional_float(pub, "cylinder_count"),
        "aspiration_token": None,  # qualitative; kept out of numeric inputs
    }
    # Qualitative aspiration stored separately in notes/source, not as invented float.
    measured: dict[str, float | int | None] = {
        "displacement_l": _optional_float(pub, "displacement_l"),
        "bore_mm": _optional_float(pub, "bore_mm"),
        "stroke_mm": _optional_float(pub, "stroke_mm"),
        "torque_nm": _optional_float(pub, "torque_nm"),
        "mean_piston_speed_m_s": _optional_float(pub, "mean_piston_speed_m_s")
        or _optional_float(raw.get("derived_checks") or {}, "mean_piston_speed_at_redline_m_s"),
        "compression_ratio": _optional_float(pub, "compression_ratio"),
        "mass_kg": _optional_float(pub, "mass_kg", "dry_mass_kg", "engine_mass_kg"),
    }
    # Explicit: if key absent from published, leave as None (do not omit — callers see unknown).
    for key in ("compression_ratio", "mass_kg"):
        if key not in pub and key not in ("dry_mass_kg", "engine_mass_kg"):
            # ensure explicit null even when never written in JSON
            measured.setdefault(key, None)

    uncertainty: dict[str, float] = {}
    # Manufacturer published geometry typically ±0.5% for stroke/bore; torque often ±2%.
    if measured["stroke_mm"] is not None:
        uncertainty["stroke_mm"] = 0.5
    if measured["displacement_l"] is not None:
        uncertainty["displacement_l"] = 1.0
    if measured["torque_nm"] is not None:
        uncertainty["torque_nm"] = 2.0

    notes = raw.get("aspiration")
    if raw.get("architecture"):
        notes = f"{raw.get('architecture')}; {notes}" if notes else str(raw.get("architecture"))

    return ValidationCase(
        id=str(raw["id"]),
        system_type=SystemType.ENGINE,
        reference_source=manufacturer_source(
            name=str(manufacturer),
            citation=str(citation) if citation else None,
            year=int(year) if year is not None else None,
        ),
        inputs={k: v for k, v in inputs.items() if k != "aspiration_token"},
        measured_outputs=measured,
        uncertainty=uncertainty,
        validation_quality=quality,
        notes=notes,
    )


def load_engine_validation_cases(
    directory: Path | None = None,
) -> list[ValidationCase]:
    root = directory or REFERENCE_ENGINES
    cases: list[ValidationCase] = []
    for path in sorted(root.glob("*.json")):
        raw = json.loads(path.read_text())
        cases.append(engine_json_to_validation_case(raw))
    return cases


def _build_registry() -> dict[str, ValidationCase]:
    registry: dict[str, ValidationCase] = {}
    for case in load_engine_validation_cases():
        if case.id in registry:
            raise ValueError(f"Duplicate validation case id: {case.id}")
        registry[case.id] = case
    return registry


VALIDATION_CASE_REGISTRY: dict[str, ValidationCase] = _build_registry()


def get_validation_case(case_id: str) -> ValidationCase | None:
    return VALIDATION_CASE_REGISTRY.get(case_id)


def all_validation_cases() -> list[ValidationCase]:
    return list(VALIDATION_CASE_REGISTRY.values())


def cases_for_system(system_type: SystemType | str) -> list[ValidationCase]:
    st = SystemType(system_type) if isinstance(system_type, str) else system_type
    return [c for c in all_validation_cases() if c.system_type is st]
