#!/usr/bin/env python3
"""Independent reality audit entrypoint — does not import PhysicsEngine."""

from __future__ import annotations

import json
from pathlib import Path

from verification.reality_auditor import run_reality_audit

ROOT = Path(__file__).resolve().parent


def main() -> None:
    report = run_reality_audit(ROOT / "output")
    out = ROOT / "output" / "reality_audit.json"
    out.write_text(json.dumps(report, indent=2, default=str))
    print(f"wrote {out}")
    print(f"overall_confidence={report['overall_confidence']}")
    print(f"scientific_score={report['scientific_score']}")
    print(f"auditor_import_gate_passed={report['auditor_import_gate']['passed']}")
    print(f"formula_passed={report['formula_correctness']['passed']}")
    if not report["auditor_import_gate"]["passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
