"""Failure / research prioritization — high impact × uncertainty × lack of validation."""

from __future__ import annotations

from typing import Any

from core.verification.model_impact import IMPACT_WEIGHT, ImpactLevel
from core.verification.model_maturity import MATURITY_RANK, ModelMaturity
from core.verification.model_registry import MODEL_REGISTRY


def _uncertainty_score(maturity: ModelMaturity, independently_verified: bool, benchmarked: bool) -> float:
    # Higher = more uncertain. Inverse of maturity rank + evidence gaps.
    base = (5 - MATURITY_RANK[maturity]) / 5.0 * 3.0
    if not independently_verified:
        base += 1.0
    if not benchmarked:
        base += 1.5
    return base


def _validation_deficit(benchmarked: bool, independently_verified: bool, case_coverage: int) -> float:
    deficit = 0.0
    if not benchmarked:
        deficit += 2.0
    if not independently_verified:
        deficit += 1.0
    if case_coverage < 10:
        deficit += (10 - case_coverage) / 10.0 * 2.0
    return deficit


def rank_failure_risks(
    *,
    external_case_count: int,
    error_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Research prioritization — not optimization."""
    quantity_bias = {}
    if error_report:
        for side in ("independent_verification_model", "jarvis_open_loop"):
            block = error_report.get(side) or {}
            for q, meta in (block.get("quantities") or {}).items():
                quantity_bias[q] = meta

    risks: list[dict[str, Any]] = []
    for model_id, desc in MODEL_REGISTRY.items():
        impact_w = IMPACT_WEIGHT[desc.impact_level]
        uncertainty = _uncertainty_score(
            desc.maturity, desc.independently_verified, desc.benchmarked
        )
        lack = _validation_deficit(
            desc.benchmarked, desc.independently_verified, external_case_count
        )
        risk = impact_w * uncertainty * max(lack, 0.5)
        recommendation = "monitor"
        if desc.maturity.value in {"placeholder", "heuristic"} or MATURITY_RANK[desc.maturity] <= 1:
            recommendation = "requires experimental validation"
        elif not desc.benchmarked and desc.impact_level in {
            ImpactLevel.HIGH,
            ImpactLevel.CRITICAL,
        }:
            recommendation = "requires external calibration dataset + error bounds"
        elif MATURITY_RANK[desc.maturity] >= 3 and not desc.benchmarked:
            recommendation = "M4 withheld until ≥10 external cases with documented error"
        risks.append(
            {
                "model": model_id,
                "maturity": desc.maturity.name,
                "impact": desc.impact_level.value,
                "risk_score": round(risk, 3),
                "uncertainty_score": round(uncertainty, 3),
                "validation_deficit": round(lack, 3),
                "recommendation": recommendation,
                "known_limitations": desc.known_limitations,
            }
        )

    risks.sort(key=lambda r: (-r["risk_score"], r["model"]))
    return {
        "highest_risk_models": risks[:12],
        "all_models": risks,
        "scoring": "risk = impact_weight × uncertainty × lack_of_validation",
        "external_case_count": external_case_count,
        "policy": "Research prioritization only — does not mutate engineering models.",
    }
