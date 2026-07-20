"""Design prediction confidence — physics / engineering / validation layers per output."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.verification.model_maturity import MATURITY_RANK, ModelMaturity
from core.verification.model_registry import MODEL_REGISTRY


def _confidence_from_maturity(maturity: ModelMaturity, *, benchmarked: bool) -> str:
    rank = MATURITY_RANK[maturity]
    if rank >= 4:
        return "high"
    if rank >= 3 and benchmarked:
        return "high"
    if rank >= 3:
        return "medium"
    if rank >= 2:
        return "medium"
    if rank >= 1:
        return "low"
    return "very_low"


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text())


def build_design_prediction_confidence(
    *,
    output_dir: Path | str | None = None,
    physics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Aggregate maturity + campaign artifacts into per-output confidence."""
    out = Path(output_dir) if output_dir else Path("output")
    bmep = _load_json(out / "bmep_maturity_packet.json") or {}
    rod = _load_json(out / "rod_maturity_packet.json") or {}
    material = _load_json(out / "material_maturity_packet.json") or {}

    def model_confidence(model_id: str, reason_suffix: str = "") -> dict[str, Any]:
        desc = MODEL_REGISTRY.get(model_id)
        if desc is None:
            return {
                "physics_confidence": "unknown",
                "engineering_confidence": "unknown",
                "validation_confidence": "unknown",
                "overall_confidence": "unknown",
                "reason": f"model {model_id} not in registry",
            }
        phys = _confidence_from_maturity(desc.maturity, benchmarked=desc.benchmarked)
        eng = phys
        val = "low" if not desc.benchmarked else "medium"
        if desc.independently_verified and desc.benchmarked:
            val = "high"
        elif desc.independently_verified:
            val = "medium"
        overall = phys
        if val == "low" and overall == "high":
            overall = "medium"
        reason = f"{model_id} maturity {desc.maturity.name}"
        if reason_suffix:
            reason = f"{reason}; {reason_suffix}"
        return {
            "physics_confidence": phys,
            "engineering_confidence": eng,
            "validation_confidence": val,
            "overall_confidence": overall,
            "maturity": desc.maturity.name,
            "reason": reason,
        }

    bmep_answer = (_load_json(out / "bmep_campaign_report.json") or {}).get(
        "baseline_design_answer"
    ) or {}

    outputs: dict[str, Any] = {
        "torque": {
            "value": "633 Nm (baseline 800 HP @ 9000 RPM)",
            **model_confidence(
                "calc_torque",
                "Campaign A kinematic identity M3",
            ),
        },
        "mean_piston_speed": {
            "value": "26.68 m/s high bound (baseline fails hard gate)",
            **model_confidence(
                "calc_mean_piston_speed",
                "Campaign A external kinematic checks",
            ),
        },
        "piston_acceleration": {
            **model_confidence(
                "calc_piston_acceleration",
                "First-harmonic approximation M3",
            ),
        },
        "displacement": {
            "value": bmep_answer.get("required_displacement_l"),
            "uncertainty_l": bmep_answer.get("uncertainty_l"),
            **model_confidence(
                "calc_displacement",
                bmep_answer.get("limitation") or "BMEP band assumption",
            ),
            "engineering_confidence": "medium",
            "validation_confidence": "low",
            "overall_confidence": "medium",
            "reason": (
                f"engine_cycle_model M2; {bmep_answer.get('reason', 'BMEP assumption')}"
            ),
        },
        "rod_loading": {
            **model_confidence(
                "calc_rod_loading",
                rod.get("blocked_reason") or "no absolute mass benches",
            ),
            "validation_confidence": "low",
            "overall_confidence": "medium",
        },
        "rod_stress": {
            **model_confidence(
                "calc_rod_stress_requirement",
                "M4 blocked pending OEM mass/load data",
            ),
        },
        "rod_material": {
            **model_confidence(
                "material_req_structural",
                "Load-backed requirement; sparse external component population",
            ),
            "example_decision": (
                (_load_json(out / "material_validation_report.json") or {})
                .get("example_auditable_decision", {})
                .get("selected")
            ),
        },
        "piston_material": {
            **model_confidence(
                "material_req_piston",
                material.get("blocked_reason") or "M4 not eligible",
            ),
        },
        "combustion_temperature": {
            **model_confidence(
                "calc_combustion_side_temperature",
                "Empirical map UNVALIDATED",
            ),
            "validation_confidence": "low",
            "overall_confidence": "low",
        },
        "heat_rejection": {
            **model_confidence(
                "calc_heat_rejection",
                "Energy-split calculated; efficiency parameters assumed",
            ),
        },
    }

    if physics:
        torque_calc = next(
            (c for c in physics.get("calculations") or [] if c.get("id") == "calc_torque"),
            None,
        )
        if torque_calc and torque_calc.get("result") is not None:
            outputs["torque"]["value"] = f"{torque_calc['result']} Nm"

    m4_blocked = {
        "rod_models": not bool(rod.get("eligible_for_upgrade")),
        "bmep_displacement": not bool(bmep.get("eligible_for_upgrade")),
        "material_requirements": not bool(material.get("eligible_for_upgrade")),
    }

    return {
        "phase": "8.9",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "outputs": outputs,
        "m4_blocked": m4_blocked,
        "histogram_policy": "M4=0 until absolute benchmarks pass gates; M5 not pursued",
        "policy": (
            "Confidence reflects earned maturity and campaign evidence — "
            "not equation sophistication alone."
        ),
    }


def write_design_prediction_confidence(
    output_dir: Path | str,
    *,
    physics: dict[str, Any] | None = None,
) -> Path:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    report = build_design_prediction_confidence(output_dir=out, physics=physics)
    path = out / "design_prediction_confidence.json"
    path.write_text(json.dumps(report, indent=2, default=str))
    return path
