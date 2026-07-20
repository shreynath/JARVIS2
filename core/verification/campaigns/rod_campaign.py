"""Phase 10 rod stress campaign execution — measurable errors, no maturity mutation.

Reuses rod_verifier equations. Does not invent masses. Does not import PhysicsEngine.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.verification.campaign_executor import (
    CampaignResult,
    finalize_result,
    reject_synthetic_evidence,
)
from core.verification.datasets.rod_validation.loader import load_rod_cases
from core.verification.evidence_store import load_approved
from core.verification.independent_campaign_validator import IndependentCampaignValidator
from core.verification.rod_verifier import verify_case


REQUIRED_FIELDS = (
    "engine_name",
    "rpm",
    "stroke_mm",
    "piston_mass_g",
    "rod_mass_g",
    "rod_length_mm",
)


def _case_complete(case: Any) -> bool:
    return all(
        getattr(case, f, None) is not None
        for f in ("rpm", "stroke_mm", "piston_mass_g", "rod_mass_g", "rod_length_mm")
    )


def _load_cases_from_path(dataset_path: Path | None) -> list[Any]:
    if dataset_path is None:
        return list(load_rod_cases())
    path = Path(dataset_path)
    if path.is_dir():
        cases = []
        for p in sorted(path.glob("*.json")):
            raw = json.loads(p.read_text())
            cases.append(raw)
        return cases
    if path.suffix == ".json":
        payload = json.loads(path.read_text())
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict) and "cases" in payload:
            return list(payload["cases"])
        return [payload]
    raise ValueError(f"Unsupported rod dataset path: {dataset_path}")


def _reject_synthetic_cases(cases: list[Any]) -> tuple[list[Any], int]:
    """Drop cases marked synthetic in source/confidence/notes."""
    kept = []
    rejected = 0
    for c in cases:
        if hasattr(c, "to_dict"):
            d = c.to_dict()
        else:
            d = dict(c)
        blob = " ".join(
            str(d.get(k) or "")
            for k in ("source", "confidence", "notes", "measurement_type")
        ).lower()
        if "synthetic" in blob or "estimate" in blob:
            rejected += 1
            continue
        kept.append(c if not isinstance(c, dict) else c)
    return kept, rejected


def run_rod_stress_campaign(*, dataset_path: Path | None = None) -> CampaignResult:
    """Execute rod stress campaign. Eligibility is earned, never forced."""
    cases = _load_cases_from_path(dataset_path)
    cases, synth_rejected = _reject_synthetic_cases(cases)

    # Approved raw evidence that is synthetic must also be counted as rejected.
    approved = load_approved()
    _, approved_synth = reject_synthetic_evidence(
        [r for r in approved if "rod" in (r.component or "").lower() or "piston" in (r.field or "")]
    )

    validator = IndependentCampaignValidator()
    errors: list[float] = []
    successful = 0
    failed = 0
    case_rows: list[dict[str, Any]] = []
    failure_modes: list[str] = []

    complete_cases = 0
    for case in cases:
        if hasattr(case, "to_dict"):
            cdict = case.to_dict()
            complete = _case_complete(case)
        else:
            cdict = dict(case)
            complete = all(cdict.get(f) is not None for f in REQUIRED_FIELDS if f != "engine_name")

        row = verify_case(cdict)
        indep = validator.rod_stress_packet(cdict)
        row["independent"] = indep

        if not complete:
            failed += 1
            row["campaign_status"] = "incomplete"
            case_rows.append(row)
            continue

        complete_cases += 1
        # Relative error proxy: when external stress/load reference exists use it;
        # otherwise document that absolute error cannot be computed (null stays null).
        external_stress = None
        rcd = cdict.get("reported_component_data") or {}
        if isinstance(rcd, dict):
            external_stress = rcd.get("measured_stress_mpa") or rcd.get("reference_stress_mpa")

        pred_force = row.get("independent_inertia_force_n")
        if external_stress is not None and indep.get("stress_mpa") is not None:
            err = abs(float(indep["stress_mpa"]) - float(external_stress)) / max(
                abs(float(external_stress)), 1e-9
            )
            errors.append(err)
            successful += 1
            row["campaign_status"] = "compared"
            row["relative_error"] = err
        elif pred_force is not None:
            # Absolute load computable but no external stress bench — successful computation,
            # not an external error sample for M4.
            successful += 1
            row["campaign_status"] = "absolute_computable_no_external_benchmark"
        else:
            failed += 1
            row["campaign_status"] = "failed"
        case_rows.append(row)

    if complete_cases < 10:
        failure_modes.append("insufficient_complete_rod_cases")
    if not errors and complete_cases == 0:
        failure_modes.append("missing_published_piston_and_rod_mass")
    if not errors and complete_cases > 0:
        failure_modes.append("no_external_stress_benchmarks_for_error")

    result = finalize_result(
        campaign_id="rod_stress",
        model_id="rod_stress",
        errors=errors,
        successful=successful,
        failed=failed,
        accepted=complete_cases,
        rejected=synth_rejected + len(approved_synth),
        failure_modes=failure_modes,
        independent_verifier=True,
        details={
            "cases": case_rows,
            "complete_cases": complete_cases,
            "required_fields": list(REQUIRED_FIELDS),
            "phase": "10.0",
            "note": (
                "Predicted rod loading / stress / fatigue / buckling via independent verifier. "
                "M4 requires ≥10 complete cases with external error characterization."
            ),
        },
    )
    # Surface common summary fields expected by reports
    result.details["samples"] = complete_cases
    result.details["eligible_for_m4"] = result.eligible_for_m4
    return result


def write_rod_campaign_result(output_dir: Path | str) -> Path:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    result = run_rod_stress_campaign()
    path = out / "rod_campaign_result.json"
    # Compact summary + full payload
    summary = {
        "model": "rod_stress",
        "samples": result.accepted_cases,
        "mean_error": result.mean_error,
        "max_error": result.max_error,
        "eligible_for_m4": result.eligible_for_m4,
        "uncertainty": result.uncertainty,
        "failure_modes": result.failure_modes,
        **result.to_dict(),
    }
    path.write_text(json.dumps(summary, indent=2, default=str) + "\n")
    return path
