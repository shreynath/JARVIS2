"""Evidence review workflow — PENDING → APPROVED / REJECTED only after checklist."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

from core.verification.evidence_pipeline import EvidenceValidationError, EvidenceValidator
from core.verification.evidence_store import (
    delete_pending,
    load_approved,
    load_pending,
    load_rejected,
    save_approved,
    save_rejected,
)
from core.verification.raw_evidence import RawEvidenceRecord


class ReviewState(str, Enum):
    PENDING = "PENDING"
    REJECTED = "REJECTED"
    APPROVED = "APPROVED"


@dataclass
class EvidenceReview:
    """Review packet for a raw evidence record."""

    record_id: str
    state: ReviewState
    checklist: dict[str, bool] = field(default_factory=dict)
    missing: list[str] = field(default_factory=list)
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        raw = asdict(self)
        raw["state"] = self.state.value
        return raw

    @property
    def can_enter_validation(self) -> bool:
        return self.state is ReviewState.APPROVED and not self.missing


def _review_checklist(record: RawEvidenceRecord) -> tuple[dict[str, bool], list[str]]:
    missing: list[str] = []
    source_verified = bool(record.source_id and record.source_title)
    if not source_verified:
        missing.append("source_verified")
    units_verified = bool(record.unit)
    if not units_verified:
        missing.append("units_verified")
    method = record.provenance.get("measurement_method") or record.provenance.get(
        "measurement_type"
    )
    measurement_method_known = bool(method or record.measurement_type not in {"", "unknown"})
    if not measurement_method_known:
        missing.append("measurement_method_known")
    uncertainty_recorded = bool(record.uncertainty)
    if not uncertainty_recorded:
        missing.append("uncertainty_recorded")
    if record.measurement_type == "synthetic":
        missing.append("synthetic_forbidden")
    if record.measurement_type == "estimate":
        missing.append("estimate_not_measurement")
    checklist = {
        "source_verified": source_verified,
        "units_verified": units_verified,
        "measurement_method_known": measurement_method_known,
        "uncertainty_recorded": uncertainty_recorded,
        "provenance_present": bool(record.provenance),
        "not_synthetic": record.measurement_type != "synthetic",
    }
    return checklist, missing


def review_record(record: RawEvidenceRecord) -> EvidenceReview:
    checklist, missing = _review_checklist(record)
    if record.status.value == "approved":
        state = ReviewState.APPROVED
    elif record.status.value == "rejected":
        state = ReviewState.REJECTED
    else:
        state = ReviewState.PENDING
    return EvidenceReview(
        record_id=record.id,
        state=state,
        checklist=checklist,
        missing=missing,
    )


def approve_record(record_id: str) -> EvidenceReview:
    """Move pending → approved after checklist + pipeline validation."""
    pending = {r.id: r for r in load_pending()}
    if record_id not in pending:
        raise KeyError(f"Pending record not found: {record_id}")
    record = pending[record_id]
    review = review_record(record)
    if review.missing:
        raise ValueError(f"Cannot approve {record_id}: missing {review.missing}")
    EvidenceValidator().validate_raw(record)
    delete_pending(record_id)
    save_approved(record)
    review.state = ReviewState.APPROVED
    review.missing = []
    return review


def reject_record(record_id: str, *, reason: str) -> EvidenceReview:
    pending = {r.id: r for r in load_pending()}
    if record_id not in pending:
        raise KeyError(f"Pending record not found: {record_id}")
    record = pending[record_id]
    delete_pending(record_id)
    save_rejected(record, reason=reason)
    review = review_record(record)
    review.state = ReviewState.REJECTED
    review.notes = reason
    return review


def evidence_review_summary() -> dict[str, Any]:
    pending = load_pending()
    approved = load_approved()
    rejected = load_rejected()
    reviews = [review_record(r) for r in pending]
    return {
        "pending": len(pending),
        "approved": len(approved),
        "rejected": len(rejected),
        "pending_missing_checklist": [
            {"id": r.record_id, "missing": r.missing} for r in reviews if r.missing
        ],
    }
