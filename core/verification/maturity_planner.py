"""Maturity upgrade planner — missing-evidence roadmaps only (no auto-upgrade)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.verification.evidence_registry import (
    EVIDENCE_REQUIREMENTS,
    blocking_evidence_for,
    requirements_for,
)
from core.verification.model_impact import IMPACT_WEIGHT
from core.verification.model_maturity import MATURITY_RANK, ModelMaturity
from core.verification.model_registry import MODEL_REGISTRY
from verification.impact_analysis import analyze_model_impact


# Aspired near-term footprint (Phase 8 program target — not a claim of current state).
NEAR_TERM_TARGET_BANDS: dict[str, tuple[int, int]] = {
    "M0": (0, 2),
    "M1": (0, 1),
    "M2": (5, 8),
    "M3": (12, 99),
    "M4": (2, 4),
    "M5": (0, 0),
}


def _priority_from_roi(roi: float) -> str:
    if roi >= 80:
        return "very_high"
    if roi >= 40:
        return "high"
    if roi >= 15:
        return "medium"
    return "low"


def _next_maturity(current: ModelMaturity) -> ModelMaturity | None:
    rank = MATURITY_RANK[current]
    if rank >= MATURITY_RANK[ModelMaturity.M5]:
        return None
    for m in ModelMaturity:
        if MATURITY_RANK[m] == rank + 1:
            return m
    return None


def research_roi(
    *,
    impact_weight: float,
    uncertainty: float,
    dependency_count: float,
    maturity_gap: float,
) -> float:
    """If engineering time improves one model, how much reliability gain?

    upgrade_value = impact * uncertainty * dependency_count * maturity_gap
    """
    return float(impact_weight) * float(uncertainty) * float(dependency_count) * float(
        maturity_gap
    )


def build_maturity_roadmap(
    *,
    impact_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    impact = impact_report or analyze_model_impact({})
    models_meta = impact.get("models") or {}
    rows: list[dict[str, Any]] = []

    for model_id, desc in sorted(MODEL_REGISTRY.items()):
        nxt = _next_maturity(desc.maturity)
        req = requirements_for(model_id)
        target = req.target if req is not None else nxt
        if target is None:
            continue
        meta = models_meta.get(model_id) or {}
        gap = max(0, MATURITY_RANK[target] - MATURITY_RANK[desc.maturity])
        # Prefer remaining gap to M4 research horizon for ROI when still below M4.
        horizon = max(gap, max(0, MATURITY_RANK[ModelMaturity.M4] - MATURITY_RANK[desc.maturity]))
        uncertainty = float(meta.get("uncertainty") or 1.0)
        dep_count = float(meta.get("dependency_count") or len(desc.affected_outputs) or 1)
        impact_w = float(IMPACT_WEIGHT[desc.impact_level])
        roi = research_roi(
            impact_weight=impact_w,
            uncertainty=uncertainty,
            dependency_count=dep_count,
            maturity_gap=max(horizon, 0.5),
        )
        blocking = blocking_evidence_for(model_id)
        rows.append(
            {
                "model": model_id,
                "current": desc.maturity.name,
                "next": (nxt.name if nxt else None),
                "program_target": target.name if target else None,
                "blocking_evidence": blocking,
                "priority": _priority_from_roi(roi),
                "upgrade_value_roi": round(roi, 3),
                "impact": desc.impact_level.value,
                "campaign": None if req is None else req.campaign,
                "rationale": None if req is None else req.rationale,
                "benchmarked": desc.benchmarked,
                "independently_verified": desc.independently_verified,
            }
        )

    rows.sort(key=lambda r: (-r["upgrade_value_roi"], r["model"]))
    counts = {m.name: 0 for m in ModelMaturity}
    for d in MODEL_REGISTRY.values():
        counts[d.maturity.name] += 1

    return {
        "phase": "8.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "policy": (
            "Roadmap lists missing evidence only. Registry maturity does not change "
            "because sophistication increased."
        ),
        "current_histogram": counts,
        "near_term_target_bands": {
            k: {"min": v[0], "max": v[1]} for k, v in NEAR_TERM_TARGET_BANDS.items()
        },
        "near_term_note": (
            "Targets are aspired program outcomes after evidence campaigns — not claims."
        ),
        "roadmap": rows,
        "evidence_program_size": len(EVIDENCE_REQUIREMENTS),
        "m5_policy": "M5 should remain 0 until physical testing + field correlation exist.",
    }


def write_maturity_roadmap(
    output_dir: Path | str,
    *,
    impact_report: dict[str, Any] | None = None,
) -> Path:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "maturity_roadmap.json"
    path.write_text(
        json.dumps(build_maturity_roadmap(impact_report=impact_report), indent=2, default=str)
    )
    return path
