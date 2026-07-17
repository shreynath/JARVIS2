"""Validation report and schema validation."""

from __future__ import annotations

from pydantic import BaseModel, Field

from core.ir.design_graph import EngineeringDesignGraph


class ValidationIssue(BaseModel):
    severity: str
    category: str
    message: str
    node_id: str | None = None


class ValidationReport(BaseModel):
    passed: bool = True
    issues: list[ValidationIssue] = Field(default_factory=list)

    def add_issue(self, severity: str, category: str, message: str, node_id: str | None = None) -> None:
        self.issues.append(
            ValidationIssue(severity=severity, category=category, message=message, node_id=node_id)
        )
        if severity == "critical":
            self.passed = False

    def merge(self, other: ValidationReport) -> None:
        self.issues.extend(other.issues)
        if not other.passed:
            self.passed = False


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
