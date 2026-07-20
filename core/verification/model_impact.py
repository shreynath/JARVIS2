"""Model impact levels — how strongly a model influences downstream outputs."""

from __future__ import annotations

from enum import Enum


class ImpactLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# Numeric weight for scoring / prioritization.
IMPACT_WEIGHT: dict[ImpactLevel, float] = {
    ImpactLevel.LOW: 1.0,
    ImpactLevel.MEDIUM: 2.0,
    ImpactLevel.HIGH: 3.0,
    ImpactLevel.CRITICAL: 4.0,
}


def impact_level_from_str(value: str) -> ImpactLevel:
    text = str(value).strip().upper()
    if text in ImpactLevel.__members__:
        return ImpactLevel[text]
    lower = str(value).strip().lower()
    for member in ImpactLevel:
        if member.value == lower:
            return member
    raise ValueError(f"Unknown impact level: {value!r}")


def impact_str(level: ImpactLevel) -> str:
    return level.name
