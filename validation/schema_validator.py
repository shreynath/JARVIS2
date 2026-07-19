"""Validation report and schema validation."""

from __future__ import annotations

from pydantic import BaseModel, Field

from core.ir.constraint import ConstraintEvaluation
from core.ir.design_graph import EngineeringDesignGraph


class ValidationIssue(BaseModel):
    severity: str
    category: str
    message: str
    node_id: str | None = None


class ValidationReport(BaseModel):
    passed: bool = True
    status: str = "pass"
    evaluation_complete: bool = True
    hard_violations: int = 0
    warnings: int = 0
    missing_decisions: int = 0
    unverified_assumptions: int = 0
    unvalidated_hard_limits: int = 0
    issues: list[ValidationIssue] = Field(default_factory=list)
    constraint_evaluations: list[ConstraintEvaluation] = Field(default_factory=list)

    def add_issue(self, severity: str, category: str, message: str, node_id: str | None = None) -> None:
        self.issues.append(
            ValidationIssue(severity=severity, category=category, message=message, node_id=node_id)
        )
        if severity == "critical":
            self.hard_violations += 1
            self.passed = False
        elif severity == "warning":
            self.warnings += 1
        if category == "missing_decision":
            self.missing_decisions += 1
        if category == "assumption":
            self.unverified_assumptions += 1
        if category == "unvalidated_hard_limit":
            self.unvalidated_hard_limits += 1
        self._refresh_status()

    def mark_incomplete(self, message: str, node_id: str | None = "root") -> None:
        """Physics/material evaluation did not run — neither pass nor fail is truthful."""
        self.evaluation_complete = False
        self.passed = False
        self.status = "incomplete"
        self.issues.append(
            ValidationIssue(
                severity="warning",
                category="incomplete_evaluation",
                message=message,
                node_id=node_id,
            )
        )
        self.warnings += 1

    def merge(self, other: ValidationReport) -> None:
        self.issues.extend(other.issues)
        self.hard_violations += other.hard_violations
        self.warnings += other.warnings
        self.missing_decisions += other.missing_decisions
        self.unverified_assumptions += other.unverified_assumptions
        self.unvalidated_hard_limits += other.unvalidated_hard_limits
        self.constraint_evaluations.extend(other.constraint_evaluations)
        if not other.evaluation_complete:
            self.evaluation_complete = False
        if not other.passed:
            self.passed = False
        self._refresh_status()

    def _refresh_status(self) -> None:
        if not self.evaluation_complete:
            self.status = "incomplete"
            self.passed = False
            return
        if self.hard_violations:
            self.status = "fail"
            self.passed = False
        elif self.warnings or self.missing_decisions or self.unverified_assumptions:
            self.status = "pass_with_warnings"
            self.passed = True
        else:
            self.status = "pass"
            self.passed = True


class SchemaValidator:
    """Validate graph against Pydantic schemas."""

    def validate(self, graph: EngineeringDesignGraph) -> ValidationReport:
        report = ValidationReport()
        try:
            EngineeringDesignGraph.model_validate(graph.model_dump())
        except Exception as exc:
            report.add_issue("critical", "schema", f"Graph schema validation failed: {exc}")

        if not graph.root_id:
            report.add_issue("critical", "schema", "Graph missing root_id")
        elif graph.root_id not in graph.all_node_ids():
            report.add_issue("critical", "schema", f"root_id '{graph.root_id}' not found in graph")

        if not graph.components:
            report.add_issue("critical", "schema", "Graph has no components")

        return report
