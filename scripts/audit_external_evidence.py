#!/usr/bin/env python3
"""Audit external evidence inventory — no maturity mutation."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.verification.evidence_audit import write_evidence_audit
from core.verification.evidence_collection import (
    write_evidence_collection_plan,
    write_m4_readiness_dashboard,
)
from core.verification.model_maturity import ModelMaturity
from core.verification.model_registry import MODEL_REGISTRY

EXPECTED = {"M0": 3, "M1": 1, "M2": 9, "M3": 10, "M4": 0, "M5": 0}


def _histogram() -> dict[str, int]:
    counts = {m.name: 0 for m in ModelMaturity}
    for d in MODEL_REGISTRY.values():
        counts[d.maturity.name] += 1
    return counts


def main() -> None:
    out = ROOT / "output"
    hist = _histogram()
    assert hist == EXPECTED, f"maturity drift during evidence audit: {hist}"

    audit_path = write_evidence_audit(out)
    plan_path = write_evidence_collection_plan(out)
    dash_path = write_m4_readiness_dashboard(out)

    audit = json.loads(audit_path.read_text())
    dashboard = json.loads(dash_path.read_text())
    print(json.dumps({"audit": audit, "dashboard_title": dashboard.get("title")}, indent=2))
    print(f"wrote {audit_path}")
    print(f"wrote {plan_path}")
    print(f"wrote {dash_path}")
    print("Phase 9.0 evidence audit OK")


if __name__ == "__main__":
    main()
