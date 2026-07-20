"""Maturity scorecard + research ROI ranking."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.verification.maturity_planner import build_maturity_roadmap
from core.verification.model_maturity import MATURITY_RANK, ModelMaturity
from core.verification.model_registry import MODEL_REGISTRY
from verification.impact_analysis import analyze_model_impact


def build_maturity_scorecard(
    *,
    impact_report: dict[str, Any] | None = None,
    roadmap: dict[str, Any] | None = None,
) -> dict[str, Any]:
    impact = impact_report or analyze_model_impact({})
    road = roadmap or build_maturity_roadmap(impact_report=impact)
    ranks = [MATURITY_RANK[d.maturity] for d in MODEL_REGISTRY.values()]
    overall = sum(ranks) / len(ranks) if ranks else 0.0

    # Highest confidence ≈ highest maturity with independent verification / benchmarks.
    scored = []
    for mid, desc in MODEL_REGISTRY.items():
        conf = MATURITY_RANK[desc.maturity]
        if desc.independently_verified:
            conf += 0.5
        if desc.benchmarked:
            conf += 0.5
        scored.append((conf, -desc.sensitivity_rank, mid))
    scored.sort(reverse=True)
    highest = [mid for _, __, mid in scored[:5]]

    # Largest risk: low maturity × high impact / sensitivity.
    risk = []
    for mid, desc in MODEL_REGISTRY.items():
        meta = (impact.get("models") or {}).get(mid) or {}
        risk_score = (
            (5 - MATURITY_RANK[desc.maturity])
            * float(meta.get("uncertainty") or 1.0)
            * (51 - desc.sensitivity_rank)
        )
        risk.append((risk_score, mid))
    risk.sort(reverse=True)
    largest_risk = [mid for _, mid in risk[:5]]

    upgrade_rows = list(road.get("roadmap") or [])
    best_upgrade = [r["model"] for r in upgrade_rows[:5]]

    hist = {m.name: 0 for m in ModelMaturity}
    for d in MODEL_REGISTRY.values():
        hist[d.maturity.name] += 1

    return {
        "phase": "8.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "overall_maturity": round(overall, 3),
        "histogram": hist,
        "highest_confidence_models": highest,
        "largest_risk_models": largest_risk,
        "best_upgrade_candidates": best_upgrade,
        "research_roi_top": [
            {
                "model": r["model"],
                "upgrade_value": r["upgrade_value_roi"],
                "current": r["current"],
                "next": r["next"],
                "blocking_evidence": r["blocking_evidence"][:4],
            }
            for r in upgrade_rows[:8]
        ],
        "roi_formula": "upgrade_value = impact × uncertainty × dependency_count × maturity_gap",
        "near_term_target_bands": road.get("near_term_target_bands"),
        "policy": (
            "Scorecard guides evidence spend. M5 remains off-limits without physical/"
            "field validation. Prefer many honest M3/M4 models over inflated M5 labels."
        ),
        "m4_count": hist["M4"],
        "m5_count": hist["M5"],
    }


def write_maturity_scorecard(
    output_dir: Path | str,
    *,
    impact_report: dict[str, Any] | None = None,
) -> Path:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    impact = impact_report or analyze_model_impact({})
    road = build_maturity_roadmap(impact_report=impact)
    scorecard = build_maturity_scorecard(impact_report=impact, roadmap=road)
    path = out / "maturity_scorecard.json"
    path.write_text(json.dumps(scorecard, indent=2, default=str))
    return path


__all__ = [
    "build_maturity_scorecard",
    "write_maturity_scorecard",
]
