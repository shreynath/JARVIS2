"""EvaluationResult — packaged Phase 1 truth for one candidate."""

from __future__ import annotations

from dataclasses import dataclass, field

from core.epistemology import Evidence
from core.ir.constraint import ConstraintEvaluation
from core.ir.material import MaterialSpec
from core.ir.requirement_spec import RequirementSpecification
from core.reasoning.physics_engine import PhysicsAnalysis


@dataclass
class Completeness:
    """Bookkeeping over existing constraint labels — not a new validity judgment.

    ``evaluation_complete`` and ``passed`` on EvaluationResult are independent.
    """

    evaluation_complete: bool
    evaluated_constraints: int
    unevaluated_hard_limits: int
    unevaluated_component_ids: list[str] = field(default_factory=list)


@dataclass
class EvaluationResult:
    physics: PhysicsAnalysis
    materials: dict[str, MaterialSpec]
    constraints: list[ConstraintEvaluation]
    completeness: Completeness
    evidence: list[Evidence]
    passed: bool
    hard_violations: int
    # Pass-through Phase 1 artifacts for inspectability / parity (no new judgments).
    requirement_spec: RequirementSpecification | None = None
    validation_status: str = ""
