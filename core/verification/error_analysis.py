"""Error characterization — identify bias and error distributions (do not auto-fix)."""

from __future__ import annotations

from collections import defaultdict
from typing import Any


def _signed_relative(predicted: float, measured: float) -> float:
    if measured == 0:
        return 0.0
    return (predicted - measured) / abs(measured)


def characterize_errors(calibration_results: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate absolute/relative error and bias per quantity and overall."""
    by_quantity: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in calibration_results:
        if row.get("pass_status") in {"skipped", "unknown"}:
            continue
        if row.get("predicted") is None or row.get("measured") is None:
            continue
        by_quantity[row["quantity"]].append(row)

    models: dict[str, Any] = {}
    for quantity, rows in sorted(by_quantity.items()):
        abs_errs = [float(r["absolute_error"]) for r in rows if r.get("absolute_error") is not None]
        rel_errs = [float(r["relative_error"]) for r in rows if r.get("relative_error") is not None]
        signed = [
            _signed_relative(float(r["predicted"]), float(r["measured"]))
            for r in rows
        ]
        mean_rel = sum(rel_errs) / len(rel_errs) if rel_errs else None
        mean_signed = sum(signed) / len(signed) if signed else None
        median_rel = sorted(rel_errs)[len(rel_errs) // 2] if rel_errs else None
        if mean_signed is None:
            bias = "unknown"
        elif abs(mean_signed) < 0.02:
            bias = "neutral"
        elif mean_signed > 0:
            bias = "+"
        else:
            bias = "-"
        fail_count = sum(1 for r in rows if r.get("pass_status") == "fail")
        models[quantity] = {
            "model": quantity,
            "samples": len(rows),
            "mean_absolute_error": (sum(abs_errs) / len(abs_errs)) if abs_errs else None,
            "mean_error": mean_rel,
            "median_error": median_rel,
            "mean_signed_relative_error": mean_signed,
            "bias": bias,
            "fail_count": fail_count,
            "pass_rate": (len(rows) - fail_count) / len(rows) if rows else None,
            "upgrade_required": bool(
                mean_rel is not None and mean_rel > 0.10
            ) or fail_count > len(rows) / 2,
            "interpretation": _interpret(quantity, bias, mean_signed, mean_rel),
        }

    return {
        "quantities": models,
        "quantity_count": len(models),
        "policy": "Identify bias only — never auto-correct model parameters.",
    }


def _interpret(
    quantity: str,
    bias: str,
    mean_signed: float | None,
    mean_rel: float | None,
) -> str:
    if mean_signed is None or mean_rel is None:
        return "Insufficient paired predictions for interpretation."
    pct = abs(mean_signed) * 100.0
    if bias == "neutral":
        return f"{quantity}: no material systematic bias (mean |signed| < 2%)."
    direction = "overprediction" if bias == "+" else "underprediction"
    hint = ""
    if quantity == "displacement_l" and bias == "+":
        hint = " Likely cause candidate: BMEP assumption band too conservative (larger displacement)."
    elif quantity == "stroke_mm" and bias == "+":
        hint = " Likely cause candidate: bore/stroke ratio band or BMEP→displacement chain."
    elif quantity == "torque_nm":
        hint = " Torque identity should be near-zero error; large bias indicates input/unit mismatch."
    return f"{quantity}: systematic {direction} (~{pct:.1f}% signed mean).{hint}"


def build_model_error_report(
    *,
    independent_calibration: dict[str, Any],
    jarvis_calibration: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ind_rows = independent_calibration.get("results") or []
    jarvis_rows = (jarvis_calibration or {}).get("results") or []
    return {
        "independent_verification_model": characterize_errors(ind_rows),
        "jarvis_open_loop": characterize_errors(jarvis_rows) if jarvis_rows else None,
        "note": (
            "Independent model validates analytical identities against published geometry. "
            "JARVIS open-loop errors quantify sizing-model approximation — not a silent pass."
        ),
    }


def build_validation_matrix(
    calibration_results: list[dict[str, Any]],
) -> dict[str, Any]:
    """case × quantity pass/fail matrix."""
    matrix: dict[str, dict[str, str]] = defaultdict(dict)
    for row in calibration_results:
        matrix[row["case_id"]][row["quantity"]] = row.get("pass_status", "unknown")
    return {
        "matrix": {cid: dict(qs) for cid, qs in sorted(matrix.items())},
        "case_count": len(matrix),
    }
