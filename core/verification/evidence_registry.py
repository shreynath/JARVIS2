"""Maturity evidence registry — claims require listed evidence; never auto-upgrade."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.verification.model_maturity import (
    MATURITY_RANK,
    MaturityUpgradeEvidence,
    MaturityValidationError,
    ModelMaturity,
    assert_upgrade_allowed,
    evaluate_upgrade,
    parse_maturity,
)
from core.verification.model_registry import MODEL_REGISTRY


@dataclass(frozen=True)
class EvidenceRequirement:
    """What must be earned to move a model from current → target."""

    model: str
    current: ModelMaturity
    target: ModelMaturity
    requirements: tuple[str, ...]
    rationale: str = ""
    campaign: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "current": self.current.name,
            "target": self.target.name,
            "requirements": list(self.requirements),
            "rationale": self.rationale,
            "campaign": self.campaign,
        }


# Near-term evidence program — grounded in actual registry ranks, not aspirational labels.
EVIDENCE_REQUIREMENTS: tuple[EvidenceRequirement, ...] = (
    EvidenceRequirement(
        model="calc_torque",
        current=ModelMaturity.M2,
        target=ModelMaturity.M3,
        requirements=(
            "external_comparison_exists",
            "error_characterization_exists",
            "failure_analysis_exists",
        ),
        rationale="SI power/RPM identity across high-RPM published engines (Campaign A).",
        campaign="A_high_rpm",
    ),
    EvidenceRequirement(
        model="calc_mean_piston_speed",
        current=ModelMaturity.M2,
        target=ModelMaturity.M3,
        requirements=(
            "external_comparison_exists",
            "error_characterization_exists",
            "failure_analysis_exists",
        ),
        rationale="Independent MPS vs published stroke×RPM (Campaign A).",
        campaign="A_high_rpm",
    ),
    EvidenceRequirement(
        model="calc_piston_acceleration",
        current=ModelMaturity.M2,
        target=ModelMaturity.M3,
        requirements=(
            "external_comparison_exists",
            "error_characterization_exists",
            "failure_analysis_exists",
        ),
        rationale="First-harmonic accel vs kinematic checks on Campaign A engines.",
        campaign="A_high_rpm",
    ),
    EvidenceRequirement(
        model="engine_cycle_model",
        current=ModelMaturity.M2,
        target=ModelMaturity.M3,
        requirements=(
            "external_comparison_exists",
            "error_characterization_exists",
            "failure_analysis_exists",
        ),
        rationale="BMEP band vs published torque/displacement by family (existing bmep_validation).",
        campaign="A_high_rpm",
    ),
    EvidenceRequirement(
        model="geometry_model",
        current=ModelMaturity.M2,
        target=ModelMaturity.M3,
        requirements=(
            "external_comparison_exists",
            "error_characterization_exists",
            "failure_analysis_exists",
        ),
        rationale="Bore/stroke identities vs published geometry.",
        campaign="A_high_rpm",
    ),
    EvidenceRequirement(
        model="reciprocating_mass_model",
        current=ModelMaturity.M2,
        target=ModelMaturity.M3,
        requirements=(
            "external_comparison_exists",
            "error_characterization_exists",
            "failure_analysis_exists",
            "published_piston_mass_dataset",
        ),
        rationale="Needs OEM/piston-mass references (Campaign B).",
        campaign="B_reciprocating",
    ),
    EvidenceRequirement(
        model="connecting_rod_model",
        current=ModelMaturity.M3,
        target=ModelMaturity.M4,
        requirements=(
            "external_validation_cases>=10",
            "mean_error_documented",
            "uncertainty_documented",
            "independent_verifier_exists",
            "absolute_load_benchmark",
            "fatigue_correlation_dataset",
        ),
        rationale="Rod stress M4 withheld without absolute load benches (Campaign B).",
        campaign="B_reciprocating",
    ),
    EvidenceRequirement(
        model="calc_rod_stress_requirement",
        current=ModelMaturity.M3,
        target=ModelMaturity.M4,
        requirements=(
            "external_validation_cases>=10",
            "mean_error_documented",
            "uncertainty_documented",
            "independent_verifier_exists",
            "absolute_load_benchmark",
        ),
        rationale="High impact; still lacks measured stress datasets.",
        campaign="B_reciprocating",
    ),
    EvidenceRequirement(
        model="calc_heat_rejection",
        current=ModelMaturity.M3,
        target=ModelMaturity.M4,
        requirements=(
            "external_validation_cases>=10",
            "mean_error_documented",
            "uncertainty_documented",
            "independent_verifier_exists",
            "dyno_heat_rejection_data",
        ),
        rationale="Energy-split is formula-ok; parameters need dyno evidence (Campaign C).",
        campaign="C_thermal",
    ),
    EvidenceRequirement(
        model="calc_combustion_side_temperature",
        current=ModelMaturity.M3,
        target=ModelMaturity.M4,
        requirements=(
            "external_validation_cases>=10",
            "mean_error_documented",
            "uncertainty_documented",
            "independent_verifier_exists",
            "thermal_measurement_papers",
            "no_unresolved_major_failure_modes",
        ),
        rationale="Empirical map remains UNVALIDATED — do not inflate without measurements.",
        campaign="C_thermal",
    ),
    EvidenceRequirement(
        model="mean_piston_speed_hard_limit",
        current=ModelMaturity.M1,
        target=ModelMaturity.M2,
        requirements=(
            "assumptions_documented",
            "uncertainty_range_documented",
            "references_documented",
        ),
        rationale="Classification gate — strengthen references before calling it analytical.",
        campaign="A_high_rpm",
    ),
    EvidenceRequirement(
        model="eq_oil_flow",
        current=ModelMaturity.M0,
        target=ModelMaturity.M1,
        requirements=("assumptions_documented",),
        rationale="Leave M0 or document first-order pumping assumption; do not fake M3.",
        campaign=None,
    ),
)


def requirements_for(model_id: str) -> EvidenceRequirement | None:
    for req in EVIDENCE_REQUIREMENTS:
        if req.model == model_id:
            return req
    return None


def attempt_upgrade(
    model: str,
    from_maturity: ModelMaturity | str,
    to_maturity: ModelMaturity | str,
    evidence: MaturityUpgradeEvidence | None = None,
) -> dict[str, Any]:
    """Propose a maturity change. Never mutates MODEL_REGISTRY.

    Raises MaturityValidationError when evidence is insufficient or levels are skipped.
    """
    frm = parse_maturity(from_maturity)
    to = parse_maturity(to_maturity)
    packet = evidence if evidence is not None else MaturityUpgradeEvidence()
    before = {
        mid: d.maturity.name for mid, d in MODEL_REGISTRY.items() if mid == model
    }
    result = evaluate_upgrade(from_maturity=frm, to_maturity=to, evidence=packet)
    if not result["allowed"]:
        raise MaturityValidationError(
            f"upgrade({model!r}, {frm.name}, {to.name}) blocked: {result['missing']}"
        )
    assert_upgrade_allowed(from_maturity=frm, to_maturity=to, evidence=packet)
    after = {
        mid: d.maturity.name for mid, d in MODEL_REGISTRY.items() if mid == model
    }
    if before != after:
        raise MaturityValidationError(
            f"Registry mutated during attempt_upgrade({model!r}) — forbidden"
        )
    return {
        "model": model,
        "from": frm.name,
        "to": to.name,
        "allowed": True,
        "applied": False,
        "policy": "Evidence gates may pass; registry upgrades remain explicit and manual.",
        "registry_unchanged": True,
    }


def blocking_evidence_for(model_id: str) -> list[str]:
    """List still-missing evidence for the registered near-term target."""
    desc = MODEL_REGISTRY.get(model_id)
    req = requirements_for(model_id)
    if desc is None:
        return [f"unknown_model:{model_id}"]
    if req is None:
        # Default: next single step, generic missing checklist
        rank = MATURITY_RANK[desc.maturity]
        if rank >= MATURITY_RANK[ModelMaturity.M5]:
            return []
        if desc.maturity is ModelMaturity.M3 and not desc.benchmarked:
            return [
                "external_validation_cases>=10",
                "mean_error_documented",
                "uncertainty_documented",
                "independent_verifier_exists",
                "benchmarked=True",
            ]
        if desc.maturity is ModelMaturity.M2:
            return [
                "external_comparison_exists",
                "error_characterization_exists",
                "failure_analysis_exists",
            ]
        if desc.maturity is ModelMaturity.M1:
            return [
                "assumptions_documented",
                "uncertainty_range_documented",
                "references_documented",
            ]
        if desc.maturity is ModelMaturity.M0:
            return ["assumptions_documented"]
        return ["production_validated", "physical_testing", "field_correlation"]
    # Inventory against required strings — still-blocking until campaigns clear them.
    return list(req.requirements)


def evidence_registry_snapshot() -> dict[str, Any]:
    return {
        "phase": "8.0",
        "policy": "No automatic upgrades. Evidence gates only.",
        "requirements": [r.to_dict() for r in EVIDENCE_REQUIREMENTS],
    }


__all__ = [
    "EVIDENCE_REQUIREMENTS",
    "EvidenceRequirement",
    "attempt_upgrade",
    "blocking_evidence_for",
    "evidence_registry_snapshot",
    "requirements_for",
]
