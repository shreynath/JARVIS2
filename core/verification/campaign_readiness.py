"""Campaign readiness gates — refuse runs on insufficient datasets."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from core.verification.datasets.bmep import FAMILIES, load_all_bmep_families
from core.verification.datasets.rod_validation.loader import load_rod_cases
from core.verification.evidence_completeness import (
    score_bmep_case,
    score_material_case,
    score_rod_case,
)
from core.verification.evidence_collection import BMEP_FAMILY_TARGETS, ROD_M4_FIELDS
from core.verification.evidence_review import ReviewState, review_record
from core.verification.evidence_store import load_approved, load_pending
from core.verification.material_validation import load_material_cases
from core.verification.model_maturity import ModelMaturity
from core.verification.model_registry import MODEL_REGISTRY
from core.verification.raw_evidence import RawEvidenceRecord


CAMPAIGN_ALIASES = {
    "rod_stress": "rod_stress",
    "rod": "rod_stress",
    "bmep": "bmep",
    "bmep_displacement": "bmep",
    "material": "material",
    "material_requirements": "material",
}


class CampaignNotReadyError(RuntimeError):
    """Raised when a campaign is invoked without sufficient evidence."""

    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        super().__init__(payload.get("reason", "Campaign not ready"))


def _rod_case_dict(case: Any) -> dict[str, Any]:
    rcd = getattr(case, "reported_component_data", None) or {}
    return {
        "engine_name": case.engine_name,
        "rpm": case.rpm,
        "stroke_mm": case.stroke_mm,
        "bore_mm": getattr(case, "bore_mm", None),
        "rod_length_mm": case.rod_length_mm,
        "piston_mass_g": case.piston_mass_g,
        "rod_mass_g": case.rod_mass_g,
        "rod_material": rcd.get("connecting_rods_material") or rcd.get("rod_material"),
        "source_id": getattr(case, "source", None),
        "measurement_method": rcd.get("measurement_method"),
        "uncertainty": rcd.get("uncertainty"),
    }


def _count_complete_rod_cases() -> tuple[int, list[str]]:
    cases = load_rod_cases()
    scores = [score_rod_case(_rod_case_dict(c), case_id=c.engine_id or c.engine_name) for c in cases]
    eligible = [s for s in scores if s["eligible_for_campaign"]]
    missing_fields: set[str] = set()
    for s in scores:
        missing_fields.update(s.get("missing") or [])
    return len(eligible), sorted(missing_fields)


def _bmep_family_counts() -> dict[str, int]:
    families = load_all_bmep_families()
    counts: dict[str, int] = {}
    for family in FAMILIES:
        rows = families.get(family, [])
        complete = 0
        for r in rows:
            row = {
                "engine_name": r.engine,
                "family": family,
                "rpm": r.rpm,
                "horsepower": r.hp,
                "torque_nm": r.torque_nm,
                "displacement_l": r.displacement_l,
                "source_id": r.source,
                "measurement_method": None,
                "uncertainty": None,
            }
            if score_bmep_case(row, case_id=r.engine_id or r.engine)["eligible_for_campaign"]:
                complete += 1
        counts[family] = complete
    return counts


def _material_complete_count() -> int:
    cases = load_material_cases()
    n = 0
    for c in cases:
        row = {
            "component": c.component,
            "engine_name": c.engine,
            "material": c.material,
            "yield_strength_mpa": c.yield_strength_mpa,
            "fatigue_strength_mpa": c.fatigue_strength_mpa,
            "temperature_limit_c": c.temperature_limit_c,
            "source_id": c.source,
            "measurement_method": None,
            "uncertainty": None,
        }
        if score_material_case(row, case_id=c.engine)["eligible_for_campaign"]:
            n += 1
    return n


def _has_synthetic_records(records: list[RawEvidenceRecord]) -> bool:
    return any(r.measurement_type in {"synthetic", "estimate"} for r in records)


def check_campaign_ready(campaign: str) -> dict[str, Any]:
    """Return readiness report; does not mutate maturity."""
    key = CAMPAIGN_ALIASES.get(campaign, campaign)
    if key == "rod_stress":
        target = ROD_M4_FIELDS[0][1]
        complete, missing = _count_complete_rod_cases()
        completion = complete / target if target else 0.0
        ready = complete >= target
        reason = (
            "Rod stress campaign ready"
            if ready
            else f"Missing complete rod cases ({complete}/{target}); fields: {', '.join(missing[:5])}"
        )
        if "rod_mass_g" in missing or complete < target:
            if not ready and "rod_mass_g" in str(missing):
                reason = f"Missing piston_mass_g / rod_mass_g / rod_length_mm in {target - complete} required cases"
        return {
            "campaign": "rod_stress",
            "ready": ready,
            "reason": reason,
            "completion": round(completion, 3),
            "complete_cases": complete,
            "target_cases": target,
            "missing_fields": missing,
        }
    if key == "bmep":
        counts = _bmep_family_counts()
        gaps = []
        total_cur, total_tgt = 0, 0
        for family, tgt in BMEP_FAMILY_TARGETS.items():
            cur = counts.get(family, 0)
            total_cur += cur
            total_tgt += tgt
            if cur < tgt:
                gaps.append(f"{family} {cur}/{tgt}")
        completion = total_cur / total_tgt if total_tgt else 0.0
        ready = not gaps
        return {
            "campaign": "bmep",
            "ready": ready,
            "reason": "BMEP campaign ready" if ready else f"Insufficient family cases: {', '.join(gaps)}",
            "completion": round(completion, 3),
            "family_counts": counts,
            "family_targets": dict(BMEP_FAMILY_TARGETS),
        }
    if key == "material":
        target = 20
        complete = _material_complete_count()
        completion = complete / target if target else 0.0
        ready = complete >= target
        return {
            "campaign": "material",
            "ready": ready,
            "reason": (
                "Material campaign ready"
                if ready
                else f"Need {target} validated components ({complete}/{target})"
            ),
            "completion": round(completion, 3),
            "complete_cases": complete,
            "target_cases": target,
        }
    raise ValueError(f"Unknown campaign: {campaign}")


def assert_campaign_ready(campaign: str) -> dict[str, Any]:
    """Raise CampaignNotReadyError if dataset is insufficient."""
    report = check_campaign_ready(campaign)
    pending = load_pending()
    approved = load_approved()
    if _has_synthetic_records(pending + approved):
        report = {
            **report,
            "ready": False,
            "reason": "Synthetic or estimate evidence present — cannot run campaign",
        }
    if not report["ready"]:
        raise CampaignNotReadyError(report)
    return report


def validate_csv_submission(path: Path, template: str) -> dict[str, Any]:
    """Validate researcher CSV against template rules (no estimates, source_id required)."""
    from core.verification.dataset_templates import (
        BMEP_REQUIRED_COLUMNS,
        MATERIAL_REQUIRED_COLUMNS,
        ROD_REQUIRED_COLUMNS,
    )

    headers_map = {
        "rod": ROD_REQUIRED_COLUMNS,
        "bmep": BMEP_REQUIRED_COLUMNS,
        "material": MATERIAL_REQUIRED_COLUMNS,
    }
    required = headers_map.get(template)
    if required is None:
        raise ValueError(f"Unknown template: {template}")

    text = path.read_text(encoding="utf-8")
    lines = [ln for ln in text.strip().splitlines() if ln.strip()]
    if not lines:
        return {"valid": False, "reason": "Empty file"}
    reader = csv.DictReader(lines)
    fieldnames = reader.fieldnames or []
    missing_cols = [c for c in required if c not in fieldnames]
    if missing_cols:
        return {"valid": False, "reason": f"Missing columns: {missing_cols}"}

    invalid_rows: list[dict[str, Any]] = []
    for i, row in enumerate(reader, start=2):
        if not (row.get("source_id") or "").strip():
            invalid_rows.append({"row": i, "reason": "source_id required"})
        if template == "bmep":
            hp, rpm = row.get("horsepower"), row.get("rpm")
            tq, disp = row.get("torque_nm"), row.get("displacement_l")
            if hp and str(hp).strip() and not (rpm and str(rpm).strip()):
                invalid_rows.append({"row": i, "reason": "horsepower without rpm"})
            if tq and str(tq).strip() and not (disp and str(disp).strip()):
                invalid_rows.append({"row": i, "reason": "torque without displacement"})
        notes = (row.get("notes") or "").lower()
        if "estimate" in notes or "synthetic" in notes:
            invalid_rows.append({"row": i, "reason": "estimates forbidden in notes"})

    return {
        "valid": not invalid_rows,
        "rows_checked": max(0, len(lines) - 1),
        "invalid_rows": invalid_rows,
        "reason": "OK" if not invalid_rows else f"{len(invalid_rows)} invalid row(s)",
    }


def m4_histogram_locked() -> dict[str, int]:
    return {m.name: sum(1 for d in MODEL_REGISTRY.values() if d.maturity is m) for m in ModelMaturity}


def campaign_not_ready() -> bool:
    return not check_campaign_ready("rod_stress")["ready"]


def generated_dataset_invalid(records: list[RawEvidenceRecord]) -> bool:
    return _has_synthetic_records(records) or any(
        review_record(r).state is not ReviewState.APPROVED for r in records
        if r.measurement_type == "synthetic"
    )
