#!/usr/bin/env python3
"""Run independent formula validation against output/physics_analysis.json."""

from __future__ import annotations

import json
from pathlib import Path

from knowledge.equations.catalog import EQUATION_CATALOG
from verification.formula_validator import validate_output_physics_file

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    formula_report = validate_output_physics_file(ROOT / "output" / "physics_analysis.json")
    ref_report = {
        "equations": EQUATION_CATALOG,
        "independent_verification": formula_report,
        "policy": (
            "validation_status UNVALIDATED/OUT_OF_MODEL remains unless literature + independent "
            "recompute both succeed. Confidence is not inflated by software tests alone."
        ),
    }
    (ROOT / "output" / "formula_reference_report.json").write_text(json.dumps(ref_report, indent=2, default=str))
    print(json.dumps({"passed": formula_report["passed"], "fail_count": formula_report["fail_count"]}, indent=2))


if __name__ == "__main__":
    main()
