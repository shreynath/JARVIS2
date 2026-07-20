#!/usr/bin/env python3
"""Dimensional analysis audit."""

from __future__ import annotations

import json
from pathlib import Path

from verification.units import run_units_audit

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    report = run_units_audit()
    path = ROOT / "output" / "unit_analysis.json"
    path.write_text(json.dumps(report, indent=2))
    print(f"wrote {path} passed={report['passed']} failures={report['failures']}")


if __name__ == "__main__":
    main()
