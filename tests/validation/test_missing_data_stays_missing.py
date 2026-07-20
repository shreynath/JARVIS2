"""Phase 6 — missing published fields stay null (never invented)."""

from __future__ import annotations

import json
from pathlib import Path

from core.verification.datasets.registry import engine_json_to_validation_case, load_engine_validation_cases

ENGINES = Path(__file__).resolve().parents[2] / "datasets" / "reference_engines"


def test_missing_compression_ratio_stays_null():
    # Cosworth DFV historically may not list CR in our dataset → must remain None
    raw = json.loads((ENGINES / "cosworth_dfv.json").read_text())
    case = engine_json_to_validation_case(raw)
    # If published lacks compression_ratio OR sets null, measured stays None
    if raw.get("published", {}).get("compression_ratio") is None:
        assert case.measured_outputs.get("compression_ratio") is None


def test_missing_mass_stays_null_for_engines_without_mass():
    cases = {c.id: c for c in load_engine_validation_cases()}
    # Most OEM sheets in this repo omit dry mass
    f20c = cases["honda_f20c"]
    assert f20c.measured_outputs.get("mass_kg") is None or isinstance(
        f20c.measured_outputs.get("mass_kg"), (int, float)
    )
    # Explicit: adapter never invents a number when published mass is null
    raw = json.loads((ENGINES / "honda_f20c.json").read_text())
    raw["published"]["mass_kg"] = None
    raw["published"].pop("dry_mass_kg", None)
    case = engine_json_to_validation_case(raw)
    assert case.measured_outputs["mass_kg"] is None


def test_adapter_does_not_fill_unknown_with_defaults():
    raw = {
        "id": "synthetic_partial",
        "name": "Synthetic",
        "manufacturer": "Test",
        "published": {
            "horsepower": 100,
            "max_rpm": 7000,
            "displacement_l": 2.0,
            "bore_mm": 86.0,
            "stroke_mm": 86.0,
            "cylinder_count": 4,
            "torque_nm": None,
            "compression_ratio": None,
            "mass_kg": None,
        },
        "data_quality": "published_oem_geometry_power",
    }
    case = engine_json_to_validation_case(raw)
    assert case.measured_outputs["torque_nm"] is None
    assert case.measured_outputs["compression_ratio"] is None
    assert case.measured_outputs["mass_kg"] is None
    assert case.measured_outputs["displacement_l"] == 2.0
