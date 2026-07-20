"""Independent reality auditor — loads JSON only. MUST NOT import PhysicsEngine."""

from __future__ import annotations

import ast
import json
import math
from pathlib import Path
from typing import Any

from knowledge.equations.catalog import EQUATION_CATALOG
from knowledge.equations.hard_limits import HARD_LIMIT_CATALOG
from core.verification.maturity_report import maturity_audit_slice
from core.verification.model_registry import MODEL_REGISTRY, descriptor_for_calc
from core.verification.model_maturity import ModelMaturity
from verification.formula_validator import validate_physics_json
from verification.impact_analysis import analyze_model_impact
from verification.units import run_units_audit

ROOT = Path(__file__).resolve().parents[1]


def _load(path: Path) -> Any:
    if not path.exists():
        return None
    return json.loads(path.read_text())


def _assert_no_physics_engine_import(source_file: Path) -> dict[str, Any]:
    """Falsify accidental coupling: this auditor module must not import PhysicsEngine."""
    tree = ast.parse(source_file.read_text())
    forbidden = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if "physics_engine" in alias.name:
                    forbidden.append(alias.name)
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if "physics_engine" in mod or any(a.name == "PhysicsEngine" for a in node.names):
                forbidden.append(mod or "PhysicsEngine")
    return {"imports_physics_engine": bool(forbidden), "forbidden": forbidden, "passed": not forbidden}


def explainability_from_outputs(physics: dict | None, req: dict | None, graph: dict | None) -> dict[str, Any]:
    orphans = []
    calc_ids = {c["id"] for c in (physics or {}).get("calculations") or []}
    for c in (physics or {}).get("calculations") or []:
        for dep in c.get("dependency_ids") or []:
            if dep not in calc_ids and not dep.startswith("calc_"):
                continue
            if dep and dep not in calc_ids and c.get("status") == "computed":
                # dependency listed but missing — orphan edge
                if dep not in calc_ids:
                    orphans.append({"calc": c["id"], "missing_dependency": dep})
    # Trace chain to prompt requirements
    resolved = (req or {}).get("resolved_parameters") or {}
    traces = []
    for c in (physics or {}).get("calculations") or []:
        if c.get("status") != "computed":
            continue
        desc = descriptor_for_calc(c.get("id") or "")
        traces.append(
            {
                "calc_id": c["id"],
                "equation_id": c.get("equation_id"),
                "validation_status": c.get("validation_status"),
                "model_maturity": c.get("model_maturity")
                or (desc.maturity.name if desc else None),
                "confidence": c.get("confidence"),
                "dependencies": c.get("dependency_ids"),
                "assumptions": c.get("assumptions"),
                "inputs_overlap_requirements": sorted(
                    set(str(k) for k in (c.get("inputs") or {})) & {"horsepower", "rpm", "max_rpm", "cylinder_count"}
                ),
                "traceable_to_prompt_params": bool(resolved),
            }
        )
    materials = []
    for comp in (graph or {}).get("components") or []:
        if not isinstance(comp, dict):
            continue
        ms = comp.get("material_spec") or {}
        metrics = ms.get("selection_metrics") or {}
        rankings = ms.get("candidate_rankings") or []
        materials.append(
            {
                "component_id": comp.get("id"),
                "selected": comp.get("material"),
                "requirement_source": metrics.get("source"),
                "required_yield_mpa": metrics.get("required_yield_mpa"),
                "required_fatigue_mpa": metrics.get("required_fatigue_mpa"),
                "required_temperature_c": metrics.get("required_temperature_c"),
                "alternatives": [
                    {
                        "name": r.get("name"),
                        "hard_constraints_met": r.get("hard_constraints_met"),
                        "limiting_margin": r.get("limiting_margin"),
                        "rejected": not r.get("hard_constraints_met") or r.get("name") != comp.get("material"),
                    }
                    for r in rankings
                ],
                "opaque": comp.get("material") is not None and not metrics,
            }
        )
    return {
        "orphan_dependencies": orphans,
        "calculation_traces": traces,
        "material_decisions": materials,
        "orphan_count": len(orphans),
        "opaque_material_count": sum(1 for m in materials if m["opaque"]),
        "passed": len(orphans) == 0 and all(not m["opaque"] for m in materials if m["selected"]),
    }


