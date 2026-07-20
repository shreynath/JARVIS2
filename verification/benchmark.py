"""Reference-engine benchmark — may use the pipeline; reports error vs published data."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from verification.formulas import mean_piston_speed_m_s, percent_error, torque_nm_from_hp_rpm

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "datasets" / "reference_engines"


def load_engines() -> list[dict[str, Any]]:
    engines = []
    for path in sorted(DATASET.glob("*.json")):
        engines.append(json.loads(path.read_text()))
    return engines


def kinematic_check(engine: dict[str, Any]) -> dict[str, Any]:
    pub = engine["published"]
    stroke_m = float(pub["stroke_mm"]) / 1000.0
    rpm = float(pub["max_rpm"])
    expected = mean_piston_speed_m_s(stroke_m, rpm)
    published_derived = (engine.get("derived_checks") or {}).get("mean_piston_speed_at_redline_m_s")
    err = None if published_derived is None else percent_error(float(published_derived), expected)
    return {
        "check": "independent_mps_from_published_stroke_rpm",
        "expected_m_s": expected,
        "dataset_derived_m_s": published_derived,
        "percent_error_vs_dataset_note": err,
        "status": "pass" if err is None or err < 0.5 else "fail",
    }


def jarvis_prediction(engine: dict[str, Any]) -> dict[str, Any]:
    """Run JARVIS from HP/RPM/architecture only — measures open-loop estimate error."""
    from core.reasoning.pipeline import SemanticKernelPipeline
    from llm.ollama_client import DeterministicProvider

    pub = engine["published"]
    arch = engine.get("architecture", "V8")
    # Map architecture tokens into a prompt JARVIS recognizes
    arch_token = "V12" if "V12" in arch else ("V8" if "V8" in arch else ("Inline-4" if "Inline" in arch or "inline" in arch.lower() else arch))
    if "Flat" in arch or "Boxer" in arch:
        # JARVIS architecture parser may not map flat/boxer → leave explicit cylinder count via prompt wording
        prompt = (
            f"Design a {int(pub['max_rpm'])} RPM {engine.get('aspiration', 'naturally aspirated')} "
            f"{int(pub['cylinder_count'])}-cylinder engine producing {pub['horsepower']} horsepower."
        )
    else:
        prompt = (
            f"Design a {int(pub['max_rpm'])} RPM {engine.get('aspiration', 'naturally aspirated').lower()} "
            f"{arch_token} producing {pub['horsepower']} horsepower."
        )
    result = SemanticKernelPipeline(provider=DeterministicProvider()).run(prompt)
    if result.physics_analysis is None:
        return {"status": "blocked", "prompt": prompt, "reason": "physics blocked"}
    pa = result.physics_analysis
    stroke = pa.by_id("calc_stroke")
    mps = pa.by_id("calc_mean_piston_speed")
    disp = pa.by_id("calc_displacement")
    torque = pa.by_id("calc_torque")
    published_stroke = float(pub["stroke_mm"])
    published_mps = mean_piston_speed_m_s(published_stroke / 1000.0, float(pub["max_rpm"]))
    published_disp = float(pub["displacement_l"])
    pred = {
        "prompt": prompt,
        "predicted_stroke_mm": stroke.result if stroke else None,
        "predicted_mps": mps.result if mps else None,
        "predicted_displacement_l": disp.result if disp else None,
        "predicted_torque_nm": torque.result if torque else None,
        "published_stroke_mm": published_stroke,
        "published_mps": published_mps,
        "published_displacement_l": published_disp,
        "published_torque_nm": torque_nm_from_hp_rpm(float(pub["horsepower"]), float(pub["max_rpm"])),
    }
    errors = {}
    if pred["predicted_stroke_mm"] is not None:
        errors["stroke_pct"] = percent_error(published_stroke, float(pred["predicted_stroke_mm"]))
    if pred["predicted_mps"] is not None:
        errors["mps_pct"] = percent_error(published_mps, float(pred["predicted_mps"]))
    if pred["predicted_displacement_l"] is not None:
        errors["displacement_pct"] = percent_error(published_disp, float(pred["predicted_displacement_l"]))
    if pred["predicted_torque_nm"] is not None:
        errors["torque_pct"] = percent_error(pred["published_torque_nm"], float(pred["predicted_torque_nm"]))
    pred["errors_percent"] = errors
    pred["status"] = "compared"
    return pred


def aggregate_errors(rows: list[dict[str, Any]]) -> dict[str, Any]:
    metrics = ["stroke_pct", "mps_pct", "displacement_pct", "torque_pct"]
    out: dict[str, Any] = {}
    for m in metrics:
        vals = [
            r["jarvis"].get("errors_percent", {}).get(m)
            for r in rows
            if r.get("jarvis", {}).get("status") == "compared"
            and r["jarvis"].get("errors_percent", {}).get(m) is not None
        ]
        if not vals:
            out[m] = None
            continue
        mae = sum(vals) / len(vals)
        rmse = math.sqrt(sum(v * v for v in vals) / len(vals))
        bias = sum(vals) / len(vals)  # percent errors already absolute in formula — use signed if available
        out[m] = {"MAE_pct": mae, "RMSE_pct": rmse, "n": len(vals), "note": "absolute percent error aggregates"}
    return out


def run_benchmark(*, include_jarvis: bool = True) -> dict[str, Any]:
    rows = []
    for engine in load_engines():
        row = {
            "id": engine["id"],
            "name": engine["name"],
            "architecture": engine.get("architecture"),
            "data_quality": engine.get("data_quality"),
            "kinematic": kinematic_check(engine),
        }
        if include_jarvis:
            row["jarvis"] = jarvis_prediction(engine)
        rows.append(row)
    return {
        "engines": rows,
        "aggregates": aggregate_errors(rows) if include_jarvis else {},
        "interpretation": (
            "Kinematic checks validate published stroke/RPM arithmetic independently. "
            "JARVIS open-loop estimates (HP+RPM→BMEP→geometry) are expected to err vs OEM geometry; "
            "large stroke/displacement errors quantify model approximation, not a silent pass."
        ),
    }
