#!/usr/bin/env python3
"""Phase 4 orchestrator — generate all scientific validation deliverables."""

from __future__ import annotations

import hashlib
import json
import math
import traceback
from pathlib import Path

from knowledge.equations.catalog import EQUATION_CATALOG
from knowledge.equations.hard_limits import HARD_LIMIT_CATALOG
from verification.benchmark import run_benchmark
from verification.formula_validator import validate_output_physics_file
from verification.monte_carlo import run_monte_carlo
from verification.reality_auditor import (
    component_coverage,
    explainability_from_outputs,
    model_gaps,
    numerical_scan,
    run_reality_audit,
)
from verification.sensitivity import run_sensitivity
from verification.units import run_units_audit

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"


SUPPORTED_ARCHITECTURES = {
    "V12": "parsed via keyword / cylinder_count=12",
    "V10": "parsed via keyword / cylinder_count=10",
    "V8": "parsed via keyword / cylinder_count=8",
    "V6": "parsed via keyword / cylinder_count=6",
    "Inline 6": "parsed via keyword",
    "Inline 4": "parsed via keyword",
    "Flat 6": "parsed via keyword",
}

UNSUPPORTED_ARCHITECTURES = {
    "VR": "No dedicated architecture parser or physics specialization",
    "Rotary / Wankel": "OUT_OF_MODEL — no rotary displacement/combustion model",
    "Radial": "OUT_OF_MODEL",
    "W": "OUT_OF_MODEL",
    "Opposed-piston": "OUT_OF_MODEL",
    "Electric": "OUT_OF_MODEL for ICE physics stack",
    "Hybrid": "OUT_OF_MODEL as combined powertrain",
    "Steam": "OUT_OF_MODEL",
}


def _write(name: str, payload: object) -> None:
    path = OUT / name
    path.write_text(json.dumps(payload, indent=2, default=str))
    print(f"wrote {path}")


def extreme_input_audit(n_focus: int = 40) -> dict:
    from core.reasoning.pipeline import SemanticKernelPipeline
    from llm.ollama_client import DeterministicProvider

    pipeline = SemanticKernelPipeline(provider=DeterministicProvider())
    cases = [
        "Design a 500 RPM naturally aspirated V8 producing 5 horsepower.",
        "Design a 100 RPM naturally aspirated V8 producing 50 horsepower.",
        "Design a 30000 RPM naturally aspirated V8 producing 800 horsepower.",
        "Design a 500000 RPM naturally aspirated V12 producing 800 horsepower.",
        "Design a 9000 RPM naturally aspirated V12 producing 5000 horsepower.",
        "Design a naturally aspirated turbocharged diesel spark ignition engine.",
        "Design a steam V12 producing 800 horsepower.",
        "Design a hydrogen rotary engine producing 400 horsepower.",
        "Design an electric diesel V8 producing 800 horsepower.",
        "Design a V12 using unobtainium pistons and lava cooling.",
        "Design a 9000 RPM naturally aspirated V12 producing 800 horsepower.",
    ]
    # Add synthetic extremes as prompts
    for rpm in (0, -1000, 1, 1000000):
        cases.append(f"Design a {rpm} RPM naturally aspirated V8 producing 800 horsepower.")
    for hp in (0, -50, 1):
        cases.append(f"Design a 7000 RPM naturally aspirated V8 producing {hp} horsepower.")

    results = []
    crashes = 0
    fabricated_on_conflict = 0
    for prompt in cases[:n_focus]:
        entry = {"prompt": prompt, "ok": False}
        try:
            result = pipeline.run(prompt)
            entry["ok"] = True
            entry["evaluation_status"] = result.evaluation_status.value
            entry["physics"] = None if result.physics_analysis is None else "present"
            entry["hard_violations"] = (
                result.validation_report.hard_violations if result.validation_report else None
            )
            if result.requirement_spec.conflicts and result.physics_analysis is not None:
                # Conflicts that still produce physics are a fabrication failure
                # (except if conflict was non-blocking category — aspiration conflicts must block)
                if any(c.get("field") == "aspiration" for c in result.requirement_spec.conflicts):
                    fabricated_on_conflict += 1
                    entry["fabrication_failure"] = True
        except Exception as exc:  # noqa: BLE001 — audit must catch all
            crashes += 1
            entry["ok"] = False
            entry["error"] = f"{type(exc).__name__}: {exc}"
            entry["traceback"] = traceback.format_exc()[-500:]
        results.append(entry)

    return {
        "cases_run": len(results),
        "crashes": crashes,
        "aspiration_conflict_fabrications": fabricated_on_conflict,
        "passed": crashes == 0 and fabricated_on_conflict == 0,
        "results": results,
    }


def reproducibility_check() -> dict:
    from core.reasoning.pipeline import SemanticKernelPipeline
    from llm.ollama_client import DeterministicProvider

    prompt = "Design a 9000 RPM naturally aspirated V12 producing 800 horsepower."
    p = SemanticKernelPipeline(provider=DeterministicProvider())
    a = p.run(prompt)
    b = p.run(prompt)

    def dump(result) -> bytes:
        payload = {
            "resolved": result.requirement_spec.resolved_parameters,
            "physics": result.physics_analysis.model_dump() if result.physics_analysis else None,
            "materials": {cid: c.material for cid, c in result.graph.components.items()},
            "status": result.validation_report.status if result.validation_report else None,
            "hard_violations": result.validation_report.hard_violations if result.validation_report else None,
        }
        return json.dumps(payload, sort_keys=True, default=str).encode()

    ha, hb = hashlib.sha256(dump(a)).hexdigest(), hashlib.sha256(dump(b)).hexdigest()
    return {"hash_a": ha, "hash_b": hb, "byte_identical": ha == hb, "passed": ha == hb}


