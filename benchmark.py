#!/usr/bin/env python3
"""Benchmark JARVIS estimates against published reference engines."""

from __future__ import annotations

import json
from pathlib import Path

from verification.benchmark import run_benchmark

ROOT = Path(__file__).resolve().parent


def main() -> None:
    report = run_benchmark(include_jarvis=True)
    out = ROOT / "output" / "benchmark_results.json"
    accuracy = ROOT / "output" / "reference_engine_accuracy.json"
    out.write_text(json.dumps(report, indent=2, default=str))
    accuracy.write_text(
        json.dumps(
            {
                "aggregates": report.get("aggregates"),
                "interpretation": report.get("interpretation"),
                "per_engine_errors": [
                    {
                        "id": e["id"],
                        "errors_percent": (e.get("jarvis") or {}).get("errors_percent"),
                        "kinematic_status": e["kinematic"]["status"],
                    }
                    for e in report["engines"]
                ],
            },
            indent=2,
        )
    )
    print(f"wrote {out}")
    print(f"wrote {accuracy}")
    print("aggregates:", json.dumps(report.get("aggregates"), indent=2))


if __name__ == "__main__":
    main()
