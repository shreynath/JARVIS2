#!/usr/bin/env python3
"""Phase 9.5 validation — evidence expansion without maturity changes."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.verification.campaign_readiness import check_campaign_ready, m4_histogram_locked
from core.verification.dataset_templates import (
    BMEP_TEMPLATE,
    MATERIAL_TEMPLATE,
    ROD_TEMPLATE,
    template_headers,
)
from core.verification.evidence_audit import build_evidence_audit, write_evidence_audit
from core.verification.evidence_collection import (
    write_evidence_collection_plan,
    write_m4_readiness_dashboard,
)
from core.verification.model_maturity import ModelMaturity
from core.verification.model_registry import MODEL_REGISTRY

EXPECTED = {"M0": 3, "M1": 1, "M2": 9, "M3": 10, "M4": 0, "M5": 0}


def _histogram() -> dict[str, int]:
    return m4_histogram_locked()


def main() -> None:
    out = ROOT / "output"
    out.mkdir(parents=True, exist_ok=True)
    assert _histogram() == EXPECTED

    templates_ok = all(
        p.exists() for p in (ROD_TEMPLATE, BMEP_TEMPLATE, MATERIAL_TEMPLATE)
    )
    assert templates_ok
    assert len(template_headers(ROD_TEMPLATE)) >= 10

    write_evidence_audit(out)
    write_evidence_collection_plan(out)
    dash = write_m4_readiness_dashboard(out)
    readiness = {
        "rod_stress": check_campaign_ready("rod_stress"),
        "bmep": check_campaign_ready("bmep"),
        "material": check_campaign_ready("material"),
    }
    summary = {
        "phase": "9.5",
        "histogram": _histogram(),
        "templates_present": templates_ok,
        "m4_readiness": json.loads(dash.read_text()),
        "campaign_readiness": readiness,
        "evidence_state": build_evidence_audit()["evidence_state"],
        "policy": "Evidence expansion only — no maturity promotion.",
    }
    (out / "phase95_evidence_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print(json.dumps(summary, indent=2))
    print("Phase 9.5 OK")


if __name__ == "__main__":
    main()
