"""
CandidateDesign — a proposed design state, not evaluated truth.

Allowed as authoritative data on this class:
    - prompt (natural-language design intent)
    - variables (structured design-parameter proposals; semantics enforced by
      EngineeringEvaluator via the Phase 3.0 role registry — not by this class)
    - declared_knobs (study-scoped elevation of FIXED_REQUIREMENT keys to
      OPTIMIZATION_KNOB; empty means only default knobs such as max_rpm)
    - constraints (user-supplied limits)
    - status (candidate lifecycle marker)

Forbidden as authoritative data on this class — these live on
EvaluationResult and must never be duplicated here, cached here, or
written back onto a candidate by anything that evaluates it:
    - physics results
    - materials
    - validation state / pass-fail outcomes
    - constraint evaluation outcomes
    - scores
    - evidence
    - design_graph / requirement_spec (Phase 1 pipeline outputs)

EngineeringEvaluator owns generation of all derived engineering
information and returns it via EvaluationResult. It does not write
conclusions back onto the CandidateDesign it was given.
"""

from __future__ import annotations

from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, Field


class CandidateStatus(StrEnum):
    PROPOSED = "proposed"
    EVALUATED = "evaluated"
    REJECTED = "rejected"


class CandidateDesign(BaseModel):
    """A design proposal. Represents a *proposed* design state — never
    evaluated engineering truth. See module docstring for the allowed/
    forbidden field split; this class must not grow fields that duplicate
    anything EvaluationResult already owns.
    """

    id: str = Field(default_factory=lambda: f"candidate_{uuid4().hex[:12]}")
    prompt: str = ""
    variables: dict[str, float] = Field(default_factory=dict)
    declared_knobs: list[str] = Field(default_factory=list)
    constraints: dict[str, str | float | int] = Field(default_factory=dict)
    status: CandidateStatus = CandidateStatus.PROPOSED

    @classmethod
    def from_prompt(cls, prompt: str) -> CandidateDesign:
        return cls(prompt=prompt.strip(), status=CandidateStatus.PROPOSED)
