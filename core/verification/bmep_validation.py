"""BMEP validation against published engines — reports errors; never tunes bands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.engineering.engine_cycle_model import BOOSTED_BMEP_BAR, NA_BMEP_BAR, EngineCycleModel
from verification.benchmark import load_engines


def bmep_bar_from_torque_displacement(torque_nm: float, displacement_l: float) -> float:
    """Four-stroke BMEP [bar] from brake torque and displacement.

    BMEP = 4π τ / V_d  with τ in N·m and V_d in m³ → Pa, then /1e5 → bar.
    """
    if displacement_l <= 0:
        raise ZeroDivisionError("displacement must be positive")
    v_m3 = displacement_l / 1000.0
    bmep_pa = 4.0 * 3.141592653589793 * torque_nm / v_m3
    return bmep_pa / 1e5


def _classify_family(engine: dict[str, Any]) -> str:
    aspir = str(engine.get("aspiration") or "").lower()
    name = str(engine.get("name") or "").lower()
    arch = str(engine.get("architecture") or "").lower()
    if "diesel" in aspir or "diesel" in name:
        return "diesel"
    if "aircraft" in name or "lycoming" in name or "radial" in arch:
        return "aircraft"
    if "turbo" in aspir or "super" in aspir:
        return "turbo"
    return "na"


def build_bmep_validation() -> dict[str, Any]:
    """Compare real-engine BMEP vs JARVIS empirical bands — no model mutation."""
    families: dict[str, list[dict[str, Any]]] = {
        "na": [],
        "turbo": [],
        "diesel": [],
        "aircraft": [],
    }
    model = EngineCycleModel()

    for engine in load_engines():
        pub = engine.get("published") or {}
        torque = pub.get("torque_nm")
        disp = pub.get("displacement_l")
        if torque is None or disp is None:
            continue
        family = _classify_family(engine)
        measured_bar = bmep_bar_from_torque_displacement(float(torque), float(disp))
        aspir = engine.get("aspiration") or "Naturally aspirated"
        estimate = model.estimate(aspiration=str(aspir))
        band = estimate.bmep.value if estimate.bmep else None
        mid = None
        err = None
        inside = None
        if isinstance(band, tuple):
            mid = (band[0] + band[1]) / 2.0
            err = (mid - measured_bar) / measured_bar if measured_bar else None
            inside = band[0] <= measured_bar <= band[1]
        families[family].append(
            {
                "id": engine["id"],
                "measured_bmep_bar": round(measured_bar, 3),
                "jarvis_band_bar": band,
                "jarvis_mid_bar": mid,
                "relative_error_vs_mid": err,
                "inside_band": inside,
                "aspiration": aspir,
            }
        )

    summaries: dict[str, Any] = {}
    for family, rows in families.items():
        errs = [r["relative_error_vs_mid"] for r in rows if r["relative_error_vs_mid"] is not None]
        mean_err = sum(errs) / len(errs) if errs else None
        var = (
            sum((e - mean_err) ** 2 for e in errs) / len(errs)  # type: ignore[operator]
            if errs and mean_err is not None
            else None
        )
        summaries[family] = {
            "samples": len(rows),
            "mean_error": mean_err,
            "variance": var,
            "application_range_bar": (
                NA_BMEP_BAR if family in {"na", "aircraft"} else BOOSTED_BMEP_BAR
                if family == "turbo"
                else None
            ),
            "engines": rows,
            "note": (
                "Families are never mixed. JARVIS NA/turbo bands are empirical catalog floors."
            ),
        }

    return {
        "phase": "7.0",
        "policy": "Validation reports error only — BMEP model is never auto-tuned.",
        "families": summaries,
        "na_band_bar": NA_BMEP_BAR,
        "turbo_band_bar": BOOSTED_BMEP_BAR,
    }


def write_bmep_validation(output_dir: Path | str) -> Path:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "bmep_validation.json"
    path.write_text(json.dumps(build_bmep_validation(), indent=2, default=str))
    return path
