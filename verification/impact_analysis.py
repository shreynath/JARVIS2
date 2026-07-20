"""Automatic model impact analysis from calculation dependency graph."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from core.verification.model_impact import IMPACT_WEIGHT, ImpactLevel
from core.verification.model_registry import MODEL_REGISTRY, descriptor_for_calc

# Downstream consumer labels for known calc IDs.
_DEFAULT_AFFECTED: dict[str, list[str]] = {
    "calc_torque": ["operating_conditions", "validation"],
    "calc_displacement": ["stroke", "rod_loading", "mean_piston_speed", "material_selection"],
    "calc_stroke": ["mean_piston_speed", "piston_acceleration", "rod_loading", "geometry"],
    "calc_mean_piston_speed": ["validation", "constraint_evaluation"],
    "calc_piston_acceleration": ["rod_loading", "rod_stress"],
    "calc_rod_loading": ["rod_stress", "material_selection", "validation"],
    "calc_rod_stress_requirement": ["material_selection", "validation", "constraints"],
    "calc_heat_rejection": ["combustion_temperature", "material_selection"],
    "calc_combustion_side_temperature": ["material_selection", "constraints"],
    "piston_mass_estimate": ["rod_loading", "rod_stress", "material_selection"],
    "geometry_model": ["stroke", "bore", "rod_loading", "reciprocating_mass"],
    "reciprocating_mass_model": ["rod_loading", "rod_stress"],
    "connecting_rod_model": ["rod_stress", "material_selection", "buckling", "fatigue"],
    "material_req_structural": ["material_selection", "validation"],
    "material_req_piston": ["material_selection", "validation"],
    "material_selection_ranking": ["material_selection"],
    "bmep_assumption_bands": ["displacement", "rod_loading"],
    "engine_cycle_model": ["displacement", "stroke", "mps", "rod_loading"],
    "thermal_model": ["heat_rejection", "combustion_temperature", "material_selection"],
}


def _uncertainty_factor(desc) -> float:
    """Higher when maturity is low and/or lack of external benchmarks."""
    from core.verification.model_maturity import MATURITY_RANK

    u = (5 - MATURITY_RANK[desc.maturity]) / 5.0 * 2.0
    if not desc.benchmarked:
        u += 1.0
    if not desc.independently_verified:
        u += 0.5
    return max(u, 0.5)


def _priority_label(score: float) -> str:
    if score >= 40:
        return "very_high"
    if score >= 20:
        return "high"
    if score >= 8:
        return "medium"
    return "low"


def build_dependency_graph(physics: dict[str, Any] | None) -> dict[str, list[str]]:
    """calc_id → list of dependency calc ids."""
    graph: dict[str, list[str]] = {}
    for c in (physics or {}).get("calculations") or []:
        cid = c.get("id")
        if not cid:
            continue
        graph[cid] = list(c.get("dependency_ids") or [])
    return graph


def reverse_dependents(graph: dict[str, list[str]]) -> dict[str, list[str]]:
    """calc_id → calcs that depend on it."""
    rev: dict[str, list[str]] = defaultdict(list)
    for node, deps in graph.items():
        for d in deps:
            rev[d].append(node)
    return dict(rev)


def analyze_model_impact(physics: dict[str, Any] | None = None) -> dict[str, Any]:
    """Trace dependency fan-out and attach registry impact metadata.

    Phase 7: impact_score = sensitivity_weight * uncertainty * dependency_count
    """
    graph = build_dependency_graph(physics)
    dependents = reverse_dependents(graph)

    models: dict[str, Any] = {}
    for model_id, desc in sorted(MODEL_REGISTRY.items()):
        fanout = len(dependents.get(model_id, []))
        dep_count = max(fanout, len(desc.affected_outputs), 1)
        affected = list(desc.affected_outputs) or list(_DEFAULT_AFFECTED.get(model_id, []))
        for dep in dependents.get(model_id, []):
            if dep not in affected:
                affected.append(dep)
        impact = desc.impact_level
        # sensitivity: invert sensitivity_rank (1 = most sensitive)
        sensitivity = max(0.5, 51 - desc.sensitivity_rank) / 10.0
        uncertainty = _uncertainty_factor(desc)
        closure_score = IMPACT_WEIGHT[impact] * sensitivity * uncertainty * dep_count
        models[model_id] = {
            "impact": impact.value,
            "impact_level": impact.name,
            "outputs": affected,
            "depends_on": graph.get(model_id, []),
            "dependents": dependents.get(model_id, []),
            "fanout": fanout,
            "dependency_count": dep_count,
            "sensitivity": round(sensitivity, 3),
            "uncertainty": round(uncertainty, 3),
            "closure_impact_score": round(closure_score, 3),
            "sensitivity_rank": desc.sensitivity_rank,
            "priority": _priority_label(closure_score),
            "upgrade_priority": desc.upgrade_priority,
            "maturity": desc.maturity.name,
            "subsystem": desc.subsystem,
        }

    ranked = sorted(
        models.items(),
        key=lambda kv: (
            -kv[1]["closure_impact_score"],
            kv[1]["sensitivity_rank"],
            kv[0],
        ),
    )

    return {
        "phase": "7.0",
        "dependency_graph": graph,
        "models": models,
        "impact_ranking": [
            {
                "model": mid,
                "rank": i + 1,
                "impact": meta["impact"],
                "priority": meta["priority"],
                "closure_impact_score": meta["closure_impact_score"],
                "outputs": meta["outputs"],
                "maturity": meta["maturity"],
            }
            for i, (mid, meta) in enumerate(ranked)
        ],
        "model_count": len(models),
        "scoring": "impact_score = impact_weight × sensitivity × uncertainty × dependency_count",
    }


def write_model_impact_report(
    output_dir: Path | str,
    physics: dict[str, Any] | None = None,
) -> Path:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    if physics is None:
        physics_path = out / "physics_analysis.json"
        if physics_path.exists():
            physics = json.loads(physics_path.read_text())
    report = analyze_model_impact(physics)
    path = out / "model_impact_report.json"
    path.write_text(json.dumps(report, indent=2, default=str))
    return path
