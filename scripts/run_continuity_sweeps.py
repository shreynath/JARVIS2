#!/usr/bin/env python3
"""Regenerate output/continuity_sweeps.json with a clean single-source schema.

Authoritative locations (no null top-level duplicates):
  - Physics scalars: torque/displacement/stroke/mps/acceleration/rod_loading/rod_stress
  - Requirement metrics for the tracked part: req_yield (from selection_metrics.required_yield_mpa)
  - Role/provenance: mass_sensitive, material, source
  - Candidate ranking payload: top_candidates[] (owns limiting_margin, fatigue/thermal margins,
    hard_constraints_met — never mirrored as nullable parent fields)
"""

from __future__ import annotations

import json
from pathlib import Path

from core.reasoning.pipeline import SemanticKernelPipeline
from llm.ollama_client import DeterministicProvider

HOLD_HP = 500
HOLD_RPM = 7000
CATEGORICAL = ("mass_sensitive", "material", "source")
ROOT = Path(__file__).resolve().parents[1]


def _conf(c):
    if c is None:
        return None
    return c.value if hasattr(c, "value") else c


def chain(result, *, comparison_mode: str) -> dict:
    pa = result.physics_analysis
    assert pa is not None, "continuity sweep requires computed physics"
    rods = result.graph.components.get("connecting_rods")
    metrics = (rods.material_spec.selection_metrics if rods and rods.material_spec else {}) or {}
    rankings = (rods.material_spec.candidate_rankings if rods and rods.material_spec else []) or []

    def c(cid: str) -> dict:
        calc = pa.by_id(cid)
        assert calc is not None, cid
        return {
            "id": cid,
            "result": calc.result,
            "range": list(calc.value_range) if calc.value_range else None,
            "confidence": _conf(calc.confidence),
            "passes": calc.passes,
            "assessment": calc.assessment,
        }

    # Thin candidate rows: keep ranking fields; no parent-level null mirrors.
    top_candidates = [
        {
            "catalog_key": row.get("catalog_key"),
            "name": row.get("name"),
            "hard_constraints_met": row.get("hard_constraints_met"),
            "yield_margin": row.get("yield_margin"),
            "fatigue_margin": row.get("fatigue_margin"),
            "thermal_margin": row.get("thermal_margin"),
            "limiting_margin": row.get("limiting_margin"),
            "density_kg_m3": row.get("density_kg_m3"),
            "relative_cost": row.get("relative_cost"),
        }
        for row in rankings[:3]
    ]

    return {
        "comparison_mode": comparison_mode,
        "torque": c("calc_torque"),
        "displacement": c("calc_displacement"),
        "stroke": c("calc_stroke"),
        "mps": c("calc_mean_piston_speed"),
        "acceleration": c("calc_piston_acceleration"),
        "rod_loading": c("calc_rod_loading"),
        "rod_stress": c("calc_rod_stress_requirement"),
        "req_yield": metrics.get("required_yield_mpa"),
        "mass_sensitive": metrics.get("mass_sensitive"),
        "material": rods.material if rods else None,
        "source": metrics.get("source"),
        "top_candidates": top_candidates,
    }


def scalar(row: dict, key: str):
    node = row.get(key)
    if isinstance(node, dict):
        return node.get("result")
    return node


def check_continuity(rows: list[dict], label: str) -> list[str]:
    issues: list[str] = []
    numeric_keys = [
        "torque",
        "displacement",
        "stroke",
        "mps",
        "acceleration",
        "rod_loading",
        "rod_stress",
    ]
    for i in range(1, len(rows)):
        prev, cur = rows[i - 1], rows[i]
        for key in numeric_keys:
            a, b = scalar(prev, key), scalar(cur, key)
            if a is None or b is None:
                issues.append(f"{label}[{i}] {key}: missing value")
        for field in CATEGORICAL:
            if prev.get(field) != cur.get(field):
                if field == "material":
                    ry0, ry1 = prev.get("req_yield"), cur.get("req_yield")
                    crossed = False
                    if ry0 is not None and ry1 is not None:
                        for thresh in (710.0, 880.0):
                            if (ry0 - thresh) * (ry1 - thresh) <= 0 and ry0 != ry1:
                                crossed = True
                    if crossed:
                        continue
                issues.append(
                    f"{label}[{i}]: categorical '{field}' flipped "
                    f"{prev.get(field)!r} → {cur.get(field)!r} without explainable threshold"
                )
    return issues


def main() -> None:
    comparison_mode = "constant_power_resized_design"
    pipeline = SemanticKernelPipeline(provider=DeterministicProvider())
    sweep_a = []
    for rpm in range(5000, 13001, 500):
        result = pipeline.run(
            f"Design a {rpm} RPM naturally aspirated V8 producing {HOLD_HP} horsepower."
        )
        sweep_a.append({"rpm": rpm, "hp": HOLD_HP, **chain(result, comparison_mode=comparison_mode)})

    sweep_b = []
    for hp in range(200, 901, 100):
        result = pipeline.run(
            f"Design a {HOLD_RPM} RPM naturally aspirated V8 producing {hp} horsepower."
        )
        sweep_b.append({"rpm": HOLD_RPM, "hp": hp, **chain(result, comparison_mode=comparison_mode)})

    out = {
        "schema": {
            "authoritative": {
                "physics": [
                    "torque",
                    "displacement",
                    "stroke",
                    "mps",
                    "acceleration",
                    "rod_loading",
                    "rod_stress",
                ],
                "material_requirement": ["req_yield", "mass_sensitive", "material", "source"],
                "candidate_ranking": "top_candidates[] (owns limiting_margin / margins / hard_constraints_met)",
                "comparison_mode": (
                    "Every sweep row declares comparison_mode. "
                    "constant_power_resized_design = BMEP-derived displacement re-sizes with RPM/HP."
                ),
            },
            "removed_null_aliases": [
                "limiting_margin",
                "req_fatigue",
                "req_temp",
                "hard_constraints_met",
            ],
        },
        "holds": {"sweep_a_hp": HOLD_HP, "sweep_b_rpm": HOLD_RPM},
        "comparison_mode": comparison_mode,
        "baseline_note": (
            "V8/500hp and V8/7000rpm deliberately chosen for continuity "
            "(not V12/800 worked example). "
            f"comparison_mode={comparison_mode}: rod load may fall as RPM rises because "
            "displacement shrinks under constant-power BMEP sizing."
        ),
        "sweep_a": sweep_a,
        "sweep_b": sweep_b,
        "issues_a": check_continuity(sweep_a, "sweep_a"),
        "issues_b": check_continuity(sweep_b, "sweep_b"),
    }
    out_path = ROOT / "output" / "continuity_sweeps.json"
    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2))
    print(f"wrote {out_path}")
    print(f"issues_a={out['issues_a']} issues_b={out['issues_b']}")
    row = sweep_a[0]
    assert "limiting_margin" not in row
    assert "req_fatigue" not in row
    assert "req_temp" not in row
    assert "hard_constraints_met" not in row
    assert row["comparison_mode"] == comparison_mode
    assert all("comparison_mode" in x for x in sweep_a + sweep_b)
    assert row["top_candidates"][0]["limiting_margin"] is not None
    print("schema OK: comparison_mode declared; limiting_margin only under top_candidates")


if __name__ == "__main__":
    main()
