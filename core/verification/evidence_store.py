"""Evidence persistence — pending vs approved stores (no registry mutation)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.verification.raw_evidence import EvidenceStatus, RawEvidenceRecord

STORE_ROOT = Path(__file__).resolve().parent / "evidence_store"
PENDING_DIR = STORE_ROOT / "pending"
APPROVED_DIR = STORE_ROOT / "approved"
REJECTED_DIR = STORE_ROOT / "rejected"


def _ensure_dirs() -> None:
    PENDING_DIR.mkdir(parents=True, exist_ok=True)
    APPROVED_DIR.mkdir(parents=True, exist_ok=True)
    REJECTED_DIR.mkdir(parents=True, exist_ok=True)


def save_pending(record: RawEvidenceRecord) -> Path:
    _ensure_dirs()
    record.status = EvidenceStatus.PENDING_REVIEW
    path = PENDING_DIR / f"{record.id}.json"
    path.write_text(json.dumps(record.to_dict(), indent=2, default=str) + "\n")
    return path


def save_approved(record: RawEvidenceRecord) -> Path:
    _ensure_dirs()
    record.status = EvidenceStatus.APPROVED
    path = APPROVED_DIR / f"{record.id}.json"
    path.write_text(json.dumps(record.to_dict(), indent=2, default=str) + "\n")
    return path


def load_pending() -> list[RawEvidenceRecord]:
    _ensure_dirs()
    rows: list[RawEvidenceRecord] = []
    for path in sorted(PENDING_DIR.glob("*.json")):
        rows.append(RawEvidenceRecord.from_dict(json.loads(path.read_text())))
    return rows


def load_approved() -> list[RawEvidenceRecord]:
    _ensure_dirs()
    rows: list[RawEvidenceRecord] = []
    for path in sorted(APPROVED_DIR.glob("*.json")):
        rows.append(RawEvidenceRecord.from_dict(json.loads(path.read_text())))
    return rows


def save_rejected(record: RawEvidenceRecord, *, reason: str = "") -> Path:
    _ensure_dirs()
    record.status = EvidenceStatus.REJECTED
    path = REJECTED_DIR / f"{record.id}.json"
    payload = record.to_dict()
    payload["rejection_reason"] = reason
    path.write_text(json.dumps(payload, indent=2, default=str) + "\n")
    return path


def load_rejected() -> list[RawEvidenceRecord]:
    _ensure_dirs()
    rows: list[RawEvidenceRecord] = []
    for path in sorted(REJECTED_DIR.glob("*.json")):
        rows.append(RawEvidenceRecord.from_dict(json.loads(path.read_text())))
    return rows


def delete_pending(record_id: str) -> None:
    path = PENDING_DIR / f"{record_id}.json"
    if path.exists():
        path.unlink()


def list_store_inventory() -> dict[str, Any]:
    pending = load_pending()
    approved = load_approved()
    rejected = load_rejected()
    return {
        "pending_count": len(pending),
        "approved_count": len(approved),
        "rejected_count": len(rejected),
        "pending_ids": [r.id for r in pending],
        "approved_ids": [r.id for r in approved],
        "rejected_ids": [r.id for r in rejected],
    }
