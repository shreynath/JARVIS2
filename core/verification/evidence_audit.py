"""External evidence audit — inventory without maturity mutation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.verification.datasets.bmep import load_all_bmep_families
from core.verification.datasets.rod_validation.loader import load_rod_cases, rod_dataset_inventory
from core.verification.evidence_pipeline import EvidenceValidator
from core.verification.evidence_quality import quality_score
from core.verification.evidence_store import load_approved, load_pending, load_rejected
from core.verification.material_validation import load_material_cases
from core.verification.raw_evidence import RawEvidenceRecord


def build_evidence_state() -> dict[str, Any]:
    """Phase 9.5 snapshot for reality audit — no maturity mutation."""
    from core.verification.campaign_readiness import check_campaign_ready

    pending = load_pending()
    approved = load_approved()
    rejected = load_rejected()
    rod_inv = rod_dataset_inventory()
    bmep = load_all_bmep_families()
    material = load_material_cases()
    validated_cases = (
        rod_inv["total_cases"]
        + sum(len(v) for v in bmep.values())
        + len(material)
        + len(approved)
    )
    m4_ready = sum(
        1
        for campaign in ("rod_stress", "bmep", "material")
        if check_campaign_ready(campaign)["ready"]
    )
    return {
        "validated_cases": validated_cases,
        "pending_cases": len(pending),
        "rejected_cases": len(rejected),
        "m4_ready_models": m4_ready,
    }


def build_evidence_audit() -> dict[str, Any]:
    pending = load_pending()
    approved = load_approved()
    rejected = load_rejected()
    rod_inv = rod_dataset_inventory()
    bmep = load_all_bmep_families()
    material = load_material_cases()
    validator = EvidenceValidator()

    validated_cases = 0
    promotion_eligible = 0
    estimated_values = 0
    missing_sources = 0

    for rec in pending + approved:
        if not rec.source_id:
            missing_sources += 1
        if rec.measurement_type in {"estimate", "synthetic"}:
            estimated_values += 1
        try:
            validator.validate_raw(rec)
            if rec.status.value == "approved":
                validated_cases += 1
                promotion_eligible += 1
        except Exception:
            pass

    # Existing campaign geometry cases count toward datasets but not promotion
    datasets = (
        rod_inv["total_cases"]
        + sum(len(v) for v in bmep.values())
        + len(material)
    )

    return {
        "phase": "9.5",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "datasets": datasets,
        "validated_cases": validated_cases,
        "pending_review": len(pending),
        "approved_raw": len(approved),
        "rejected_raw": len(rejected),
        "missing_sources": missing_sources,
        "estimated_values": estimated_values,
        "promotion_eligible_cases": promotion_eligible,
        "evidence_state": build_evidence_state(),
        "rod_inventory": rod_inv,
        "bmep_family_counts": {k: len(v) for k, v in bmep.items()},
        "material_cases": len(material),
        "policy": (
            "Audit counts evidence only. Registry maturity unchanged. "
            "promotion_eligible requires approved + validated raw records."
        ),
    }


def write_evidence_audit(output_dir: Path | str) -> Path:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "evidence_audit.json"
    path.write_text(json.dumps(build_evidence_audit(), indent=2, default=str))
    return path
