"""Evidence collection plan + M4 readiness dashboard."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.verification.datasets.bmep import FAMILIES, load_all_bmep_families
from core.verification.datasets.rod_validation.loader import load_rod_cases
from core.verification.evidence_store import load_approved, load_pending
from core.verification.material_validation import load_material_cases
from core.verification.model_maturity import ModelMaturity
from core.verification.model_registry import MODEL_REGISTRY


# M4 campaign field targets
ROD_M4_FIELDS = (
    ("rod_length_mm", 10),
    ("piston_mass_g", 10),
    ("rod_mass_g", 10),
)
BMEP_FAMILY_TARGETS = {
    "naturally_aspirated": 20,
    "turbocharged": 20,
    "diesel": 10,
    "aircraft": 10,
    "motorcycle": 10,
}


def _count_rod_field(cases: list, field: str) -> int:
    return sum(1 for c in cases if getattr(c, field, None) is not None)


def _count_raw_field(records: list, field: str) -> int:
    return sum(1 for r in records if r.field == field and r.value is not None)


def build_evidence_collection_plan() -> dict[str, Any]:
    rod_cases = load_rod_cases()
    pending = load_pending()
    approved = load_approved()
    bmep = load_all_bmep_families()

    rod_stress_needed = []
    for field, target in ROD_M4_FIELDS:
        current = _count_rod_field(rod_cases, field)
        current += _count_raw_field(pending, field)
        current += _count_raw_field(approved, field)
        rod_stress_needed.append({"field": field, "current": current, "target": target})

    bmep_needed = {}
    for family, target in BMEP_FAMILY_TARGETS.items():
        rows = bmep.get(family, [])  # type: ignore[arg-type]
        complete = sum(
            1
            for r in rows
            if r.torque_nm is not None and r.displacement_l is not None
        )
        bmep_needed[family] = {"current": complete, "target": target}

    return {
        "phase": "9.5",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "policy": "Tracks missing external evidence — never inflates maturity.",
        "rod_stress": {"needed": rod_stress_needed},
        "bmep_displacement": {"needed": bmep_needed},
        "material_requirements": {
            "needed": [
                {
                    "field": "component_material_population",
                    "current": len(load_material_cases()),
                    "target": 20,
                }
            ]
        },
        "pending_review_count": len(pending),
        "approved_raw_count": len(approved),
    }


def build_m4_readiness_dashboard() -> dict[str, Any]:
    plan = build_evidence_collection_plan()
    rod = plan["rod_stress"]["needed"]
    rod_cases = sum(r["current"] for r in rod if r["field"] == "piston_mass_g")
    rod_target = next(r["target"] for r in rod if r["field"] == "piston_mass_g")
    rod_pct = round(100.0 * min(rod_cases, rod_target) / rod_target, 1) if rod_target else 0.0

    bmep_blocks = []
    for family, block in plan["bmep_displacement"]["needed"].items():
        cur, tgt = block["current"], block["target"]
        pct = round(100.0 * min(cur, tgt) / tgt, 1) if tgt else 0.0
        bmep_blocks.append(
            {
                "family": family,
                "cases": f"{cur}/{tgt}",
                "progress_percent": pct,
            }
        )

    missing_rod = [r["field"] for r in rod if r["current"] < r["target"]]

    return {
        "phase": "9.5",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "title": "M4 READINESS",
        "histogram": {
            m.name: sum(1 for d in MODEL_REGISTRY.values() if d.maturity is m)
            for m in ModelMaturity
        },
        "models": {
            "rod_stress": {
                "cases": f"{rod_cases}/{rod_target}",
                "missing": missing_rod,
                "progress_percent": rod_pct,
                "m4_eligible": False,
                "note": "Need ≥10 engines with piston_mass, rod_mass, rod_length",
            },
            "bmep": {
                "families": bmep_blocks,
                "m4_eligible": False,
                "note": "Need family BMEP distributions — not mid-band assumptions",
            },
            "material_requirements": plan["material_requirements"],
        },
        "policy": "Readiness is evidence inventory only — no automatic M4 promotion.",
    }


def write_evidence_collection_plan(output_dir: Path | str) -> Path:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "evidence_collection_plan.json"
    path.write_text(json.dumps(build_evidence_collection_plan(), indent=2, default=str))
    return path


def write_m4_readiness_dashboard(output_dir: Path | str) -> Path:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "m4_readiness_dashboard.json"
    path.write_text(json.dumps(build_m4_readiness_dashboard(), indent=2, default=str))
    return path
