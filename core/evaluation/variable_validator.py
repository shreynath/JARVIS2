"""Validate CandidateDesign.variables against requirement claims (Phase 3.0).

Enforcement lives here / EngineeringEvaluator — not on CandidateDesign, search,
or mutation layers. CandidateDesign stays intentionally dumb; the evaluator is
the firewall that decides whether a proposed variable patch is meaningful.

Invariant:
    A key is an OPTIMIZATION_KNOB only when it is an independent input for this
    study (default knob or declared_knobs). Values that were assumed, estimated,
    derived, or out of model may never be written via candidate.variables.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from core.candidates.parameter_roles import (
    ASSUMPTION_INTERNAL_KEYS,
    DEFAULT_FIXED_REQUIREMENTS,
    DEFAULT_OPTIMIZATION_KNOBS,
    DERIVED_OUTPUT_KEYS,
    OUT_OF_MODEL_KEYS,
    PHYSICS_ESTIMATED_WHEN_ABSENT,
    ParameterClaim,
    ParameterProvenance,
    ParameterRole,
)
from core.ir.requirement_spec import RequirementSpecification


class VariableValidationResult(BaseModel):
    valid: bool
    illegal_variables: list[str] = Field(default_factory=list)
    claims: list[ParameterClaim] = Field(default_factory=list)
    reasons: dict[str, str] = Field(default_factory=dict)


class IllegalCandidateVariablesError(ValueError):
    """Raised when EngineeringEvaluator rejects illegal candidate.variables."""

    def __init__(self, result: VariableValidationResult) -> None:
        self.result = result
        illegal = ", ".join(result.illegal_variables) or "(none)"
        detail = "; ".join(f"{k}: {v}" for k, v in result.reasons.items()) or illegal
        super().__init__(f"Illegal candidate variables: {detail}")


def classify_parameter(
    name: str,
    requirement_spec: RequirementSpecification,
    declared_knobs: list[str] | set[str] | frozenset[str] | None = None,
    proposed_value: float | int | str | None = None,
) -> ParameterClaim:
    """Assign role + provenance for a parameter key in the context of a study."""
    declared = set(declared_knobs or ())
    in_resolved = name in requirement_spec.resolved_parameters
    resolved_value = requirement_spec.resolved_parameters.get(name, proposed_value)

    if name in declared or name in DEFAULT_OPTIMIZATION_KNOBS:
        provenance = ParameterProvenance.KNOWN if in_resolved else ParameterProvenance.UNSPECIFIED
        return ParameterClaim(
            name=name,
            value=resolved_value if in_resolved else proposed_value,
            role=ParameterRole.OPTIMIZATION_KNOB,
            provenance=provenance,
            reason="Independent optimization input for this study",
        )

    if name in DERIVED_OUTPUT_KEYS:
        return ParameterClaim(
            name=name,
            value=proposed_value,
            role=ParameterRole.DERIVED_OUTPUT,
            provenance=ParameterProvenance.DERIVED,
            reason="Derived engineering outcome — not proposable via candidate.variables",
        )

    if name in ASSUMPTION_INTERNAL_KEYS:
        return ParameterClaim(
            name=name,
            value=proposed_value,
            role=ParameterRole.ASSUMPTION_INTERNAL,
            provenance=ParameterProvenance.ASSUMED,
            reason="Internal estimation lever — owned by physics/assumption layer",
        )

    if name in OUT_OF_MODEL_KEYS:
        return ParameterClaim(
            name=name,
            value=proposed_value,
            role=ParameterRole.OUT_OF_MODEL,
            provenance=ParameterProvenance.UNSPECIFIED,
            reason="No Phase 1 consumer for this parameter",
        )

    # Dual-role: displacement_l (and similar) — claim state drives mutability.
    if name in PHYSICS_ESTIMATED_WHEN_ABSENT and not in_resolved:
        return ParameterClaim(
            name=name,
            value=proposed_value,
            role=ParameterRole.ASSUMPTION_INTERNAL,
            provenance=ParameterProvenance.ASSUMED,
            reason=(
                f"{name} is not an independent input in this specification; "
                "physics will estimate it — cannot be proposed as a variable"
            ),
        )

    if name in DEFAULT_FIXED_REQUIREMENTS or in_resolved:
        return ParameterClaim(
            name=name,
            value=resolved_value if in_resolved else proposed_value,
            role=ParameterRole.FIXED_REQUIREMENT,
            provenance=ParameterProvenance.KNOWN if in_resolved else ParameterProvenance.UNSPECIFIED,
            reason=(
                f"{name} is a fixed requirement for this study; "
                "list it in declared_knobs to elevate to an optimization knob"
            ),
        )

    return ParameterClaim(
        name=name,
        value=proposed_value,
        role=ParameterRole.OUT_OF_MODEL,
        provenance=ParameterProvenance.UNSPECIFIED,
        reason=f"Unrecognized parameter '{name}' — no semantic role registered",
    )


def validate_candidate_variables(
    variables: dict[str, float],
    requirement_spec: RequirementSpecification,
    declared_knobs: list[str] | set[str] | frozenset[str] | None = None,
) -> VariableValidationResult:
    """Return whether every proposed variable is a legal OPTIMIZATION_KNOB."""
    if not variables:
        return VariableValidationResult(valid=True)

    claims: list[ParameterClaim] = []
    illegal: list[str] = []
    reasons: dict[str, str] = {}

    for name, value in variables.items():
        claim = classify_parameter(
            name,
            requirement_spec,
            declared_knobs=declared_knobs,
            proposed_value=value,
        )
        claims.append(claim)
        if claim.role != ParameterRole.OPTIMIZATION_KNOB:
            illegal.append(name)
            reasons[name] = f"{claim.role.value}: {claim.reason}"

    return VariableValidationResult(
        valid=not illegal,
        illegal_variables=illegal,
        claims=claims,
        reasons=reasons,
    )
