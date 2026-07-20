"""Adversarial rejection tests — EvidenceValidator (≥3 broken fixtures)."""

import pytest

from core.verification.evidence_pipeline import EvidenceValidationError, EvidenceValidator
from core.verification.evidence_source import SourceType
from core.verification.raw_evidence import RawEvidenceRecord
from validation.integrity import VerificationKind


def _record(**overrides) -> RawEvidenceRecord:
    base = dict(
        id="adv_rec",
        component="connecting_rod",
        field="piston_mass_g",
        value=450.0,
        unit="g",
        source_id="src_test",
        source_title="Test source",
        measurement_type="direct",
        quality="high",
        provenance={"source_type": SourceType.OEM_DOCUMENTATION.value},
        uncertainty={"relative": 0.02},
    )
    base.update(overrides)
    return RawEvidenceRecord(**base)


def test_rejects_missing_unit():
    with pytest.raises(EvidenceValidationError, match="unit"):
        EvidenceValidator().validate_raw(_record(unit=""))


def test_rejects_synthetic_measurement_type():
    with pytest.raises(EvidenceValidationError, match="synthetic"):
        EvidenceValidator().validate_raw(_record(measurement_type="synthetic"))


def test_rejects_secondary_estimate_masquerading_as_measurement():
    with pytest.raises(EvidenceValidationError, match="SECONDARY_ESTIMATE|quality"):
        EvidenceValidator().validate_raw(
            _record(
                measurement_type="estimate",
                quality="high",
                provenance={"source_type": SourceType.SECONDARY_ESTIMATE.value},
            )
        )


def test_rejects_missing_provenance():
    with pytest.raises(EvidenceValidationError):
        EvidenceValidator().validate_raw(_record(provenance={}))


def test_accepts_valid_measurement_grade_record():
    checklist = EvidenceValidator().validate_raw(_record())
    assert checklist["unit_present"] is True
    meta = EvidenceValidator.verification_metadata()
    assert meta.verification_kind == VerificationKind.EXTERNALLY_VERIFIED.value
