"""JARVIS open-loop predictor for calibration — may import pipeline.

Kept separate from core/verification/datasets and calibration compare primitives
so dataset packages remain production-model-free.
"""

from __future__ import annotations

from typing import Any

from core.verification.datasets.validation_case import ValidationCase


def jarvis_open_loop_predictor(case: ValidationCase) -> dict[str, float | None]:
    """Run SemanticKernelPipeline from published HP/RPM only (open-loop sizing)."""
    from core.reasoning.pipeline import SemanticKernelPipeline
    from llm.ollama_client import DeterministicProvider

    hp = case.inputs.get("horsepower")
    rpm = case.inputs.get("max_rpm")
    cyl = case.inputs.get("cylinder_count")
    if hp is None or rpm is None:
        return {
            "torque_nm": None,
            "displacement_l": None,
            "stroke_mm": None,
            "mean_piston_speed_m_s": None,
        }

    notes = (case.notes or "").lower()
    aspir = "naturally aspirated"
    if "turbo" in notes or "super" in notes or "boost" in notes:
        aspir = "turbocharged"

    arch = "V8"
    if "v12" in notes:
        arch = "V12"
    elif "v10" in notes:
        arch = "V10"
    elif "v6" in notes:
        arch = "V6"
    elif "inline" in notes or "i4" in notes or "i-4" in notes:
        arch = "Inline-4"
    elif cyl == 12:
        arch = "V12"
    elif cyl == 10:
        arch = "V10"
    elif cyl == 6:
        arch = "V6"
    elif cyl == 4:
        arch = "Inline-4"

    prompt = (
        f"Design a {int(rpm)} RPM {aspir} {arch} producing {hp} horsepower."
    )
    result = SemanticKernelPipeline(provider=DeterministicProvider()).run(prompt)
    out: dict[str, float | None] = {
        "torque_nm": None,
        "displacement_l": None,
        "stroke_mm": None,
        "mean_piston_speed_m_s": None,
    }
    if result.physics_analysis is None:
        return out

    def _val(calc_id: str) -> float | None:
        calc = result.physics_analysis.by_id(calc_id)
        if calc is None or calc.status == "skipped" or calc.result is None:
            return None
        return float(calc.result)

    out["torque_nm"] = _val("calc_torque")
    out["displacement_l"] = _val("calc_displacement")
    out["stroke_mm"] = _val("calc_stroke")
    out["mean_piston_speed_m_s"] = _val("calc_mean_piston_speed")
    return out
