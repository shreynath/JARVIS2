"""Evidence completeness scoring per case — campaign eligibility helper."""

from __future__ import annotations

from typing import Any

from core.verification.dataset_templates import (
    BMEP_M4_PAIR_RULES,
    MATERIAL_M4_FIELDS,
    ROD_M4_CASE_FIELDS,
)


def _present(row: dict[str, Any], field: str) -> bool:
    val = row.get(field)
    if val is None:
        return False
    if isinstance(val, str) and not val.strip():
        return False
    return True


def score_row_completeness(
    row: dict[str, Any],
    required_fields: tuple[str, ...],
    *,
    case_id: str,
    pair_rules: tuple[tuple[str, str], ...] = (),
) -> dict[str, Any]:
    missing = [f for f in required_fields if not _present(row, f)]
    for a, b in pair_rules:
        if _present(row, a) and not _present(row, b):
            missing.append(f"{a}_requires_{b}")
        if _present(row, b) and not _present(row, a):
            missing.append(f"{b}_requires_{a}")
    total = len(required_fields) + len(pair_rules) * 2
    present = total - len(missing)
    completeness = present / total if total else 0.0
    return {
        "case": case_id,
        "completeness": round(completeness, 3),
        "required_fields": len(required_fields),
        "present_count": len(required_fields) - len([m for m in missing if m in required_fields]),
        "missing": missing,
        "eligible_for_campaign": completeness >= 1.0 and not missing,
    }


def score_rod_case(row: dict[str, Any], *, case_id: str) -> dict[str, Any]:
    return score_row_completeness(row, ROD_M4_CASE_FIELDS, case_id=case_id)


def score_bmep_case(row: dict[str, Any], *, case_id: str) -> dict[str, Any]:
    base = score_row_completeness(
        row,
        (
            "engine_name",
            "family",
            "rpm",
            "horsepower",
            "torque_nm",
            "displacement_l",
            "source_id",
            "measurement_method",
            "uncertainty",
        ),
        case_id=case_id,
        pair_rules=BMEP_M4_PAIR_RULES,
    )
    return base


def score_material_case(row: dict[str, Any], *, case_id: str) -> dict[str, Any]:
    return score_row_completeness(row, MATERIAL_M4_FIELDS, case_id=case_id)


def aggregate_completeness(scores: list[dict[str, Any]]) -> dict[str, Any]:
    if not scores:
        return {"mean_completeness": 0.0, "eligible_cases": 0, "total_cases": 0}
    eligible = sum(1 for s in scores if s.get("eligible_for_campaign"))
    mean = sum(float(s.get("completeness") or 0) for s in scores) / len(scores)
    return {
        "mean_completeness": round(mean, 3),
        "eligible_cases": eligible,
        "total_cases": len(scores),
    }
