"""M4 candidate simulation — reports eligibility without promoting."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.verification.campaign_gate import evaluate_m3_to_m4_campaign_gate
from core.verification.campaign_readiness import check_campaign_ready, m4_histogram_locked
from core.verification.model_maturity import ModelMaturity


def evaluate_m4_candidate(campaign_result: dict[str, Any]) -> dict[str, Any]:
    """Simulate M4 eligibility from a campaign_result.json payload."""
    reasons: list[str] = []
    campaign = campaign_result.get("campaign", "unknown")
    gate = campaign_result.get("gate", "")

    if campaign_result.get("eligible_for_upgrade"):
        pass  # necessary but not sufficient for M4
    else:
        reasons.append("campaign gate not passed")

    blocked = campaign_result.get("blocked_models") or []
    for block in blocked:
        reasons.append(f"blocked: {block.get('model')} — {block.get('reason')}")

    readiness_key = {
        "high_rpm_dynamics": None,
        "rod_validation": "rod_stress",
        "bmep": "bmep",
        "material": "material",
    }.get(campaign)
    if readiness_key:
        ready = check_campaign_ready(readiness_key)
        if not ready["ready"]:
            reasons.append(f"missing evidence — {ready['reason']}")

    evidence_summary = campaign_result.get("evidence_summary") or {}
    for model_id, summary in evidence_summary.items():
        if isinstance(summary, dict) and summary.get("gate") == "M3_to_M4":
            if not summary.get("eligible_for_upgrade"):
                missing = summary.get("missing") or []
                if missing:
                    reasons.append(f"{model_id}: {', '.join(missing)}")

    histogram = m4_histogram_locked()
    if histogram.get("M4", 0) != 0:
        reasons.append("maturity isolation violated — M4 must remain 0")

    eligible_models = campaign_result.get("eligible_models") or []
    if gate == "M3_to_M4" and not eligible_models:
        reasons.append("insufficient cases for M3→M4")

    passed = not reasons
    return {
        "campaign": campaign,
        "m4_eligibility": "PASS" if passed else "FAIL",
        "reasons": reasons or ["all checks satisfied (simulation only — no promotion)"],
        "histogram": histogram,
        "policy": "Simulation only. Does not mutate MODEL_REGISTRY or recorded promotions.",
    }


def load_and_evaluate(path: Path | str) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text())
    return evaluate_m4_candidate(payload)


def format_m4_candidate_report(result: dict[str, Any]) -> str:
    lines = [
        "M4 Eligibility:",
        result["m4_eligibility"],
        "Reasons:",
    ]
    for r in result["reasons"]:
        lines.append(f"- {r}")
    lines.append("")
    lines.append(f"Histogram M4={result['histogram'].get('M4', 0)} (locked at 0)")
    return "\n".join(lines)
