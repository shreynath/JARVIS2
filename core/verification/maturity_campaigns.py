"""Targeted maturity benchmark campaigns — evidence acquisition, not tuning."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.engineering.engine_cycle_model import EngineCycleModel
from core.verification.bmep_validation import bmep_bar_from_torque_displacement
from verification.benchmark import load_engines
from verification.formulas import mean_piston_speed_m_s, peak_piston_acceleration_m_s2


# Campaign A focus engines (high RPM NA performance).
CAMPAIGN_A_ENGINE_IDS = (
    "honda_f20c",
    "lexus_lfa_1lr_gue",
    "ferrari_f136",
    "ferrari_458_f136",
    "ferrari_812_f140",
    "ferrari_f140",
    "porsche_991_gt3_ma1",
    "porsche_911_gt3_992_approx",
)

CAMPAIGN_B_NEEDED_FIELDS = (
    "rod_dimensions",
    "rod_material",
    "piston_mass_kg",
    "max_rpm",
)

CAMPAIGN_C_NEEDED_SOURCES = (
    "dyno_heat_rejection",
    "combustion_temperature_papers",
    "thermal_measurements",
)


def _engine_by_id() -> dict[str, dict[str, Any]]:
    return {e["id"]: e for e in load_engines()}


def run_campaign_a_high_rpm() -> dict[str, Any]:
    """Campaign A — kinematic / torque identities on high-RPM engines.

    Goal: evidence toward M2→M3 for torque, MPS, acceleration (not auto-upgrade).
    """
    engines = _engine_by_id()
    cases: list[dict[str, Any]] = []
    mps_errors: list[float] = []
    for eid in CAMPAIGN_A_ENGINE_IDS:
        eng = engines.get(eid)
        if eng is None:
            cases.append({"id": eid, "status": "missing_from_dataset"})
            continue
        pub = eng.get("published") or {}
        stroke_mm = pub.get("stroke_mm")
        rpm = pub.get("max_rpm")
        row: dict[str, Any] = {
            "id": eid,
            "name": eng.get("name"),
            "max_rpm": rpm,
            "stroke_mm": stroke_mm,
            "horsepower": pub.get("horsepower"),
        }
        if stroke_mm is None or rpm is None:
            row["status"] = "incomplete_geometry"
            cases.append(row)
            continue
        stroke_m = float(stroke_mm) / 1000.0
        mps = mean_piston_speed_m_s(stroke_m, float(rpm))
        accel = peak_piston_acceleration_m_s2(stroke_m, float(rpm))
        derived = (eng.get("derived_checks") or {}).get("mean_piston_speed_at_redline_m_s")
        err = None
        if derived is not None:
            err = (mps - float(derived)) / float(derived) if float(derived) else None
            if err is not None:
                mps_errors.append(abs(err))
        row.update(
            {
                "status": "ok",
                "independent_mps_m_s": round(mps, 4),
                "dataset_mps_m_s": derived,
                "mps_relative_error": err,
                "independent_peak_accel_m_s2": round(accel, 1),
            }
        )
        cases.append(row)

    usable = [c for c in cases if c.get("status") == "ok"]
    mean_abs_err = sum(mps_errors) / len(mps_errors) if mps_errors else None
    return {
        "id": "A_high_rpm",
        "name": "High RPM engines",
        "goal_models": [
            "calc_torque",
            "calc_mean_piston_speed",
            "calc_piston_acceleration",
            "engine_cycle_model",
            "geometry_model",
        ],
        "target_step": "M2→M3 (kinematic identities) / supporting BMEP M2→M3",
        "cases": cases,
        "usable_cases": len(usable),
        "mps_mean_abs_relative_error": mean_abs_err,
        "error_characterized": mean_abs_err is not None,
        "blocking_for_m4": [
            "Campaign A alone does not satisfy M3→M4 (≥10 predictive benches + uncertainty).",
            "Torque SI at redline must not be compared to published peak torque without caveat.",
        ],
        "policy": "Reports evidence readiness — does not mutate maturity.",
    }


def run_campaign_b_reciprocating() -> dict[str, Any]:
    """Campaign B — reciprocating mass / rod load evidence gaps."""
    engines = load_engines()
    inventory: list[dict[str, Any]] = []
    with_mass = 0
    with_rod_material = 0
    for eng in engines:
        pub = eng.get("published") or {}
        materials = eng.get("materials") or {}
        mass = pub.get("piston_mass_kg") or pub.get("mass_kg")
        rod = materials.get("connecting_rods")
        row = {
            "id": eng["id"],
            "max_rpm": pub.get("max_rpm"),
            "piston_mass_kg": mass,
            "connecting_rods_material": rod,
            "rod_dimensions_public": False,  # not in current dataset schema
        }
        if mass is not None:
            with_mass += 1
        if rod and str(rod).lower() not in {"unknown", "unknown_public", "null"}:
            with_rod_material += 1
        inventory.append(row)

    return {
        "id": "B_reciprocating",
        "name": "Reciprocating dynamics",
        "goal_models": [
            "reciprocating_mass_model",
            "piston_mass_estimate",
            "calc_rod_loading",
            "calc_rod_stress_requirement",
            "connecting_rod_model",
        ],
        "target_step": "mass M2→M3; rod models M3→M4 only with absolute benches",
        "needed_fields": list(CAMPAIGN_B_NEEDED_FIELDS),
        "inventory_summary": {
            "engines_scanned": len(engines),
            "with_piston_mass": with_mass,
            "with_named_rod_material": with_rod_material,
            "with_rod_dimensions": 0,
        },
        "sample": inventory[:8],
        "blocking_evidence": [
            "published_piston_mass_dataset",
            "absolute_load_benchmark",
            "fatigue_correlation_dataset",
            "rod_section_dimensions",
        ],
        "m4_ready": False,
        "policy": "Missing OEM mass/load data keeps rod models at M3.",
    }


def run_campaign_c_thermal() -> dict[str, Any]:
    """Campaign C — thermal / combustion temperature evidence gaps."""
    return {
        "id": "C_thermal",
        "name": "Thermal",
        "goal_models": [
            "calc_heat_rejection",
            "thermal_model",
            "calc_combustion_side_temperature",
        ],
        "target_step": "heat already M3 formula-ok; combustion map needs measurements before any M4 claim",
        "needed_sources": list(CAMPAIGN_C_NEEDED_SOURCES),
        "current_status": {
            "heat_rejection": "calculated energy-split; η_th/coolant fraction assumed",
            "combustion_temperature": "empirical internal map — UNVALIDATED",
        },
        "blocking_evidence": [
            "dyno_heat_rejection_data",
            "thermal_measurement_papers",
            "combustion_temperature_correlation",
            "independent_verifier_exists",
        ],
        "m4_ready": False,
        "policy": "Do not remove the empirical map — refuse maturity inflation without measurements.",
    }


def run_all_campaigns() -> dict[str, Any]:
    a = run_campaign_a_high_rpm()
    b = run_campaign_b_reciprocating()
    c = run_campaign_c_thermal()

    # Optional supporting BMEP spot-check on Campaign A engines (never tunes bands).
    engines = _engine_by_id()
    bmep_rows = []
    model = EngineCycleModel()
    for eid in CAMPAIGN_A_ENGINE_IDS:
        eng = engines.get(eid)
        if not eng:
            continue
        pub = eng.get("published") or {}
        if pub.get("torque_nm") is None or pub.get("displacement_l") is None:
            continue
        measured = bmep_bar_from_torque_displacement(
            float(pub["torque_nm"]), float(pub["displacement_l"])
        )
        band = model.estimate(aspiration=str(eng.get("aspiration") or "Naturally aspirated"))
        bmep_rows.append(
            {
                "id": eid,
                "measured_bmep_bar": round(measured, 3),
                "jarvis_band_bar": None if band.bmep is None else band.bmep.value,
            }
        )

    return {
        "phase": "8.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "campaigns": {"A_high_rpm": a, "B_reciprocating": b, "C_thermal": c},
        "campaign_a_bmep_spotcheck": bmep_rows,
        "policy": (
            "Campaigns acquire / inventory evidence. They never retune equations "
            "and never write maturity into the registry."
        ),
        "automatic_upgrades_applied": 0,
    }


def write_campaign_report(output_dir: Path | str) -> Path:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "maturity_campaigns.json"
    path.write_text(json.dumps(run_all_campaigns(), indent=2, default=str))
    return path
