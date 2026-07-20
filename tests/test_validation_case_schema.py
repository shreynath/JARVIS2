"""Phase 6 — ValidationCase schema and source helpers."""

from __future__ import annotations

import pytest

from core.verification.datasets.schemas import ValidationSchemaError, validate_case_dict
from core.verification.datasets.sources import manufacturer_source, paper_source
from core.verification.datasets.validation_case import (
    SystemType,
    ValidationCase,
    ValidationQuality,
)
from core.verification.datasets.registry import VALIDATION_CASE_REGISTRY, cases_for_system


def test_validate_case_dict_rejects_missing_keys():
    with pytest.raises(ValidationSchemaError):
        validate_case_dict({"id": "x"})


def test_validate_case_dict_rejects_invented_non_numeric_measurement():
    with pytest.raises(ValidationSchemaError):
        validate_case_dict(
            {
                "id": "x",
                "system_type": "engine",
                "reference_source": manufacturer_source(name="X"),
                "inputs": {},
                "measured_outputs": {"stroke_mm": "about eighty"},
                "validation_quality": "manufacturer",
            }
        )


def test_validation_case_round_trip():
    case = ValidationCase(
        id="rt",
        system_type=SystemType.ENGINE,
        reference_source=paper_source(title="T"),
        inputs={"horsepower": 100.0},
        measured_outputs={"stroke_mm": 80.0, "compression_ratio": None},
        validation_quality=ValidationQuality.LITERATURE,
    )
    restored = ValidationCase.from_dict(case.to_dict())
    assert restored.id == "rt"
    assert restored.measured("compression_ratio") is None
    assert restored.measured("stroke_mm") == 80.0


def test_registry_only_engine_system_type_today():
    assert cases_for_system(SystemType.ENGINE)
    assert cases_for_system("structure") == []
    assert len(VALIDATION_CASE_REGISTRY) >= 20


def test_manufacturer_source_kind():
    src = manufacturer_source(name="Honda", year=1999)
    assert src["kind"] == "manufacturer"
    assert src["year"] == 1999