def mutation_resistance() -> dict:
    """Perturb assumed BMEP/geometry bands via prompts of nearby RPM/HP; expect continuous MPS/torque."""
    from core.reasoning.pipeline import SemanticKernelPipeline
    from llm.ollama_client import DeterministicProvider

    p = SemanticKernelPipeline(provider=DeterministicProvider())
    rows = []
    for rpm in range(8500, 9501, 100):
        r = p.run(f"Design a {rpm} RPM naturally aspirated V12 producing 800 horsepower.")
        if r.physics_analysis is None:
            continue
        mps = r.physics_analysis.by_id("calc_mean_piston_speed")
        torque = r.physics_analysis.by_id("calc_torque")
        rows.append({"rpm": rpm, "mps": mps.result if mps else None, "torque": torque.result if torque else None})
    jumps = []
    for i in range(1, len(rows)):
        if rows[i]["mps"] is None or rows[i - 1]["mps"] is None:
            continue
        dmps = abs(rows[i]["mps"] - rows[i - 1]["mps"])
        # RPM step 100 at ~9000 → ~1.1% ; MPS should move ~same order, not chaotic
        if dmps > 2.0:  # absolute m/s jump threshold for 100 rpm step
            jumps.append({"from": rows[i - 1], "to": rows[i], "dmps": dmps})
    return {"series": rows, "large_jumps": jumps, "passed": len(jumps) == 0}


def architecture_coverage() -> dict:
    return {
        "supported": SUPPORTED_ARCHITECTURES,
        "unsupported": {k: {"status": "unsupported", "reason": v} for k, v in UNSUPPORTED_ARCHITECTURES.items()},
        "policy": "Unsupported architectures must not be silently approximated as Vee/inline ICE geometry.",
    }


def main() -> None:
    OUT.mkdir(exist_ok=True)

    # Ensure baseline physics JSON exists
    from core.reasoning.pipeline import SemanticKernelPipeline
    from llm.ollama_client import DeterministicProvider

    baseline = SemanticKernelPipeline(provider=DeterministicProvider()).run(
        "Design a 9000 RPM naturally aspirated V12 producing 800 horsepower."
    )
    SemanticKernelPipeline(provider=DeterministicProvider()).write_outputs(baseline, OUT)

    # Formula + units + MC + sensitivity
    formula = validate_output_physics_file(OUT / "physics_analysis.json")
    _write(
        "formula_reference_report.json",
        {"equations": EQUATION_CATALOG, "hard_limits": HARD_LIMIT_CATALOG, "independent_verification": formula},
    )
    _write("unit_analysis.json", run_units_audit())
    _write("monte_carlo_summary.json", run_monte_carlo(n_samples=1000))
    _write("sensitivity_matrix.json", run_sensitivity())

    physics = json.loads((OUT / "physics_analysis.json").read_text())
    req = json.loads((OUT / "requirement_specification.json").read_text())
    graph = json.loads((OUT / "engine_design_graph.json").read_text())
    validation = json.loads((OUT / "validation_report.json").read_text())

    _write("component_coverage.json", component_coverage(graph, physics, validation))
    _write("model_gaps.json", model_gaps(physics, req, graph))
    _write("explainability_report.json", explainability_from_outputs(physics, req, graph))
    _write("numerical_stability_report.json", numerical_scan(physics))

    # Constraint provenance file (slice)
    _write(
        "constraint_provenance.json",
        {"hard_limits": HARD_LIMIT_CATALOG, "note": "Anonymous numeric gates are forbidden."},
    )

    bench = run_benchmark(include_jarvis=True)
    _write("benchmark_results.json", bench)
    _write(
        "reference_engine_accuracy.json",
        {"aggregates": bench.get("aggregates"), "interpretation": bench.get("interpretation")},
    )

    _write("architecture_coverage.json", architecture_coverage())
    _write("extreme_input_audit.json", extreme_input_audit())
    _write("reproducibility_report.json", reproducibility_check())
    _write("mutation_resistance_report.json", mutation_resistance())

    reality = run_reality_audit(OUT)
    _write("reality_audit.json", reality)

    from core.verification.maturity_report import write_maturity_artifacts

    write_maturity_artifacts(OUT)

    # Restore baseline outputs after extreme audit overwrote working tree via other runs —
    # re-write baseline once more for a clean primary artifact set.
    SemanticKernelPipeline(provider=DeterministicProvider()).write_outputs(baseline, OUT)

    summary = {
        "reality_overall_confidence": reality.get("overall_confidence"),
        "average_maturity": reality.get("average_maturity"),
        "average_maturity_rank": reality.get("average_maturity_rank"),
        "formula_passed": formula.get("passed"),
        "units_passed": run_units_audit().get("passed"),
        "numerical_passed": numerical_scan(physics).get("passed"),
        "auditor_no_physics_engine_import": reality["auditor_import_gate"]["passed"],
    }
    _write("phase4_validation_summary.json", summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
