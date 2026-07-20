"""Verification integrity labels — external ground truth vs self-consistency.

Category (a) ``externally_verified``: ground truth is outside the generation
pipeline (datasets, cited formulas, approved raw evidence).

Category (b) ``self_consistency_check``: checks internal coherence of the
design graph / pipeline outputs. Must never be labeled ``validated`` or
``verified`` in user-facing status — those words are reserved for (a).

See ``docs/verification_integrity_report.md``.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class VerificationKind(StrEnum):
    EXTERNALLY_VERIFIED = "externally_verified"
    SELF_CONSISTENCY_CHECK = "self_consistency_check"


class VerificationCheckRecord(BaseModel):
    """Provenance stamp for one validator invocation."""

    validator_id: str
    verification_kind: str
    ground_truth: str
    rejected: bool = False
    critical_issues: int = 0
    warnings: int = 0


# Registry: validator_id → (kind, ground_truth one-liner)
VALIDATOR_REGISTRY: dict[str, tuple[VerificationKind, str]] = {
    "SchemaValidator": (
        VerificationKind.SELF_CONSISTENCY_CHECK,
        "Pydantic IR schema (EngineeringDesignGraph) — no external dataset",
    ),
    "ConsistencyChecker": (
        VerificationKind.SELF_CONSISTENCY_CHECK,
        "Graph topology invariants (refs, orphans, cycles) — no external dataset",
    ),
    "PhysicsRulesEngine": (
        VerificationKind.SELF_CONSISTENCY_CHECK,
        "Design-graph field presence (material assigned) — warning-only; "
        "hard suitability via ConstraintEvaluator",
    ),
    "ConstraintEvaluator": (
        VerificationKind.SELF_CONSISTENCY_CHECK,
        "Pipeline-derived physics calcs + knowledge/material_suitability rules — "
        "not independent external benchmark",
    ),
    "DesignCritic": (
        VerificationKind.SELF_CONSISTENCY_CHECK,
        "Rule checks + optional LLM review of same graph — no external dataset",
    ),
    "EvidenceValidator": (
        VerificationKind.EXTERNALLY_VERIFIED,
        "Raw evidence provenance checklist + quality score threshold",
    ),
    "IndependentCampaignValidator": (
        VerificationKind.EXTERNALLY_VERIFIED,
        "Published engine/rod case fields — must not import PhysicsEngine",
    ),
    "formula_validator": (
        VerificationKind.EXTERNALLY_VERIFIED,
        "Independent recomputation from cited formulas vs physics JSON inputs",
    ),
    "reality_auditor": (
        VerificationKind.EXTERNALLY_VERIFIED,
        "JSON-only audit: formula validation + benchmark cross-checks",
    ),
}


def stamp_validator(
    report,
    validator_id: str,
    *,
    rejected: bool | None = None,
) -> None:
    """Append verification provenance to a ValidationReport."""
    kind, ground_truth = VALIDATOR_REGISTRY.get(
        validator_id,
        (VerificationKind.SELF_CONSISTENCY_CHECK, "Unregistered validator — treat as self-consistency"),
    )
    if rejected is None:
        rejected = report.hard_violations > 0 or not report.passed
    record = VerificationCheckRecord(
        validator_id=validator_id,
        verification_kind=kind.value,
        ground_truth=ground_truth,
        rejected=rejected,
        critical_issues=report.hard_violations,
        warnings=report.warnings,
    )
    if hasattr(report, "verification_checks"):
        report.verification_checks.append(record)


def registry_entry(validator_id: str) -> VerificationCheckRecord:
    """Static metadata for validators that do not emit ValidationReport."""
    kind, ground_truth = VALIDATOR_REGISTRY.get(
        validator_id,
        (VerificationKind.SELF_CONSISTENCY_CHECK, "Unregistered"),
    )
    return VerificationCheckRecord(
        validator_id=validator_id,
        verification_kind=kind.value,
        ground_truth=ground_truth,
    )
