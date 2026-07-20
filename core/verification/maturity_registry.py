"""M4 requirement checks — eligibility only; never mutates the registry.

Phase 10 facade over model_maturity / campaign gates.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.verification.campaign_gate import evaluate_m3_to_m4_campaign_gate
from core.verification.model_maturity import (
    M4_MIN_EXTERNAL_CASES,
    MaturityUpgradeEvidence,
    ModelMaturity,
    evaluate_m3_to_m4_upgrade,
)
from core.verification.model_registry import MODEL_REGISTRY

PROMOTIONS_PATH = Path(__file__).resolve().parent / "promotions.json"


def check_m4_requirements(
    model_id: str,
    campaign_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return M4 eligibility checklist for a model.

    Requires:
      - >=10 approved external cases
      - mean error + max error + uncertainty
      - independent verifier result
      - failure analysis (known failure regions / uncertainties / limitations)
    """
    if model_id not in MODEL_REGISTRY and model_id not in {
        "rod_stress",
        "bmep",
        "engine_cycle_model",
        "material_req_structural",
    }:
        return {"eligible": False, "reason": f"unknown model: {model_id}", "missing": ["model"]}

    desc = MODEL_REGISTRY.get(model_id)
    current = desc.maturity.name if desc else "unknown"

    result = campaign_result or {}
    evidence_cases = int(
        result.get("accepted_cases")
        or result.get("samples")
        or result.get("evidence_cases")
        or 0
    )
    mean_error = result.get("mean_error")
    max_error = result.get("max_error")
    uncertainty = result.get("uncertainty")
    independent = bool(result.get("independent_verifier"))
    failure_modes = list(result.get("failure_modes") or [])
    failure_analysis = bool(
        result.get("failure_modes") is not None
        or (result.get("details") or {}).get("failure_analysis")
        or result.get("known_failure_regions")
    )

    missing: list[str] = []
    if evidence_cases < M4_MIN_EXTERNAL_CASES:
        missing.append(f"external_cases>={M4_MIN_EXTERNAL_CASES} (have {evidence_cases})")
    if mean_error is None:
        missing.append("mean_error")
    if max_error is None:
        missing.append("maximum_error")
    if not uncertainty or uncertainty == "unknown":
        missing.append("uncertainty")
    if not independent:
        missing.append("independent_verifier")
    if not failure_analysis:
        missing.append("failure_analysis")

    # Synthetic rejection flag
    if result.get("rejected_cases") and result.get("accepted_cases", 0) == 0 and "synthetic" in str(
        result.get("details") or ""
    ):
        missing.append("synthetic_evidence_rejected_no_valid_cases")

    evidence = MaturityUpgradeEvidence(
        external_validation_cases=evidence_cases,
        mean_error_documented=mean_error is not None,
        uncertainty_documented=bool(uncertainty) and uncertainty != "unknown",
        independent_verifier_exists=independent,
        unresolved_major_failure_modes=tuple(failure_modes),
        failure_analysis_exists=failure_analysis,
    )
    gate = evaluate_m3_to_m4_upgrade(evidence)
    m4_gate = evaluate_m3_to_m4_campaign_gate(
        model_id=model_id,
        evidence_cases=evidence_cases,
        mean_error_fraction=None if mean_error is None else float(mean_error),
        uncertainty_quantified=bool(uncertainty) and uncertainty != "unknown",
        failure_modes=failure_modes,
        independent_verifier=independent,
    )

    eligible = False
    if "eligible_for_m4" in result:
        eligible = bool(result["eligible_for_m4"]) and len(missing) == 0 and gate["allowed"]
    elif "eligible_for_upgrade" in result:
        eligible = bool(result["eligible_for_upgrade"]) and len(missing) == 0 and gate["allowed"]
    else:
        eligible = gate["allowed"] and m4_gate["eligible_for_upgrade"] and len(missing) == 0

    reason = (
        "ok"
        if eligible
        else "missing requirement: "
        + ", ".join(missing or gate.get("missing") or ["campaign_not_eligible"])
    )
    return {
        "model_id": model_id,
        "current_maturity": current,
        "eligible": eligible,
        "reason": reason,
        "missing": missing or gate.get("missing") or [],
        "evidence_cases": evidence_cases,
        "required_cases": M4_MIN_EXTERNAL_CASES,
        "mean_error": mean_error,
        "max_error": max_error,
        "uncertainty": uncertainty,
        "independent_verifier": independent,
        "failure_modes": failure_modes,
        "m3_to_m4_gate": gate,
        "campaign_gate": m4_gate,
        "policy": "Eligibility only — promotion requires scripts/promote_m4_model.py",
    }


def build_maturity_progress() -> dict[str, Any]:
    """Per-campaign maturity progress for reality audit."""
    from core.verification.campaign_executor import CampaignExecutor
    from core.verification.campaigns.bmep_campaign import FAMILY_TARGETS
    from core.verification.campaigns.material_campaign import TARGET_CASES

    executor = CampaignExecutor()
    progress: dict[str, Any] = {}
    mapping = {
        "rod_stress": ("rod_stress", "rod_stress", 10),
        "bmep": ("bmep", "engine_cycle_model", sum(FAMILY_TARGETS.values())),
        "material": ("material", "material_req_structural", TARGET_CASES),
    }
    for key, (campaign_id, model_id, required) in mapping.items():
        result = executor.run_campaign(campaign_id)
        check = check_m4_requirements(model_id, result.to_dict())
        desc = MODEL_REGISTRY.get(model_id)
        current = "M3"
        if desc:
            current = desc.maturity.name
        elif key == "rod_stress":
            rod = MODEL_REGISTRY.get("calc_rod_stress_requirement") or MODEL_REGISTRY.get(
                "connecting_rod_model"
            )
            current = rod.maturity.name if rod else "M3"
        progress[key] = {
            "current": current,
            "evidence_cases": int(result.accepted_cases),
            "required_cases": required,
            "m4_ready": check["eligible"],
            "mean_error": result.mean_error,
            "uncertainty": result.uncertainty,
        }
    return progress


def load_promotions() -> dict[str, Any]:
    if not PROMOTIONS_PATH.exists():
        return {"phase": "10.0", "promotions": {}, "policy": "M4 promotions only via promote_m4_model.py"}
    return json.loads(PROMOTIONS_PATH.read_text())


def save_promotions(payload: dict[str, Any]) -> Path:
    PROMOTIONS_PATH.write_text(json.dumps(payload, indent=2, default=str) + "\n")
    return PROMOTIONS_PATH