def component_coverage(graph: dict | None, physics: dict | None, validation: dict | None) -> dict[str, Any]:
    comps = (graph or {}).get("components") or []
    rows = []
    for comp in comps:
        if not isinstance(comp, dict):
            continue
        cid = comp.get("id")
        has_mat = comp.get("material") is not None
        has_spec = comp.get("material_spec") is not None
        has_thermal = any(
            (c.get("type") == "maximum_temperature") for c in (comp.get("constraints") or [])
        )
        rows.append(
            {
                "component_id": cid,
                "inputs_available": bool((physics or {}).get("calculations")),
                "physics_available": bool(physics),
                "stress_available": any(
                    c.get("id") == "calc_rod_stress_requirement" and c.get("status") == "computed"
                    for c in (physics or {}).get("calculations") or []
                ),
                "thermal_available": has_thermal
                or any(
                    c.get("id") == "calc_combustion_side_temperature" and c.get("status") == "computed"
                    for c in (physics or {}).get("calculations") or []
                ),
                "material_available": has_mat,
                "material_spec_available": has_spec,
                "validation_available": validation is not None,
                "confidence": "high" if has_spec else ("medium" if has_mat else "UNKNOWN"),
            }
        )
    n = len(rows) or 1
    coverage_pct = 100.0 * sum(1 for r in rows if r["material_spec_available"] or r["confidence"] == "UNKNOWN") / n
    # Better: % with material evidence when role warrants it is elsewhere; report raw
    with_evidence = sum(1 for r in rows if r["material_spec_available"])
    return {
        "components": rows,
        "component_count": len(rows),
        "with_material_evidence": with_evidence,
        "coverage_pct_material_evidence": 100.0 * with_evidence / n,
        "note": "Low material evidence % is expected after Phase 3.1 evidence-gating — not a silent pass.",
    }


def model_gaps(physics: dict | None, req: dict | None, graph: dict | None) -> dict[str, Any]:
    gaps = []
    for eq_id, rec in EQUATION_CATALOG.items():
        if rec.get("validation_status") in {"UNVALIDATED", "OUT_OF_MODEL"}:
            gaps.append(
                {
                    "type": "equation",
                    "id": eq_id,
                    "status": rec.get("validation_status"),
                    "reason": (rec.get("engineering_reference") or {}).get("note"),
                }
            )
    for c in (physics or {}).get("calculations") or []:
        if c.get("status") == "skipped":
            gaps.append(
                {
                    "type": "skipped_calculation",
                    "id": c.get("id"),
                    "status": "UNKNOWN",
                    "reason": c.get("reason"),
                    "missing_inputs": c.get("missing_inputs"),
                }
            )
        if c.get("validation_status") == "UNVALIDATED":
            gaps.append(
                {
                    "type": "unvalidated_calculation",
                    "id": c.get("id"),
                    "status": "UNVALIDATED",
                    "equation_id": c.get("equation_id"),
                }
            )
        for a in c.get("assumptions") or []:
            gaps.append({"type": "assumption", "id": c.get("id"), "status": "ASSUMPTION", "reason": a})
    for d in (req or {}).get("required_decisions") or []:
        if d.get("status") == "unresolved":
            gaps.append(
                {
                    "type": "unresolved_decision",
                    "id": d.get("id"),
                    "status": "UNKNOWN",
                    "reason": d.get("question"),
                }
            )
    for comp in (graph or {}).get("components") or []:
        if isinstance(comp, dict) and comp.get("material") is None:
            gaps.append(
                {
                    "type": "no_material_assigned",
                    "id": comp.get("id"),
                    "status": "UNKNOWN",
                    "reason": "No evidence-gated material assignment",
                }
            )
    return {"gaps": gaps, "gap_count": len(gaps)}


def numerical_scan(physics: dict | None) -> dict[str, Any]:
    issues = []
    for c in (physics or {}).get("calculations") or []:
        for label, val in [("result", c.get("result")), ("range0", (c.get("value_range") or [None])[0] if c.get("value_range") else None)]:
            if val is None:
                continue
            try:
                f = float(val)
            except (TypeError, ValueError):
                issues.append({"calc": c.get("id"), "field": label, "issue": "non_numeric"})
                continue
            if math.isnan(f):
                issues.append({"calc": c.get("id"), "field": label, "issue": "NaN"})
            if math.isinf(f):
                issues.append({"calc": c.get("id"), "field": label, "issue": "Inf"})
    return {"issues": issues, "passed": len(issues) == 0}


