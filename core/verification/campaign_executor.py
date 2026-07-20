"""Phase 10 campaign execution — approved evidence → measurable campaign results.

Does not mutate maturity. Does not import PhysicsEngine / MaterialAssigner /
ConstraintEvaluator / EngineeringEvaluator.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.verification.evidence_store import load_approved
from core.verification.raw_evidence import RawEvidenceRecord


@dataclass
class CampaignResult:
    """Measurable outcome of one evidence campaign run."""

    campaign_id: str
    model_id: str
    sample_count: int = 0
    successful_cases: int = 0
    failed_cases: int = 0
    accepted_cases: int = 0
    rejected_cases: int = 0
    prediction_errors: list[float] = field(default_factory=list)
    mean_error: float | None = None
    max_error: float | None = None
    uncertainty: str | None = None
    failure_modes: list[str] = field(default_factory=list)
    eligible_for_upgrade: bool = False
    eligible_for_m4: bool = False
    independent_verifier: bool = False
    details: dict[str, Any] = field(default_factory=dict)
    generated_at: str = ""
    policy: str = (
        "Campaign execution reports eligibility only. "
        "Use scripts/promote_m4_model.py for explicit M3→M4 promotion."
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def reject_synthetic_evidence(records: list[RawEvidenceRecord]) -> tuple[list[RawEvidenceRecord], list[str]]:
    """Keep only non-synthetic, non-estimate approved measurements."""
    accepted: list[RawEvidenceRecord] = []
    rejected: list[str] = []
    for rec in records:
        if rec.measurement_type in {"synthetic", "estimate"}:
            rejected.append(rec.id)
            continue
        if rec.rejects() if hasattr(rec, "rejects") else False:
            rejected.append(rec.id)
            continue
        accepted.append(rec)
    return accepted, rejected


def _error_stats(errors: list[float]) -> dict[str, float | None]:
    if not errors:
        return {"mean_error": None, "max_error": None, "mae": None}
    abs_err = [abs(e) for e in errors]
    return {
        "mean_error": sum(abs_err) / len(abs_err),
        "max_error": max(abs_err),
        "mae": sum(abs_err) / len(abs_err),
        "bias": sum(errors) / len(errors),
    }


def uncertainty_label(mae: float | None, *, n: int) -> str:
    if mae is None or n < 3:
        return "unknown"
    if mae < 0.08:
        return "low"
    if mae < 0.15:
        return "medium"
    return "high"


class CampaignExecutor:
    """Dispatch campaign runs against approved evidence / campaign datasets."""

    def run_campaign(self, campaign_id: str, dataset_path: str | None = None) -> CampaignResult:
        path = Path(dataset_path) if dataset_path else None
        if campaign_id in {"rod_stress", "rod", "rod_validation"}:
            from core.verification.campaigns.rod_campaign import run_rod_stress_campaign

            return run_rod_stress_campaign(dataset_path=path)
        if campaign_id in {"bmep", "bmep_displacement", "bmep_distribution"}:
            from core.verification.campaigns.bmep_campaign import run_bmep_distribution_campaign

            return run_bmep_distribution_campaign(dataset_path=path)
        if campaign_id in {"material", "material_requirements", "material_decision"}:
            from core.verification.campaigns.material_campaign import run_material_campaign

            return run_material_campaign(dataset_path=path)
        raise ValueError(f"Unknown campaign_id: {campaign_id}")

    def run_all(self, output_dir: Path | str) -> dict[str, CampaignResult]:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        results = {
            "rod_stress": self.run_campaign("rod_stress"),
            "bmep": self.run_campaign("bmep"),
            "material": self.run_campaign("material"),
        }
        for cid, result in results.items():
            filename = {
                "rod_stress": "rod_campaign_result.json",
                "bmep": "bmep_campaign_result.json",
                "material": "material_campaign_result.json",
            }[cid]
            (out / filename).write_text(json.dumps(result.to_dict(), indent=2, default=str) + "\n")
        return results


def finalize_result(
    *,
    campaign_id: str,
    model_id: str,
    errors: list[float],
    successful: int,
    failed: int,
    accepted: int,
    rejected: int,
    failure_modes: list[str],
    independent_verifier: bool,
    details: dict[str, Any] | None = None,
    min_cases_for_m4: int = 10,
    max_mean_error: float = 0.15,
) -> CampaignResult:
    stats = _error_stats(errors)
    mean_err = stats["mean_error"]
    max_err = stats["max_error"]
    unc = uncertainty_label(mean_err, n=len(errors))
    eligible = (
        accepted >= min_cases_for_m4
        and mean_err is not None
        and mean_err < max_mean_error
        and independent_verifier
        and not failure_modes
        and unc != "unknown"
    )
    return CampaignResult(
        campaign_id=campaign_id,
        model_id=model_id,
        sample_count=accepted + rejected,
        successful_cases=successful,
        failed_cases=failed,
        accepted_cases=accepted,
        rejected_cases=rejected,
        prediction_errors=list(errors),
        mean_error=None if mean_err is None else round(mean_err, 4),
        max_error=None if max_err is None else round(max_err, 4),
        uncertainty=unc,
        failure_modes=list(failure_modes),
        eligible_for_upgrade=eligible,
        eligible_for_m4=eligible,
        independent_verifier=independent_verifier,
        details=details or {},
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


def approved_evidence_for_component(component_substr: str) -> list[RawEvidenceRecord]:
    """Load approved store records matching a component substring; drop synthetics."""
    approved = load_approved()
    matched = [
        r
        for r in approved
        if component_substr.lower() in (r.component or "").lower()
        or component_substr.lower() in (r.field or "").lower()
    ]
    accepted, _ = reject_synthetic_evidence(matched)
    return accepted
