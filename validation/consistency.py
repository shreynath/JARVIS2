"""Consistency validation — missing refs, orphans, invalid hierarchies."""

from __future__ import annotations

from core.ir.design_graph import EngineeringDesignGraph
from validation.schema_validator import ValidationReport


class ConsistencyChecker:
    """Detect structural inconsistencies in the design graph."""

    def validate(self, graph: EngineeringDesignGraph) -> ValidationReport:
        report = ValidationReport()
        all_ids = graph.all_node_ids()

        for comp in graph.components.values():
            for child_id in comp.children:
                if child_id not in all_ids:
                    report.add_issue(
                        "critical",
                        "consistency",
                        f"Component '{comp.id}' references undefined child '{child_id}'",
                        node_id=comp.id,
                    )

            if comp.parent_id and comp.parent_id not in all_ids:
                report.add_issue(
                    "critical",
                    "consistency",
                    f"Component '{comp.id}' references undefined parent '{comp.parent_id}'",
                    node_id=comp.id,
                )

        for assembly in graph.assemblies.values():
            for member_id in assembly.member_ids:
                if member_id not in all_ids:
                    report.add_issue(
                        "critical",
                        "consistency",
                        f"Assembly '{assembly.id}' references undefined member '{member_id}'",
                        node_id=assembly.id,
                    )

        referenced_as_child: set[str] = set()
        for comp in graph.components.values():
            referenced_as_child.update(comp.children)
        for assembly in graph.assemblies.values():
            referenced_as_child.update(assembly.member_ids)

        for node_id in all_ids:
            if node_id != graph.root_id and node_id not in referenced_as_child:
                if node_id in graph.components and graph.components[node_id].parent_id:
                    continue
                report.add_issue(
                    "warning",
                    "consistency",
                    f"Node '{node_id}' is orphaned (not referenced by any parent)",
                    node_id=node_id,
                )

        self._check_cycles(graph, report)
        return report

    @staticmethod
    def _check_cycles(graph: EngineeringDesignGraph, report: ValidationReport) -> None:
        visited: set[str] = set()
        stack: set[str] = set()

        def dfs(node_id: str) -> bool:
            if node_id in stack:
                report.add_issue("critical", "hierarchy", f"Cycle detected involving '{node_id}'", node_id=node_id)
                return True
            if node_id in visited:
                return False
            visited.add(node_id)
            stack.add(node_id)

            comp = graph.components.get(node_id)
            if comp:
                for child_id in comp.children:
                    dfs(child_id)

            stack.remove(node_id)
            return False

        if graph.root_id:
            dfs(graph.root_id)
