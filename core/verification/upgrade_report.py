"""Phase 5.0 model-upgrade accountability report."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.verification.model_registry import MODEL_REGISTRY


# Baseline maturity snapshot at start of Phase 5.0 (from Phase 4.5 registry).
PHASE_4_5_BASELINE: dict[str, str] = {
    "calc_rod_loading": "M3",
    "calc_rod_stress_requirement": "M3",
    "calc_stroke": "M2",
    "piston_mass_estimate": "M1",
    "material_req_structural": "M1",
    "material_req_piston": "M1",
    "material_selection_ranking": "M1",
    "geometry_model": "absent",
    "reciprocating_mass_model": "absent",
    "connecting_rod_model": "absent",
}


def build_model_upgrade_report() -> dict[str, Any]:
    before: dict[str, str] = {}
    after: dict[str, str] = {}
    evidence: list[dict[str, Any]] = []
    withheld: list[dict[str, Any]] = []

    for model_id, baseline in PHASE_4_5_BASELINE.items():
        before[model_id] = baseline
        desc = MODEL_REGISTRY.get(model_id)
        current = desc.maturity.name if desc else "absent"
        after[model_id] = current
        if baseline != current and current != "absent":
            evidence.append(
                {
                    "model": model_id,
                    "from": baseline,
                    "to": current,
                    "independently_verified": bool(desc and desc.independently_verified),
                    "benchmarked": bool(desc and desc.benchmarked),
                    "limitations": desc.known_limitations if desc else None,
                }
            )
        if desc and desc.maturity.name == "M3" and model_id.startswith("calc_rod"):
            withheld.append(
                {
                    "model": model_id,
                    "target": "M4",
                    "reason": (
                        "Insufficient published absolute rod-load / rod-stress benchmarks "
                        "to claim validated predictive status (M4)."
                    ),
                    "evidence_present": {
                        "independently_verified": desc.independently_verified,
                        "benchmarked": desc.benchmarked,
                    },
                }
            )

    return {
        "phase": "5.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "before": before,
        "after": after,
        "evidence": evidence,
        "maturity_withheld": withheld,
        "policy": (
            "Maturity rises only with implementation + independent verification + "
            "benchmark agreement. Insufficient evidence keeps maturity unchanged."
        ),
    }


def write_model_upgrade_report(output_dir: Path | str) -> Path:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "model_upgrade_report.json"
    path.write_text(json.dumps(build_model_upgrade_report(), indent=2, default=str))
    return path
