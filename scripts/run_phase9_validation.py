#!/usr/bin/env python3
"""Phase 9.0 validation runner — evidence ingestion without maturity changes."""

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
    out.mkdir(parents=True, exist_ok=True)
    assert _histogram() == EXPECTED

    write_evidence_audit(out)
    write_evidence_collection_plan(out)
    dash = write_m4_readiness_dashboard(out)
    summary = {
        "phase": "9.0",
        "histogram": _histogram(),
        "m4_readiness": json.loads(dash.read_text()),
        "policy": "Evidence ingestion only — no maturity promotion.",
    }
    (out / "phase9_evidence_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print(json.dumps(summary, indent=2))
    print("Phase 9.0 OK")


if __name__ == "__main__":
    main()