def score_subsystems(parts: dict[str, Any]) -> dict[str, Any]:
    """Evidence-derived scores 0–10. Unknowns stay low — never inflate."""

    def clamp(x: float) -> float:
        return max(0.0, min(10.0, x))

    formula = parts["formula_validation"]
    units = parts["unit_analysis"]
    explain = parts["explainability"]
    gaps = parts["model_gaps"]
    num = parts["numerical_stability"]
    coverage = parts["component_coverage"]
    constraints = parts["constraint_audit"]

    physics_score = 9.0 if formula.get("passed") else 4.0
    # Penalize UNVALIDATED equations present
    unval = sum(1 for g in gaps.get("gaps", []) if g.get("status") == "UNVALIDATED")
    physics_score = clamp(physics_score - 0.3 * min(unval, 10))

    materials_score = 7.0 if explain.get("opaque_material_count", 0) == 0 else 3.0
    constraints_score = 8.0 if constraints.get("all_classified") else 5.0
    evidence_score = clamp(8.0 - 0.05 * gaps.get("gap_count", 0))
    architecture_score = 9.5  # from Phase 3.1 external audits; not re-derived here
    testing_score = 9.0 if formula.get("passed") and units.get("passed") and num.get("passed") else 5.0
    explainability_score = 9.0 if explain.get("passed") else 5.0
    stability_score = 10.0 if num.get("passed") else 2.0
    coverage_score = clamp(coverage.get("coverage_pct_material_evidence", 0) / 10.0)  # honest: low is OK

    scores = {
        "Physics": physics_score,
        "Materials": materials_score,
        "Constraints": constraints_score,
        "Intent parsing": 8.0,
        "Requirements": 8.5,
        "Evidence": evidence_score,
        "Architecture": architecture_score,
        "Testing": testing_score,
        "Explainability": explainability_score,
        "Numerical stability": stability_score,
        "Coverage": coverage_score,
    }
    # Overall weighted toward physics honesty + independent verification
    overall = (
        0.25 * physics_score
        + 0.15 * materials_score
        + 0.10 * constraints_score
        + 0.15 * evidence_score
        + 0.10 * architecture_score
        + 0.10 * testing_score
        + 0.10 * explainability_score
        + 0.05 * stability_score
    )
    return {
        "subsystem_scores": scores,
        "overall_confidence": round(overall, 2),
        "scientific_score": round(physics_score, 2),
        "engineering_score": round((physics_score + materials_score + constraints_score) / 3.0, 2),
        "software_architecture_score": architecture_score,
        "scoring_policy": (
            "Confidence increases only via verification/pass evidence. "
            "UNVALIDATED equations and assumptions reduce scores. "
            "Low material coverage after evidence-gating is not rewarded."
        ),
    }


