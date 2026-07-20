"""Rank external data acquisition priorities for human researchers."""

from __future__ import annotations

from typing import Any

from core.verification.evidence_collection import build_evidence_collection_plan
from verification.impact_analysis import analyze_model_impact
from core.verification.model_maturity import ModelMaturity
from core.verification.model_registry import MODEL_REGISTRY


MATURITY_GAP_WEIGHT = {
    ModelMaturity.M0: 5,
    ModelMaturity.M1: 4,
    ModelMaturity.M2: 3,
    ModelMaturity.M3: 2,
    ModelMaturity.M4: 1,
    ModelMaturity.M5: 0,
}


def _missing_evidence_ratio(model_id: str, plan: dict[str, Any]) -> float:
    if model_id in {"rod_stress", "connecting_rod_model"}:
        needed = plan.get("rod_stress", {}).get("needed", [])
        if not needed:
            return 1.0
        ratios = []
        for block in needed:
            tgt = block.get("target") or 1
            cur = block.get("current") or 0
            ratios.append(max(0.0, 1.0 - cur / tgt))
        return sum(ratios) / len(ratios)
    if model_id in {"bmep", "engine_cycle_model", "calc_bmep"}:
        needed = plan.get("bmep_displacement", {}).get("needed", {})
        if not needed:
            return 1.0
        ratios = []
        for block in needed.values():
            tgt = block.get("target") or 1
            cur = block.get("current") or 0
            ratios.append(max(0.0, 1.0 - cur / tgt))
        return sum(ratios) / len(ratios)
    if model_id in {"material_requirements", "material_decision"}:
        block = plan.get("material_requirements", {}).get("needed", [{}])[0]
        tgt = block.get("target") or 20
        cur = block.get("current") or 0
        return max(0.0, 1.0 - cur / tgt)
    return 0.5


def compute_acquisition_priorities(*, top_n: int = 10) -> list[dict[str, Any]]:
    plan = build_evidence_collection_plan()
    impact_report = analyze_model_impact()
    impact_rows = impact_report.get("models") or {}

    ranked: list[dict[str, Any]] = []
    for model_id, desc in MODEL_REGISTRY.items():
        impact_row = impact_rows.get(model_id, {})
        impact = float(impact_row.get("closure_impact_score") or 50)
        uncertainty = float(impact_row.get("uncertainty") or 1.0)
        dependency_count = int(impact_row.get("dependency_count") or len(desc.affected_outputs or ()))
        maturity_gap = MATURITY_GAP_WEIGHT.get(desc.maturity, 1)
        missing_ratio = _missing_evidence_ratio(model_id, plan)
        priority = round(
            impact * uncertainty * max(1, dependency_count) * maturity_gap * max(0.1, missing_ratio),
            1,
        )
        outputs = impact_row.get("outputs") or list(desc.affected_outputs or ())
        reason = (
            f"Controls {', '.join(outputs[:3])}"
            if outputs
            else f"Maturity {desc.maturity.name} evidence gap"
        )
        ranked.append(
            {
                "model": model_id,
                "priority": priority,
                "impact": impact,
                "uncertainty": uncertainty,
                "dependency_count": dependency_count,
                "maturity_gap": maturity_gap,
                "missing_evidence_ratio": round(missing_ratio, 3),
                "reason": reason,
            }
        )

    ranked.sort(key=lambda r: r["priority"], reverse=True)
    return ranked[:top_n]


def format_priority_report(*, top_n: int = 10) -> str:
    rows = compute_acquisition_priorities(top_n=top_n)
    lines = ["Data Acquisition Priorities", "=" * 30]
    for i, row in enumerate(rows, 1):
        lines.append(f"{i}. {row['model']} — priority {row['priority']}")
        lines.append(f"   {row['reason']}")
    return "\n".join(lines)
