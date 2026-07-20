"""Recorded explicit maturity promotions — applied at registry load.

Written only by scripts/promote_model_maturity.py after campaign gates pass.
Never written by campaign evaluators.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from core.verification.model_maturity import ModelDescriptor, ModelMaturity, parse_maturity, validate_descriptor

PROMOTIONS_PATH = Path(__file__).resolve().parent / "recorded_promotions.json"


def load_recorded_promotions() -> dict[str, Any]:
    if not PROMOTIONS_PATH.exists():
        return {"phase": "8.5", "promotions": {}}
    return json.loads(PROMOTIONS_PATH.read_text())


def save_recorded_promotions(payload: dict[str, Any]) -> Path:
    PROMOTIONS_PATH.write_text(json.dumps(payload, indent=2, default=str) + "\n")
    return PROMOTIONS_PATH


def apply_recorded_promotions(
    registry: dict[str, ModelDescriptor],
) -> dict[str, ModelDescriptor]:
    """Return a new registry dict with recorded one-step promotions applied."""
    data = load_recorded_promotions()
    promotions = data.get("promotions") or {}
    out = dict(registry)
    for model_id, promo in promotions.items():
        if model_id not in out:
            continue
        desc = out[model_id]
        to = parse_maturity(promo["to"])
        frm = parse_maturity(promo["from"])
        if desc.maturity is not frm and desc.maturity is not to:
            # Already diverged — leave untouched.
            continue
        if desc.maturity is to:
            continue
        if desc.maturity is not frm:
            continue
        limitations = promo.get("known_limitations")
        updated = replace(
            desc,
            maturity=to,
            known_limitations=limitations or desc.known_limitations,
            independently_verified=bool(
                promo.get("independently_verified", desc.independently_verified)
            ),
            benchmarked=bool(promo.get("benchmarked", desc.benchmarked)),
        )
        validate_descriptor(updated)
        out[model_id] = updated
    return out
