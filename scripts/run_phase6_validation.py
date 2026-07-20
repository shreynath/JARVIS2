#!/usr/bin/env python3
"""Phase 6 orchestrator — external validation, calibration, failure prioritization."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.verification.maturity_report import write_maturity_artifacts
from core.verification.model_maturity import ModelMaturity
from core.verification.model_registry import MODEL_REGISTRY
from core.verification.phase6_reports import write_phase6_reports
from core.verification.upgrade_report import write_model_upgrade_report
from verification.benchmark import run_benchmark
from verification.impact_analysis import write_model_impact_report
from verification.reality_auditor import run_reality_audit

OUT = ROOT / "output"

# Locked Phase 5.0 / Phase 6.0 maturity histogram — must not inflate.
EXPECTED_MATURITY_COUNTS = {"M0": 3, "M1": 1, "M2": 9, "M3": 10, "M4": 0, "M5": 0}


def _write(name: str, payload: object) -> Path:
    path = OUT / name
    path.write_text(json.dumps(payload, indent=2, default=str))
    print(f"wrote {path}")
    return path


def maturity_invariance_check() -> dict:
    counts = {m.name: 0 for m in ModelMaturity}
    for desc in MODEL_REGISTRY.values():
        counts[desc.maturity.name] += 1
    return {
        "expected": EXPECTED_MATURITY_COUNTS,
        "actual": counts,
        "passed": counts == EXPECTED_MATURITY_COUNTS,
        "m4_count": counts["M4"],
        "m5_count": counts["M5"],
    }


def main() -> None:
    OUT.mkdir(exist_ok=True)

    # Ensure baseline physics outputs exist for auditor (do not mutate via calibration).
    from core.reasoning.pipeline import SemanticKernelPipeline
    from llm.ollama_client import DeterministicProvider

    baseline = SemanticKernelPipeline(provider=DeterministicProvider()).run(
        "Design a 9000 RPM naturally aspirated V12 producing 800 horsepower."
    )
    SemanticKernelPipeline(provider=DeterministicProvider()).write_outputs(baseline, OUT)

    phase6_paths = write_phase6_reports(OUT, include_jarvis=True)
    for name, path in phase6_paths.items():
        print(f"wrote {path}")

    write_maturity_artifacts(OUT)
    write_model_impact_report(OUT)
    write_model_upgrade_report(OUT)

    bench = run_benchmark(include_jarvis=False)
    _write("benchmark_results.json", bench)
    _write(
        "reference_engine_accuracy.json",
        {"engines": len(bench.get("engines") or []), "interpretation": bench.get("interpretation")},
    )

    reality = run_reality_audit(OUT)
    _write("reality_audit.json", reality)
    _write("final_reality_audit.json", reality)

    invariance = maturity_invariance_check()
    mps = baseline.physics_analysis.by_id("calc_mean_piston_speed") if baseline.physics_analysis else None
    torque = baseline.physics_analysis.by_id("calc_torque") if baseline.physics_analysis else None

    summary = {
        "phase": "6.0",
        "scientific_confidence": reality.get("scientific_confidence"),
        "validated_models": reality.get("validated_models"),
        "unvalidated_high_impact_models": reality.get("unvalidated_high_impact_models"),
        "known_biases": reality.get("known_biases"),
        "recommended_research": reality.get("recommended_research"),
        "maturity_invariance": invariance,
        "baseline": {
            "mps_passes": None if mps is None else mps.passes,
            "torque_nm": None if torque is None else torque.result,
            "hard_violations": (
                baseline.validation_report.hard_violations if baseline.validation_report else None
            ),
        },
        "auditor_import_gate_passed": reality["auditor_import_gate"]["passed"],
        "passed": (
            invariance["passed"]
            and reality["auditor_import_gate"]["passed"]
            and (mps is not None and mps.passes is False)
        ),
    }
    summary["external_case_count"] = (reality.get("phase6") or {}).get(
        "external_case_count"
    ) or (reality.get("validation_coverage") or {}).get("matrix_case_count")

    _write("phase6_validation_summary.json", summary)
    print(json.dumps({k: summary[k] for k in ("passed", "scientific_confidence", "maturity_invariance")}, indent=2))
    if not summary["passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
