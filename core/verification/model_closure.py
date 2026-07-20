"""Model closure report — which assumptions still dominate predictions."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.verification.model_maturity import MATURITY_RANK, ModelMaturity
from core.verification.model_registry import MODEL_REGISTRY


DOMINANT_TARGETS = (
    "bmep_assumption_bands",
    "engine_cycle_model",
    "calc_displacement",
    "reciprocating_mass_model",
    "piston_mass_estimate",
    "material_req_structural",
    "material_req_piston",
    "calc_combustion_side_temperature",
    "calc_heat_rejection",
    "calc_rod_loading",
    "connecting_rod_model",
)


def build_model_closure_report(
    *,
    physics: dict[str, Any] | None = None,
    impact_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    attachments = (physics or {}).get("engineering_attachments") or {}
    dominant: list[dict[str, Any]] = []

    for model_id in DOMINANT_TARGETS:
        desc = MODEL_REGISTRY.get(model_id)
        if desc is None:
            continue
        impact_meta = ((impact_report or {}).get("models") or {}).get(model_id) or {}
        dominant.append(
            {
                "model": model_id,
                "maturity": desc.maturity.name,
                "impact": desc.impact_level.value,
                "impact_score": impact_meta.get("closure_impact_score"),
                "reason": desc.known_limitations,
                "benchmarked": desc.benchmarked,
                "assumes_open_loop": MATURITY_RANK[desc.maturity] <= 2
                or not desc.benchmarked,
            }
        )

    dominant.sort(
        key=lambda r: (
            0 if r["impact"] in {"critical", "high"} else 1,
            MATURITY_RANK[ModelMaturity[r["maturity"]]],
            r["model"],
        )
    )

    return {
        "phase": "7.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dominant_uncertainties": dominant[:12],
        "engineering_attachments_present": sorted(attachments.keys()),
        "engine_cycle_present": "engine_cycle" in attachments,
        "thermal_separated": "thermal" in attachments,
        "policy": (
            "Closure reduces naked assumptions to explicit models with provenance. "
            "Maturity rises only with independent verification + external evidence."
        ),
        "answers": {
            "why_this_displacement": (
                "Required power and RPM sized through EngineCycleModel empirical BMEP band "
                "with provenance; see engineering_attachments.engine_cycle and bmep_validation.json."
            ),
            "why_this_material": (
                "MaterialRequirement packets require calculation_dependencies and load_source; "
                "alternatives_considered record property-level rejection."
            ),
        },
    }


def write_model_closure_report(
    output_dir: Path | str,
    *,
    physics: dict[str, Any] | None = None,
    impact_report: dict[str, Any] | None = None,
) -> Path:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    if physics is None:
        p = out / "physics_analysis.json"
        if p.exists():
            physics = json.loads(p.read_text())
    if impact_report is None:
        ip = out / "model_impact_report.json"
        if ip.exists():
            impact_report = json.loads(ip.read_text())
    path = out / "model_closure_report.json"
    path.write_text(
        json.dumps(
            build_model_closure_report(physics=physics, impact_report=impact_report),
            indent=2,
            default=str,
        )
    )
    return path