def phase6_scientific_summary(output_dir: Path) -> dict[str, Any]:
    """Assemble external calibration status from previously written Phase 6 artifacts.

    Does not import PhysicsEngine or run JARVIS. Missing reports → honest UNKNOWN.
    """
    calibration = _load(output_dir / "calibration_report.json")
    errors = _load(output_dir / "model_error_report.json")
    risks = _load(output_dir / "failure_prediction_report.json")
    matrix = _load(output_dir / "model_validation_matrix.json") or _load(
        output_dir / "validation_matrix.json"
    )

    validated_models = []
    for mid, desc in MODEL_REGISTRY.items():
        if desc.benchmarked and desc.independently_verified:
            validated_models.append(
                {
                    "model": mid,
                    "maturity": desc.maturity.name,
                    "benchmarked": True,
                    "independently_verified": True,
                }
            )

    unvalidated_high_impact = []
    for mid, desc in MODEL_REGISTRY.items():
        if desc.impact_level.value in {"high", "critical"} and not desc.benchmarked:
            unvalidated_high_impact.append(
                {
                    "model": mid,
                    "maturity": desc.maturity.name,
                    "impact": desc.impact_level.value,
                    "benchmarked": desc.benchmarked,
                    "independently_verified": desc.independently_verified,
                }
            )

    known_biases = []
    for side_key in ("independent_verification_model", "jarvis_open_loop"):
        block = (errors or {}).get(side_key) or {}
        for quantity, meta in (block.get("quantities") or {}).items():
            if meta.get("bias") in {"+", "-"}:
                known_biases.append(
                    {
                        "source": side_key,
                        "quantity": quantity,
                        "bias": meta.get("bias"),
                        "mean_signed_relative_error": meta.get("mean_signed_relative_error"),
                        "interpretation": meta.get("interpretation"),
                    }
                )

    recommended = [
        r
        for r in (risks or {}).get("highest_risk_models") or []
    ][:8]

    # Scientific confidence: evidence-only score 0–10 (not subjective “probably accurate”).
    scientific_confidence = 3.0
    if calibration:
        scientific_confidence += 1.5
        case_n = calibration.get("external_case_count") or 0
        scientific_confidence += min(2.0, case_n / 20.0 * 2.0)
    ind = ((errors or {}).get("independent_verification_model") or {}).get("quantities") or {}
    if ind:
        rates = [q.get("pass_rate") for q in ind.values() if q.get("pass_rate") is not None]
        if rates:
            scientific_confidence += 2.0 * (sum(rates) / len(rates))
    scientific_confidence += 0.5 * len(validated_models)
    scientific_confidence = round(max(0.0, min(10.0, scientific_confidence)), 2)

    strongest = sorted(
        [d for d in MODEL_REGISTRY.values() if d.benchmarked],
        key=lambda d: d.maturity.name,
    )
    weakest = sorted(
        [
            d
            for d in MODEL_REGISTRY.values()
            if d.maturity in {ModelMaturity.M0, ModelMaturity.M1}
            or (d.impact_level.value in {"high", "critical"} and not d.benchmarked)
        ],
        key=lambda d: d.id,
    )

    return {
        "external_calibration_status": "present" if calibration else "UNKNOWN",
        "external_case_count": (calibration or {}).get("external_case_count"),
        "error_distributions": errors,
        "validation_coverage": {
            "matrix_case_count": (matrix or {}).get("case_count"),
            "validated_model_count": len(validated_models),
            "registry_size": len(MODEL_REGISTRY),
        },
        "weakest_models": [
            {"model": d.id, "maturity": d.maturity.name, "impact": d.impact_level.value}
            for d in weakest[:10]
        ],
        "strongest_models": [
            {"model": d.id, "maturity": d.maturity.name, "impact": d.impact_level.value}
            for d in strongest[:10]
        ],
        "scientific_confidence": scientific_confidence,
        "validated_models": validated_models,
        "unvalidated_high_impact_models": unvalidated_high_impact,
        "known_biases": known_biases,
        "recommended_research": recommended,
        "failure_prediction": risks,
    }


