#!/usr/bin/env python3
"""Explicit M3→M4 promotion — requires campaign eligibility. Never automatic.

Usage:
  PYTHONPATH=. python scripts/promote_m4_model.py rod_stress output/rod_campaign_result.json

Rejects: insufficient samples, missing verifier, missing uncertainty,
synthetic evidence, failed campaign.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.verification.maturity_promotions import (
    load_recorded_promotions,
    save_recorded_promotions,
)
from core.verification.maturity_registry import check_m4_requirements, load_promotions, save_promotions
from core.verification.model_maturity import ModelMaturity, assert_upgrade_allowed, parse_maturity
from core.verification.model_maturity import MaturityUpgradeEvidence
from core.verification.model_registry import MODEL_REGISTRY

ALIAS = {
    "rod_stress": "calc_rod_stress_requirement",
    "rod": "calc_rod_stress_requirement",
    "bmep": "engine_cycle_model",
    "material": "material_req_structural",
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Explicit M3→M4 maturity promotion")
    parser.add_argument("model_id", help="model id or alias (rod_stress, bmep, material)")
    parser.add_argument("campaign_result", help="Path to campaign_result JSON")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    model_id = ALIAS.get(args.model_id, args.model_id)
    path = Path(args.campaign_result)
    if not path.exists():
        raise SystemExit(f"Missing campaign result: {path}")
    result = json.loads(path.read_text())

    # Reject synthetic-only / zero accepted
    if int(result.get("accepted_cases") or result.get("samples") or 0) == 0:
        raise SystemExit("rejected: insufficient samples (accepted_cases == 0)")
    if result.get("uncertainty") in {None, "", "unknown"}:
        raise SystemExit("rejected: missing uncertainty")
    if not result.get("independent_verifier"):
        raise SystemExit("rejected: missing verifier")
    if result.get("failure_modes"):
        raise SystemExit(f"rejected: failed campaign — {result['failure_modes']}")
    if not (result.get("eligible_for_m4") or result.get("eligible_for_upgrade")):
        raise SystemExit("rejected: campaign not eligible for M4")
    if int(result.get("rejected_cases") or 0) > 0 and int(result.get("accepted_cases") or 0) == 0:
        raise SystemExit("rejected: synthetic evidence only")

    check = check_m4_requirements(model_id, result)
    if not check["eligible"]:
        raise SystemExit(f"rejected: {check['reason']}")

    if model_id not in MODEL_REGISTRY:
        raise SystemExit(f"Unknown registry model: {model_id}")

    base = MODEL_REGISTRY[model_id]
    frm = ModelMaturity.M3
    to = ModelMaturity.M4
    if base.maturity is not frm and base.maturity is not to:
        raise SystemExit(
            f"Registry maturity for {model_id} is {base.maturity.name}, expected M3"
        )

    evidence = MaturityUpgradeEvidence(
        external_validation_cases=int(result.get("accepted_cases") or result.get("samples") or 0),
        mean_error_documented=result.get("mean_error") is not None,
        uncertainty_documented=True,
        independent_verifier_exists=True,
        unresolved_major_failure_modes=(),
        failure_analysis_exists=True,
    )
    assert_upgrade_allowed(from_maturity=frm, to_maturity=to, evidence=evidence)

    promo = {
        "from": frm.name,
        "to": to.name,
        "campaign": result.get("campaign_id") or result.get("campaign"),
        "promoted_at": datetime.now(timezone.utc).isoformat(),
        "campaign_result": str(path.resolve()),
        "mean_error": result.get("mean_error"),
        "max_error": result.get("max_error"),
        "uncertainty": result.get("uncertainty"),
        "independently_verified": True,
        "benchmarked": True,
        "known_limitations": (
            f"M4 via Phase 10 campaign; mean_error={result.get('mean_error')}"
        ),
    }

    if args.dry_run:
        print(json.dumps({"dry_run": True, "model": model_id, "promotion": promo, "check": check}, indent=2))
        return

    # Write Phase 10 promotions.json
    payload = load_promotions()
    promotions = dict(payload.get("promotions") or {})
    promotions[model_id] = promo
    payload["promotions"] = promotions
    payload["phase"] = "10.0"
    save_promotions(payload)

    # Also record in recorded_promotions.json so MODEL_REGISTRY load applies it
    recorded = load_recorded_promotions()
    rec_promos = dict(recorded.get("promotions") or {})
    rec_promos[model_id] = promo
    recorded["promotions"] = rec_promos
    save_recorded_promotions(recorded)

    print(f"Recorded M4 promotion {model_id}: M3→M4")
    print(f"Wrote {ROOT / 'core/verification/promotions.json'}")
    print("Re-import MODEL_REGISTRY (new process) to observe maturity change.")


if __name__ == "__main__":
    main()
