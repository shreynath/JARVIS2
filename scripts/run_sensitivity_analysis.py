#!/usr/bin/env python3
"""Sensitivity matrix via independent analytical chain."""

from __future__ import annotations

import json
from pathlib import Path

from verification.sensitivity import run_sensitivity

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    report = run_sensitivity()
    path = ROOT / "output" / "sensitivity_matrix.json"
    path.write_text(json.dumps(report, indent=2))
    print(f"wrote {path}")
    print("dominant rod-stress drivers:", report["dominant_rod_stress_drivers_at_10pct"])


if __name__ == "__main__":
    main()
