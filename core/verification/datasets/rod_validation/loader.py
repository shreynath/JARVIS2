"""Load RodValidationCase records from disk."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.verification.datasets.rod_validation.case import RodValidationCase

CASES_DIR = Path(__file__).resolve().parent / "cases"


def load_rod_cases() -> list[RodValidationCase]:
    cases: list[RodValidationCase] = []
    for path in sorted(CASES_DIR.glob("*.json")):
        raw = json.loads(path.read_text())
        cases.append(
            RodValidationCase(
                engine_name=str(raw["engine_name"]),
                engine_id=str(raw["engine_id"]),
                rpm=raw.get("rpm"),
                stroke_mm=raw.get("stroke_mm"),
                rod_length_mm=raw.get("rod_length_mm"),
                piston_mass_g=raw.get("piston_mass_g"),
                rod_mass_g=raw.get("rod_mass_g"),
                bore_mm=raw.get("bore_mm"),
                reported_component_data=dict(raw.get("reported_component_data") or {}),
                source=str(raw.get("source") or ""),
                confidence=str(raw.get("confidence") or "low"),
            )
        )
    return cases


def rod_dataset_inventory() -> dict[str, Any]:
    cases = load_rod_cases()
    return {
        "total_cases": len(cases),
        "with_geometry": sum(1 for c in cases if c.has_geometry),
        "with_absolute_mass": sum(1 for c in cases if c.has_absolute_mass),
        "with_rod_length": sum(1 for c in cases if c.rod_length_mm is not None),
        "policy": "Missing masses remain null — never estimated for M4 claims.",
    }
