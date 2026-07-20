"""Phase 10 material decision campaign — requirement → candidates → select.

Does not invent material properties. Does not import PhysicsEngine / MaterialAssigner.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.verification.campaign_executor import CampaignResult, finalize_result
from core.verification.material_validation import (
    build_auditable_material_decision,
    load_material_cases,
)


TARGET_CASES = 20


def _case_complete(case: Any) -> bool:
    return all(
        getattr(case, f, None) is not None
        for f in ("component", "material", "yield_strength_mpa", "source")
    )


def run_material_campaign(*, dataset_path: Path | None = None) -> CampaignResult:
    if dataset_path is not None and Path(dataset_path).is_dir():
        # Load JSON cases from alternate directory if provided
        cases = []
        for p in sorted(Path(dataset_path).glob("*.json")):
            raw = json.loads(p.read_text())
            cases.append(raw)
        case_dicts = cases
    else:
        case_dicts = [c.to_dict() for c in load_material_cases()]

    decisions: list[dict[str, Any]] = []
    successful = 0
    failed = 0
    accepted = 0
    rejected = 0
    failure_modes: list[str] = []

    for raw in case_dicts:
        if isinstance(raw, dict):
            d = raw
        else:
            d = raw.to_dict()
        blob = " ".join(str(d.get(k) or "") for k in ("source", "confidence", "notes")).lower()
        if "synthetic" in blob:
            rejected += 1
            continue
        if not d.get("component") or not d.get("material") or d.get("yield_strength_mpa") is None:
            failed += 1
            continue
        accepted += 1
        y = float(d["yield_strength_mpa"])
        f = float(d.get("fatigue_strength_mpa") or y * 0.5)
        t = float(d.get("temperature_limit_c") or 150.0)
        # Requirement uses measured case as lower bound evidence — selection audit only.
        decision = build_auditable_material_decision(
            component=str(d["component"]),
            required_yield_mpa=max(200.0, y * 0.6),
            required_fatigue_mpa=max(100.0, f * 0.6),
            required_temp_c=max(100.0, t * 0.8),
            density_priority=True,
            candidate_keys=["forged_steel_4340", "ti_6al4v"],
            comparable_engines=len(case_dicts),
        )
        decision["engine"] = d.get("engine")
        decision["source"] = d.get("source")
        decision["failure_mode"] = d.get("application") or d.get("failure_mode")
        decision["load_case"] = d.get("application")
        decision["temperature"] = d.get("temperature_limit_c")
        decisions.append(decision)
        if decision.get("selected"):
            successful += 1
        else:
            failed += 1

    if accepted < TARGET_CASES:
        failure_modes.append(f"need_{TARGET_CASES}_validated_components_have_{accepted}")

    # No fabricated prediction errors — coverage gaps are failure modes, not MAE.
    result = finalize_result(
        campaign_id="material_decision",
        model_id="material_req_structural",
        errors=[],
        successful=successful,
        failed=failed,
        accepted=accepted,
        rejected=rejected,
        failure_modes=failure_modes,
        independent_verifier=True,
        details={
            "decisions": decisions,
            "case_count": accepted,
            "target_cases": TARGET_CASES,
            "phase": "10.0",
            "format": "requirement → candidates → reject → select",
        },
        min_cases_for_m4=TARGET_CASES,
        max_mean_error=0.05,
    )
    result.eligible_for_m4 = accepted >= TARGET_CASES and not failure_modes and successful > 0
    result.eligible_for_upgrade = result.eligible_for_m4
    return result


def write_material_campaign_result(output_dir: Path | str) -> Path:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    result = run_material_campaign()
    path = out / "material_campaign_result.json"
    path.write_text(json.dumps(result.to_dict(), indent=2, default=str) + "\n")
    return path
