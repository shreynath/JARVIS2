"""Campaign maturity gates — eligibility only; never mutates the registry."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.verification.model_maturity import (
    MaturityUpgradeEvidence,
    ModelMaturity,
    evaluate_upgrade,
    parse_maturity,
)


@dataclass
class CampaignResult:
    campaign: str
    eligible_for_upgrade: bool
    eligible_models: list[str] = field(default_factory=list)
    blocked_models: list[dict[str, Any]] = field(default_factory=list)
    gate: str = "M2_to_M3"
    generated_at: str = ""
    evidence_summary: dict[str, Any] = field(default_factory=dict)
    policy: str = (
        "Gate reports eligibility only. Use scripts/promote_model_maturity.py "
        "to apply an explicit one-step promotion after reviewing evidence."
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _model_row(validation: dict[str, Any], model_id: str) -> dict[str, Any] | None:
    for row in validation.get("models") or []:
        if row.get("model") == model_id:
            return row
    return None


def evaluate_m2_to_m3_campaign_gate(
    *,
    model_id: str,
    validation_row: dict[str, Any],
    failure_packet: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Checklist for M2→M3: independent verifier, refs, equations, error, uncertainty, failures."""
    required = {
        "independent_verifier": bool(validation_row.get("independent_verifier")),
        "external_references": int(validation_row.get("samples") or 0) >= 3,
        "documented_equations": bool(validation_row.get("equations_documented")),
        "error_distribution": validation_row.get("mean_error") is not None,
        "uncertainty_estimate": bool(str(validation_row.get("uncertainty") or "").strip()),
        "known_failure_modes_documented": bool(
            validation_row.get("known_limitations")
            or (failure_packet or {}).get("failures") is not None
            or (failure_packet or {}).get("non_blocking_known_limitations")
        ),
        "campaign_passed": bool(validation_row.get("passed")),
    }
    missing = [k for k, ok in required.items() if not ok]
    evidence = MaturityUpgradeEvidence(
        external_comparison_exists=required["external_references"]
        and required["campaign_passed"],
        error_characterization_exists=required["error_distribution"]
        and required["campaign_passed"],
        failure_analysis_exists=required["known_failure_modes_documented"],
        assumptions_documented=required["documented_equations"],
        uncertainty_range_documented=required["uncertainty_estimate"],
        references_documented=required["external_references"],
        independent_verifier_exists=required["independent_verifier"],
    )
    step = evaluate_upgrade(
        from_maturity=ModelMaturity.M2,
        to_maturity=ModelMaturity.M3,
        evidence=evidence,
    )
    eligible = step["allowed"] and not missing
    return {
        "model": model_id,
        "gate": "M2_to_M3",
        "checklist": required,
        "missing": missing,
        "upgrade_evaluation": step,
        "eligible_for_upgrade": eligible,
    }


def evaluate_high_rpm_campaign_gate(
    validation: dict[str, Any],
    failure_packet: dict[str, Any] | None = None,
) -> CampaignResult:
    """Build CampaignResult for torque / MPS / acceleration (and optional displacement)."""
    targets = (
        "calc_torque",
        "calc_mean_piston_speed",
        "calc_piston_acceleration",
    )
    eligible: list[str] = []
    blocked: list[dict[str, Any]] = []
    summaries: dict[str, Any] = {}

    for mid in targets:
        row = _model_row(validation, mid)
        if row is None:
            blocked.append({"model": mid, "reason": "missing_from_validation_report"})
            continue
        gate = evaluate_m2_to_m3_campaign_gate(
            model_id=mid, validation_row=row, failure_packet=failure_packet
        )
        summaries[mid] = gate
        if gate["eligible_for_upgrade"]:
            eligible.append(mid)
        else:
            blocked.append(
                {
                    "model": mid,
                    "reason": "gate_incomplete",
                    "missing": gate["missing"],
                }
            )

    # Displacement / BMEP estimate — optional; typically blocked.
    disp = _model_row(validation, "displacement_estimation")
    if disp is not None:
        gate = evaluate_m2_to_m3_campaign_gate(
            model_id="displacement_estimation",
            validation_row=disp,
            failure_packet=failure_packet,
        )
        summaries["displacement_estimation"] = gate
        if gate["eligible_for_upgrade"]:
            eligible.append("displacement_estimation")
        else:
            blocked.append(
                {
                    "model": "displacement_estimation",
                    "reason": "BMEP assumption uncertainty"
                    if not disp.get("passed")
                    else "gate_incomplete",
                    "missing": gate["missing"],
                    "action": "requires BMEP campaign",
                }
            )

    return CampaignResult(
        campaign="high_rpm_dynamics",
        eligible_for_upgrade=bool(eligible),
        eligible_models=eligible,
        blocked_models=blocked,
        gate="M2_to_M3",
        generated_at=datetime.now(timezone.utc).isoformat(),
        evidence_summary=summaries,
    )


