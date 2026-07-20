"""Model maturity scale — sophistication of the engineering model itself.

Distinct from confidence (epistemic strength of a run) and validation_status
(evidence class). Maturity answers: how sophisticated is this model?
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

from core.verification.model_impact import ImpactLevel, impact_level_from_str, impact_str


class ModelMaturity(Enum):
    """Engineering-model sophistication ladder (M0–M5)."""

    M0 = "placeholder"
    M1 = "heuristic"
    M2 = "analytical"
    M3 = "semi_empirical"
    M4 = "validated"
    M5 = "industry_grade"


# Numeric rank for deficit / averaging (M0=0 … M5=5).
MATURITY_RANK: dict[ModelMaturity, int] = {
    ModelMaturity.M0: 0,
    ModelMaturity.M1: 1,
    ModelMaturity.M2: 2,
    ModelMaturity.M3: 3,
    ModelMaturity.M4: 4,
    ModelMaturity.M5: 5,
}


class MaturityValidationError(ValueError):
    """Raised when a maturity claim is inconsistent with evidence flags."""


@dataclass(frozen=True)
class ModelDescriptor:
    """Registered engineering-model metadata (no equations, no scores)."""

    id: str
    maturity: ModelMaturity
    owner: str
    equation_id: str | None = None
    engineering_reference: str | None = None
    validation_status: str | None = None
    benchmarked: bool = False
    independently_verified: bool = False
    production_validated: bool = False
    known_limitations: str | None = None
    # Legacy string impact (HIGH|MEDIUM|LOW|CRITICAL) — kept for Phase 4.5 reports.
    impact: str = "MEDIUM"
    subsystem: str = "physics"
    # Phase 5.0 impact framework
    impact_level: ImpactLevel = ImpactLevel.MEDIUM
    affected_outputs: tuple[str, ...] = field(default_factory=tuple)
    sensitivity_rank: int = 50  # 1 = most sensitive / highest influence
    upgrade_priority: str = "MEDIUM"  # VERY_HIGH | HIGH | MEDIUM | LOW

    def to_dict(self) -> dict[str, Any]:
        raw = asdict(self)
        raw["maturity"] = self.maturity.name
        raw["maturity_label"] = self.maturity.value
        raw["maturity_rank"] = MATURITY_RANK[self.maturity]
        raw["impact_level"] = self.impact_level.name
        raw["impact_level_label"] = self.impact_level.value
        raw["affected_outputs"] = list(self.affected_outputs)
        return raw


def validate_descriptor(descriptor: ModelDescriptor) -> None:
    """Reject impossible maturity / evidence combinations (anti-inflation)."""
    m = descriptor.maturity

    if m == ModelMaturity.M5:
        if not descriptor.benchmarked:
            raise MaturityValidationError(
                f"{descriptor.id}: M5 requires benchmarked=True"
            )
        if not descriptor.independently_verified:
            raise MaturityValidationError(
                f"{descriptor.id}: M5 requires independently_verified=True"
            )
        if not descriptor.production_validated:
            raise MaturityValidationError(
                f"{descriptor.id}: M5 requires production_validated=True"
            )

    if m == ModelMaturity.M4:
        if not descriptor.independently_verified:
            raise MaturityValidationError(
                f"{descriptor.id}: M4 requires independently_verified=True"
            )
        if not descriptor.benchmarked:
            raise MaturityValidationError(
                f"{descriptor.id}: M4 requires benchmarked=True (benchmark evidence)"
            )

    if descriptor.impact not in {"HIGH", "MEDIUM", "LOW", "CRITICAL"}:
        raise MaturityValidationError(
            f"{descriptor.id}: impact must be HIGH|MEDIUM|LOW|CRITICAL, got {descriptor.impact!r}"
        )

    try:
        level_from_impact = impact_level_from_str(descriptor.impact)
    except ValueError as exc:
        raise MaturityValidationError(str(exc)) from exc
    if level_from_impact is not descriptor.impact_level:
        raise MaturityValidationError(
            f"{descriptor.id}: impact={descriptor.impact!r} inconsistent with "
            f"impact_level={descriptor.impact_level.name}"
        )

    if descriptor.upgrade_priority not in {"VERY_HIGH", "HIGH", "MEDIUM", "LOW"}:
        raise MaturityValidationError(
            f"{descriptor.id}: upgrade_priority must be VERY_HIGH|HIGH|MEDIUM|LOW"
        )


# ---------------------------------------------------------------------------
# Phase 6.0 — upgrade evidence gates (external calibration required)
# ---------------------------------------------------------------------------

M4_MIN_EXTERNAL_CASES = 10


@dataclass(frozen=True)
class MaturityUpgradeEvidence:
    """Evidence packet required to raise maturity. Empty fields fail closed."""

    external_validation_cases: int = 0
    mean_error_documented: bool = False
    uncertainty_documented: bool = False
    independent_verifier_exists: bool = False
    unresolved_major_failure_modes: tuple[str, ...] = ()
    production_validated: bool = False
    physical_testing: bool = False
    field_correlation: bool = False
    # Phase 8.0 — intermediate ladder evidence (M0→M3)
    assumptions_documented: bool = False
    uncertainty_range_documented: bool = False
    references_documented: bool = False
    external_comparison_exists: bool = False
    error_characterization_exists: bool = False
    failure_analysis_exists: bool = False


def evaluate_m0_to_m1_upgrade(evidence: MaturityUpgradeEvidence) -> dict[str, Any]:
    """M0→M1: concept becomes an explicit assumption model."""
    missing: list[str] = []
    if not evidence.assumptions_documented:
        missing.append("assumptions_documented")
    return {
        "from": "M0",
        "to": "M1",
        "allowed": len(missing) == 0,
        "missing": missing,
        "policy": "Placeholders need documented assumptions before heuristic status.",
    }


def evaluate_m1_to_m2_upgrade(evidence: MaturityUpgradeEvidence) -> dict[str, Any]:
    """M1→M2: documented assumptions + uncertainty + references."""
    missing: list[str] = []
    if not evidence.assumptions_documented:
        missing.append("assumptions_documented")
    if not evidence.uncertainty_range_documented:
        missing.append("uncertainty_range_documented")
    if not evidence.references_documented:
        missing.append("references_documented")
    return {
        "from": "M1",
        "to": "M2",
        "allowed": len(missing) == 0,
        "missing": missing,
        "policy": "Assumption models need ranges and references to become transparent engineering models.",
    }


def evaluate_m2_to_m3_upgrade(evidence: MaturityUpgradeEvidence) -> dict[str, Any]:
    """M2→M3: external comparison + error characterization + failure analysis."""
    missing: list[str] = []
    if not evidence.external_comparison_exists:
        missing.append("external_comparison_exists")
    if not evidence.error_characterization_exists:
        missing.append("error_characterization_exists")
    if not evidence.failure_analysis_exists:
        missing.append("failure_analysis_exists")
    return {
        "from": "M2",
        "to": "M3",
        "allowed": len(missing) == 0,
        "missing": missing,
        "policy": "Transparent models need external comparison before semi-empirical status.",
    }


def evaluate_m3_to_m4_upgrade(evidence: MaturityUpgradeEvidence) -> dict[str, Any]:
    """M3→M4 requires ALL listed evidence. No exceptions."""
    missing: list[str] = []
    if evidence.external_validation_cases < M4_MIN_EXTERNAL_CASES:
        missing.append(
            f"external_validation_cases>={M4_MIN_EXTERNAL_CASES} "
            f"(have {evidence.external_validation_cases})"
        )
    if not evidence.mean_error_documented:
        missing.append("mean_error_documented")
    if not evidence.uncertainty_documented:
        missing.append("uncertainty_documented")
    if not evidence.independent_verifier_exists:
        missing.append("independent_verifier_exists")
    if evidence.unresolved_major_failure_modes:
        missing.append(
            "no_unresolved_major_failure_modes "
            f"(have {list(evidence.unresolved_major_failure_modes)})"
        )
    return {
        "from": "M3",
        "to": "M4",
        "allowed": len(missing) == 0,
        "missing": missing,
        "policy": "No subjective confidence upgrades. No self-validation.",
    }


def evaluate_m4_to_m5_upgrade(evidence: MaturityUpgradeEvidence) -> dict[str, Any]:
    """M4→M5 requires production validation + physical testing + field correlation."""
    missing: list[str] = []
    if not evidence.production_validated:
        missing.append("production_validated")
    if not evidence.physical_testing:
        missing.append("physical_testing")
    if not evidence.field_correlation:
        missing.append("field_correlation")
    return {
        "from": "M4",
        "to": "M5",
        "allowed": len(missing) == 0,
        "missing": missing,
        "policy": "No exceptions.",
    }


_STEP_EVALUATORS = {
    (ModelMaturity.M0, ModelMaturity.M1): evaluate_m0_to_m1_upgrade,
    (ModelMaturity.M1, ModelMaturity.M2): evaluate_m1_to_m2_upgrade,
    (ModelMaturity.M2, ModelMaturity.M3): evaluate_m2_to_m3_upgrade,
    (ModelMaturity.M3, ModelMaturity.M4): evaluate_m3_to_m4_upgrade,
    (ModelMaturity.M4, ModelMaturity.M5): evaluate_m4_to_m5_upgrade,
}


def evaluate_upgrade(
    *,
    from_maturity: ModelMaturity,
    to_maturity: ModelMaturity,
    evidence: MaturityUpgradeEvidence,
) -> dict[str, Any]:
    """Evaluate a one-step maturity transition. Multi-step returns blocked."""
    gap = MATURITY_RANK[to_maturity] - MATURITY_RANK[from_maturity]
    if gap <= 0:
        return {
            "from": from_maturity.name,
            "to": to_maturity.name,
            "allowed": True,
            "missing": [],
            "policy": "Same or lower maturity — no evidence required.",
        }
    if gap > 1:
        return {
            "from": from_maturity.name,
            "to": to_maturity.name,
            "allowed": False,
            "missing": [
                f"cannot_skip_maturity_levels (gap={gap}; advance one step at a time)"
            ],
            "policy": "Complexity is not maturity. No multi-step leaps.",
        }
    evaluator = _STEP_EVALUATORS.get((from_maturity, to_maturity))
    if evaluator is None:
        return {
            "from": from_maturity.name,
            "to": to_maturity.name,
            "allowed": False,
            "missing": ["unsupported_transition"],
            "policy": "Unknown transition.",
        }
    return evaluator(evidence)


def assert_upgrade_allowed(
    *,
    from_maturity: ModelMaturity,
    to_maturity: ModelMaturity,
    evidence: MaturityUpgradeEvidence,
) -> None:
    """Raise MaturityValidationError when upgrade evidence is insufficient."""
    result = evaluate_upgrade(
        from_maturity=from_maturity,
        to_maturity=to_maturity,
        evidence=evidence,
    )
    if not result["allowed"]:
        raise MaturityValidationError(
            f"{from_maturity.name}→{to_maturity.name} blocked; "
            f"missing evidence: {result['missing']}"
        )


def parse_maturity(value: Any) -> ModelMaturity:
    """Accept ModelMaturity, 'M2', or 'analytical'."""
    if isinstance(value, ModelMaturity):
        return value
    text = str(value).strip()
    if text in ModelMaturity.__members__:
        return ModelMaturity[text]
    for member in ModelMaturity:
        if member.value == text:
            return member
    raise ValueError(f"Unknown maturity: {value!r}")


def make_descriptor(
    *,
    id: str,
    maturity: ModelMaturity,
    owner: str,
    impact_level: ImpactLevel = ImpactLevel.MEDIUM,
    affected_outputs: tuple[str, ...] = (),
    sensitivity_rank: int = 50,
    upgrade_priority: str | None = None,
    **kwargs: Any,
) -> ModelDescriptor:
    """Construct a descriptor with impact string synced to impact_level."""
    impact = kwargs.pop("impact", None) or impact_str(impact_level)
    priority = upgrade_priority or (
        "VERY_HIGH"
        if impact_level is ImpactLevel.CRITICAL
        else impact_str(impact_level)
    )
    return ModelDescriptor(
        id=id,
        maturity=maturity,
        owner=owner,
        impact=impact,
        impact_level=impact_level,
        affected_outputs=affected_outputs,
        sensitivity_rank=sensitivity_rank,
        upgrade_priority=priority,
        **kwargs,
    )
