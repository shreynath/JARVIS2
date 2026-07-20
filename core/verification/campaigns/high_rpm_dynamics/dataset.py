"""High-RPM dynamics campaign dataset — published values only; null stays null."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CAMPAIGN_ID = "high_rpm_dynamics"
REQUIRED_ENGINE_IDS = (
    "honda_f20c",
    "ferrari_f136",
    "ferrari_f140",
    "lexus_lfa_1lr_gue",
    "porsche_991_gt3_ma1",
)

REFERENCES_DIR = Path(__file__).resolve().parent / "references"

# Fields that must never be invented by loaders.
NULLABLE_PUBLISHED_FIELDS = (
    "torque_nm",
    "compression_ratio",
    "mean_piston_speed_m_s",
    "peak_piston_acceleration_m_s2",
    "mass_kg",
)


def load_high_rpm_dataset() -> list[dict[str, Any]]:
    """Load campaign references. Missing published fields remain null."""
    engines: list[dict[str, Any]] = []
    for eid in REQUIRED_ENGINE_IDS:
        path = REFERENCES_DIR / f"{eid}.json"
        if not path.exists():
            raise FileNotFoundError(f"Campaign reference missing: {path}")
        data = json.loads(path.read_text())
        if data.get("id") != eid:
            raise ValueError(f"id mismatch in {path}: {data.get('id')!r}")
        if not data.get("verified_sources"):
            raise ValueError(f"{eid}: verified_sources required")
        pub = data.setdefault("published", {})
        for field in NULLABLE_PUBLISHED_FIELDS:
            # Do not fill missing keys with estimates — explicit null only.
            if field not in pub:
                pub[field] = None
        engines.append(data)
    return engines


def assert_no_invented_values(engine: dict[str, Any]) -> None:
    """Guard: published nullable fields must be number or null — not filler strings."""
    pub = engine.get("published") or {}
    for field in NULLABLE_PUBLISHED_FIELDS:
        value = pub.get(field)
        if value is None:
            continue
        if isinstance(value, (int, float)):
            continue
        raise ValueError(f"{engine.get('id')}: invented/non-numeric {field}={value!r}")
