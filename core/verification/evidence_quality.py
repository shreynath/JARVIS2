"""Evidence quality scoring — affects reports only, never maturity."""

from __future__ import annotations

from core.verification.evidence_source import SourceType

# Quality weights per directive (0.0–1.0).
QUALITY_BY_SOURCE_TYPE: dict[SourceType, float] = {
    SourceType.OEM_DOCUMENTATION: 1.0,
    SourceType.PEER_REVIEWED_PAPER: 0.9,
    SourceType.TEARDOWN_DATA: 0.85,
    SourceType.ENGINEERING_DATABASE: 0.85,
    SourceType.TECHNICAL_MANUAL: 0.85,
    SourceType.SECONDARY_ESTIMATE: 0.4,
}

QUALITY_BY_MEASUREMENT: dict[str, float] = {
    "direct": 1.0,
    "derived": 0.7,
    "estimate": 0.4,
    "unknown": 0.0,
}


def quality_score(
    *,
    source_type: SourceType | str | None = None,
    measurement_type: str | None = None,
    quality_label: str | None = None,
) -> float:
    """Return 0.0–1.0 quality. Unknown → 0."""
    if quality_label == "unknown" or measurement_type == "unknown":
        return 0.0
    if measurement_type == "synthetic":
        return 0.0
    base = 0.0
    if source_type is not None:
        if isinstance(source_type, str):
            try:
                source_type = SourceType(source_type)
            except ValueError:
                return 0.0
        base = QUALITY_BY_SOURCE_TYPE.get(source_type, 0.0)
    meas = QUALITY_BY_MEASUREMENT.get(str(measurement_type or "").lower(), 0.0)
    if base == 0.0 and meas == 0.0:
        return 0.0
    return min(1.0, max(base, meas))


def is_measurement_grade(score: float) -> bool:
    """Estimates (≤0.4) cannot masquerade as direct measurements in validated cases."""
    return score >= 0.5