def assert_not_m4_claim(from_maturity: ModelMaturity | str, to_maturity: ModelMaturity | str) -> None:
    """Campaign A (kinematic identities) must not claim M4."""
    frm = parse_maturity(from_maturity)
    to = parse_maturity(to_maturity)
    if to is ModelMaturity.M4 or to is ModelMaturity.M5:
        raise ValueError(
            f"Campaign A forbids claiming {to.name} (from {frm.name}). "
            "Use predictive benchmark campaigns (rod/BMEP) with M3→M4 gates."
        )


def evaluate_m3_to_m4_campaign_gate(
    *,
    model_id: str,
    evidence_cases: int,
    mean_error_fraction: float | None,
    uncertainty_quantified: bool,
    failure_modes: list[str],
    independent_verifier: bool,
    max_error_fraction: float = 0.15,
) -> dict[str, Any]:
    """Rod/BMEP-style M3→M4 checklist. Does not mutate registry."""
    evidence = MaturityUpgradeEvidence(
        external_validation_cases=int(evidence_cases),
        mean_error_documented=mean_error_fraction is not None,
        uncertainty_documented=bool(uncertainty_quantified),
        independent_verifier_exists=bool(independent_verifier),
        unresolved_major_failure_modes=tuple(failure_modes),
    )
    step = evaluate_upgrade(
        from_maturity=ModelMaturity.M3,
        to_maturity=ModelMaturity.M4,
        evidence=evidence,
    )
    checklist = {
        "external_cases_ge_10": evidence_cases >= 10,
        "mean_error_documented": mean_error_fraction is not None,
        "mean_error_under_15_percent": (
            mean_error_fraction is not None and mean_error_fraction < max_error_fraction
        ),
        "uncertainty_quantified": uncertainty_quantified,
        "failure_modes_documented": True,  # presence of list (may be empty = none found)
        "no_unresolved_major_failures": len(failure_modes) == 0,
        "independent_verifier": independent_verifier,
    }
    missing = [k for k, ok in checklist.items() if not ok]
    eligible = step["allowed"] and not missing
    return {
        "model": model_id,
        "gate": "M3_to_M4",
        "checklist": checklist,
        "missing": missing,
        "upgrade_evaluation": step,
        "eligible_for_upgrade": eligible,
    }


def write_campaign_result(
    output_dir: Path | str,
    *,
    validation: dict[str, Any],
    failure_packet: dict[str, Any] | None = None,
) -> Path:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    result = evaluate_high_rpm_campaign_gate(validation, failure_packet)
    path = out / "campaign_result.json"
    path.write_text(json.dumps(result.to_dict(), indent=2, default=str))
    return path


def write_generic_campaign_result(
    output_dir: Path | str,
    *,
    filename: str,
    result: CampaignResult,
) -> Path:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / filename
    path.write_text(json.dumps(result.to_dict(), indent=2, default=str))
    return path
