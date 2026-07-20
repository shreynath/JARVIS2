"""Raw evidence → validated case transformation (no maturity side effects).

``EvidenceValidator`` is **externally_verified** — enforces provenance against
raw evidence records, not pipeline-generated design graphs.
Adversarial tests: ``tests/validator_adversarial/test_evidence_validator.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.verification.datasets.validation_case import (
    SystemType,
    ValidationCase,
    ValidationQuality,
)
from core.verification.evidence_quality import is_measurement_grade, quality_score
from core.verification.evidence_source import SourceType
from core.verification.raw_evidence import RawEvidenceRecord
from validation.integrity import VerificationKind, registry_entry


class EvidenceValidationError(ValueError):
    """Raised when raw evidence cannot become a validated case."""


@dataclass
class EvidenceValidator:
    """Enforces provenance / unit / uncertainty requirements (externally_verified)."""

    VALIDATOR_ID = "EvidenceValidator"
    VERIFICATION_KIND = VerificationKind.EXTERNALLY_VERIFIED
    min_quality_for_validation: float = 0.5

    @classmethod
    def verification_metadata(cls):
        return registry_entry(cls.VALIDATOR_ID)

    def validate_raw(self, record: RawEvidenceRecord) -> dict[str, Any]:
        """Return checklist; raises on hard reject."""
        if record.rejects():
            missing = []
            if record.value is None:
                missing.append("value")
            if not record.unit:
                missing.append("unit")
            if not record.source_id:
                missing.append("source_id")
            if not record.provenance:
                missing.append("provenance")
            if not record.uncertainty:
                missing.append("uncertainty")
            if record.measurement_type == "synthetic":
                missing.append("synthetic_forbidden")
            raise EvidenceValidationError(
                f"Raw evidence {record.id!r} rejected: missing {missing}"
            )
        st = record.provenance.get("source_type")
        score = quality_score(
            source_type=st,
            measurement_type=record.measurement_type,
            quality_label=record.quality,
        )
        checklist = {
            "unit_present": bool(record.unit),
            "source_present": bool(record.source_id and record.source_title),
            "provenance_present": bool(record.provenance),
            "uncertainty_present": bool(record.uncertainty),
            "quality_score": score,
            "measurement_grade": is_measurement_grade(score),
        }
        if score < self.min_quality_for_validation:
            raise EvidenceValidationError(
                f"Raw evidence {record.id!r} quality {score} below validation threshold "
                f"(estimate cannot masquerade as measurement)"
            )
        if record.measurement_type == "estimate" and st == SourceType.SECONDARY_ESTIMATE.value:
            raise EvidenceValidationError(
                f"Raw evidence {record.id!r}: SECONDARY_ESTIMATE cannot enter validated cases"
            )
        return checklist

    def to_validation_case(self, record: RawEvidenceRecord) -> ValidationCase:
        checklist = self.validate_raw(record)
        vq = ValidationQuality.MANUFACTURER
        if record.measurement_type == "estimate":
            vq = ValidationQuality.ESTIMATED
        elif record.provenance.get("source_type") == SourceType.PEER_REVIEWED_PAPER.value:
            vq = ValidationQuality.LITERATURE
        return ValidationCase(
            id=record.id,
            system_type=SystemType.MATERIAL if "material" in record.component else SystemType.ENGINE,
            reference_source={
                "source_id": record.source_id,
                "title": record.source_title,
                "provenance": dict(record.provenance),
                "quality_score": checklist["quality_score"],
            },
            inputs={
                "engine": record.engine,
                "engine_id": record.engine_id,
                "component": record.component,
                "field": record.field,
            },
            measured_outputs={record.field: float(record.value) if record.value is not None else None},
            uncertainty=dict(record.uncertainty),
            validation_quality=vq,
            notes=record.notes,
        )


def transform_raw_to_validation_case(record: RawEvidenceRecord) -> ValidationCase:
    """Pipeline entry: RawEvidenceRecord → ValidationCase."""
    return EvidenceValidator().to_validation_case(record)


def transform_batch(records: list[RawEvidenceRecord]) -> list[ValidationCase]:
    return [transform_raw_to_validation_case(r) for r in records]
