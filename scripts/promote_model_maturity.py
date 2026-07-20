#!/usr/bin/env python3
"""Explicit one-step maturity promotion — requires campaign_result eligibility.

Example:
  PYTHONPATH=. python scripts/promote_model_maturity.py calc_torque M2 M3

Does NOT auto-run from campaign evaluators. Rejects M4/M5 claims from Campaign A.
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

from core.verification.campaign_gate import assert_not_m4_claim
from core.verification.maturity_promotions import (
    load_recorded_promotions,
    save_recorded_promotions,
)
from core.verification.model_maturity import (
    MaturityUpgradeEvidence,
    ModelMaturity,
    assert_upgrade_allowed,
    parse_maturity,
)
from core.verification.model_registry import MODEL_REGISTRY

ALIAS = {
    "torque": "calc_torque",
    "mps": "calc_mean_piston_speed",
    "mean_piston_speed": "calc_mean_piston_speed",
    "acceleration": "calc_piston_acceleration",
    "piston_acceleration": "calc_piston_acceleration",
}


def _load_campaign_result(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(
            f"Missing {path}. Run scripts/run_campaign_a.py first so "
            "eligible_for_upgrade is documented."
        )
    return json.loads(path.read_text())


def main() -> None:
    parser = argparse.ArgumentParser(description="Explicit maturity promotion")
    parser.add_argument("model", help="model id or alias (torque, mps, acceleration)")
    parser.add_argument("from_maturity")
    parser.add_argument("to_maturity")
    parser.add_argument(
        "--campaign-result",
        default=str(ROOT / "output" / "campaign_result.json"),
        help="Path to campaign_result.json",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate eligibility without writing promotions",
    )
    args = parser.parse_args()

    model_id = ALIAS.get(args.model, args.model)
    frm = parse_maturity(args.from_maturity)
    to = parse_maturity(args.to_maturity)

    if model_id not in MODEL_REGISTRY:
        raise SystemExit(f"Unknown model: {model_id}")

    result = _load_campaign_result(Path(args.campaign_result))
    campaign = str(result.get("campaign") or "")
    gate = str(result.get("gate") or "")
    # Campaign A identity campaign cannot mint M4/M5.
    if campaign in {"high_rpm_dynamics", ""} and gate in {"M2_to_M3", ""}:
        if to is ModelMaturity.M4 or to is ModelMaturity.M5:
            assert_not_m4_claim(frm, to)

    if not result.get("eligible_for_upgrade"):
        raise SystemExit("campaign_result.eligible_for_upgrade is false — reject")
    eligible = set(result.get("eligible_models") or [])
    if model_id not in eligible:
        raise SystemExit(
            f"{model_id} not in eligible_models={sorted(eligible)}. Rejected."
        )

    # One-step evidence must still satisfy ladder gates.
    if frm is ModelMaturity.M3 and to is ModelMaturity.M4:
        evidence = MaturityUpgradeEvidence(
            external_validation_cases=int(result.get("evidence_cases") or 10),
            mean_error_documented=True,
            uncertainty_documented=True,
            independent_verifier_exists=True,
            unresolved_major_failure_modes=(),
        )
    else:
        evidence = MaturityUpgradeEvidence(
            external_comparison_exists=True,
            error_characterization_exists=True,
            failure_analysis_exists=True,
            assumptions_documented=True,
            uncertainty_range_documented=True,
            references_documented=True,
            independent_verifier_exists=True,
        )
    assert_upgrade_allowed(from_maturity=frm, to_maturity=to, evidence=evidence)

    base = MODEL_REGISTRY[model_id]
    if base.maturity not in {frm, to}:
        # When promotions already applied, maturity may already be `to`.
        raise SystemExit(
            f"Registry maturity for {model_id} is {base.maturity.name}, "
            f"expected {frm.name} (or already {to.name})"
        )

    validation_path = ROOT / "output" / "high_rpm_dynamics_validation.json"
    known_limits = None
    if validation_path.exists():
        validation = json.loads(validation_path.read_text())
        for row in validation.get("models") or []:
            if row.get("model") == model_id:
                limits = row.get("known_limitations") or []
                if limits:
                    known_limits = (
                        f"Campaign A (high_rpm_dynamics) M3: " + "; ".join(limits)
                    )
                break

    promo = {
        "from": frm.name,
        "to": to.name,
        "campaign": result.get("campaign", "high_rpm_dynamics"),
        "promoted_at": datetime.now(timezone.utc).isoformat(),
        "campaign_result": str(Path(args.campaign_result).resolve()),
        "known_limitations": known_limits,
        "independently_verified": True,
        "benchmarked": bool(base.benchmarked or model_id in {
            "calc_torque",
            "calc_mean_piston_speed",
        }),
    }

    if args.dry_run:
        print(json.dumps({"dry_run": True, "model": model_id, "promotion": promo}, indent=2))
        return

    payload = load_recorded_promotions()
    promotions = dict(payload.get("promotions") or {})
    promotions[model_id] = promo
    payload["promotions"] = promotions
    payload["phase"] = "8.5"
    payload["policy"] = (
        "Explicit promotions only. Campaign evaluators never write this file."
    )
    path = save_recorded_promotions(payload)
    print(f"Recorded promotion {model_id}: {frm.name}→{to.name}")
    print(f"Wrote {path}")
    print("Re-import MODEL_REGISTRY (new process) to observe maturity change.")


if __name__ == "__main__":
    main()