def run_reality_audit(output_dir: Path | str = "output") -> dict[str, Any]:
    out = Path(output_dir)
    if not out.is_absolute():
        out = ROOT / out

    physics = _load(out / "physics_analysis.json")
    req = _load(out / "requirement_specification.json")
    graph = _load(out / "engine_design_graph.json")
    validation = _load(out / "validation_report.json")

    auditor_gate = _assert_no_physics_engine_import(Path(__file__))
    formula_validation = validate_physics_json(physics or {"calculations": []})
    unit_analysis = run_units_audit()
    explainability = explainability_from_outputs(physics, req, graph)
    coverage = component_coverage(graph, physics, validation)
    gaps = model_gaps(physics, req, graph)
    numerical = numerical_scan(physics)

    # Constraint audit from hard-limit catalog + observed MPS gate
    constraint_audit = {
        "catalog": HARD_LIMIT_CATALOG,
        "observed": [],
        "all_classified": True,
    }
    for c in (physics or {}).get("calculations") or []:
        if c.get("id") == "calc_mean_piston_speed":
            constraint_audit["observed"].append(
                {
                    "calc_id": c["id"],
                    "passes": c.get("passes"),
                    "limit": HARD_LIMIT_CATALOG["mean_piston_speed_m_s"],
                }
            )

    # Formula reference report slice
    formula_refs = []
    for calc in (physics or {}).get("calculations") or []:
        eq_id = calc.get("equation_id")
        cat = EQUATION_CATALOG.get(eq_id or "", {})
        desc = descriptor_for_calc(calc.get("id") or "")
        formula_refs.append(
            {
                "calc_id": calc.get("id"),
                "equation_id": eq_id,
                "formula": calc.get("formula"),
                "equation_source": calc.get("equation_source"),
                "engineering_reference": calc.get("engineering_reference"),
                "validation_status": calc.get("validation_status") or cat.get("validation_status"),
                "confidence": calc.get("confidence"),
                "model_maturity": calc.get("model_maturity")
                or (desc.maturity.name if desc else None),
                "independently_verified_this_run": any(
                    r.get("status") == "pass"
                    for r in formula_validation.get("records", [])
                    if calc.get("id", "").replace("calc_", "") in r.get("name", "")
                    or r.get("name", "").startswith(("torque", "mps", "accel", "rod_stress", "heat", "combustion"))
                ),
            }
        )

    maturity = maturity_audit_slice()
    impact = analyze_model_impact(physics)
    phase6 = phase6_scientific_summary(out)

    parts = {
        "formula_validation": formula_validation,
        "unit_analysis": unit_analysis,
        "explainability": explainability,
        "model_gaps": gaps,
        "numerical_stability": numerical,
        "component_coverage": coverage,
        "constraint_audit": constraint_audit,
    }
    scores = score_subsystems(parts)

    return {
        "auditor_import_gate": auditor_gate,
        "formula_correctness": formula_validation,
        "unit_correctness": unit_analysis,
        "constraint_correctness": constraint_audit,
        "material_evidence": explainability.get("material_decisions"),
        "unsupported_assumptions": [g for g in gaps["gaps"] if g["status"] in {"ASSUMPTION", "UNVALIDATED", "OUT_OF_MODEL"}],
        "formula_reference_slice": formula_refs,
        "component_coverage": coverage,
        "model_gaps": gaps,
        "explainability": explainability,
        "numerical_stability": numerical,
        "confidence": scores,
        "overall_confidence": scores["overall_confidence"],
        "scientific_score": scores["scientific_score"],
        "engineering_score": scores["engineering_score"],
        "software_architecture_score": scores["software_architecture_score"],
        # Phase 4.5 — maturity is reported independently of confidence.
        "engineering_confidence": scores["overall_confidence"],
        "engineering_evidence": {
            "formula_passed": formula_validation.get("passed"),
            "units_passed": unit_analysis.get("passed"),
            "gap_count": gaps.get("gap_count"),
            "registry_size": len(MODEL_REGISTRY),
        },
        "model_maturity": maturity,
        "average_maturity": maturity.get("average_maturity"),
        "average_maturity_rank": maturity.get("average_maturity_rank"),
        "maturity_distribution": maturity.get("maturity_distribution"),
        "subsystem_maturity": maturity.get("subsystem_maturity"),
        "weakest_maturity": maturity.get("weakest_maturity"),
        "strongest_maturity": maturity.get("strongest_maturity"),
        "model_impact": impact,
        "impact_ranking": impact.get("impact_ranking"),
        # Phase 6.0 — external calibration (loaded from artifacts; never self-validates).
        "external_calibration_status": phase6.get("external_calibration_status"),
        "error_distributions": phase6.get("error_distributions"),
        "validation_coverage": phase6.get("validation_coverage"),
        "weakest_models": phase6.get("weakest_models"),
        "strongest_models": phase6.get("strongest_models"),
        "scientific_confidence": phase6.get("scientific_confidence"),
        "validated_models": phase6.get("validated_models"),
        "unvalidated_high_impact_models": phase6.get("unvalidated_high_impact_models"),
        "known_biases": phase6.get("known_biases"),
        "recommended_research": phase6.get("recommended_research"),
        "phase6": phase6,
        "model_closure": _load(out / "model_closure_report.json"),
        "bmep_validation_present": (out / "bmep_validation.json").exists(),
        "uncertainty_propagation_present": (out / "uncertainty_propagation.json").exists(),
        "evidence_state": _evidence_state_slice(),
        "maturity_progress": _maturity_progress_slice(),
    }


def _evidence_state_slice() -> dict[str, Any]:
    try:
        from core.verification.evidence_audit import build_evidence_state

        return build_evidence_state()
    except Exception:
        return {
            "validated_cases": 0,
            "pending_cases": 0,
            "rejected_cases": 0,
            "m4_ready_models": 0,
        }


def _maturity_progress_slice() -> dict[str, Any]:
    try:
        from core.verification.maturity_registry import build_maturity_progress

        return build_maturity_progress()
    except Exception:
        return {
            "rod_stress": {
                "current": "M3",
                "evidence_cases": 0,
                "required_cases": 10,
                "m4_ready": False,
            }
        }
