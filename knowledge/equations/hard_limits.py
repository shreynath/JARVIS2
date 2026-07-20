"""Hard-limit provenance — nothing remains an anonymous magic number."""

from __future__ import annotations

from typing import Any

HARD_LIMIT_CATALOG: dict[str, dict[str, Any]] = {
    "mean_piston_speed_m_s": {
        "value": 26.0,
        "unit": "m/s",
        "classification": "engineering_standard",
        "origin": (
            "High-performance production / racing guideline: mean piston speeds above "
            "~20–25 m/s are extreme; 26 m/s used as a hard-limit gate for pass/fail."
        ),
        "reference": {
            "citation": "Industry practice / Heywood-range discussion of piston speed severity",
            "confidence": "medium",
            "note": (
                "Not a physics law. Not a single SAE/ISO mandatory number. "
                "Treated as a CONSERVATIVE_ESTIMATE / engineering_standard gate."
            ),
        },
        "confidence": "medium",
    },
}
