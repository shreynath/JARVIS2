"""Constraint generator — build constraint graph from requirement specification."""

from __future__ import annotations

from core.ir.constraint import Constraint, ConstraintSeverity
from core.ir.constraint_graph import ConstraintGraph, GraphEdgeType, GraphNodeType, ConstraintGraphNode
from core.ir.design_graph import EngineeringDesignGraph
from core.ir.functional import FunctionalAnalysis
from core.ir.requirement_spec import CompiledRequirement, RequirementSpecification
from core.reasoning.physics_engine import PhysicsAnalysis


class ConstraintGenerator:
    """Generate constraints from compiled requirements — never invent arbitrary defaults."""

    _METRIC_TO_CONSTRAINT: dict[str, dict] = {
        "max_rpm": {"type": "max_rpm", "severity": ConstraintSeverity.HARD_LIMIT},
        "mass": {"type": "mass", "severity": ConstraintSeverity.GOAL, "goal": "minimize"},
        "horsepower": {"type": "power_output", "severity": ConstraintSeverity.GOAL, "goal": "maximize"},
        "specific_power": {"type": "specific_power", "severity": ConstraintSeverity.GOAL, "goal": "maximize"},
        "displacement": {"type": "displacement", "severity": ConstraintSeverity.HARD_LIMIT},
    }

    def build_graph(self, requirement_spec: RequirementSpecification) -> ConstraintGraph:
        graph = ConstraintGraph()
        graph.add_node(
            ConstraintGraphNode(
                id="root",
                node_type=GraphNodeType.ASSEMBLY,
                label="Root assembly",
                data={"source": "constraint_generator"},
            )
        )

        for req in requirement_spec.requirements:
            graph.add_requirement(req)

        edge_id = 0
        for req in requirement_spec.requirements:
            if req.metric and req.target_value is not None:
                edge_id += 1
                constraint = self._requirement_to_constraint(req, edge_id)
                graph.add_constraint(constraint, applies_to="root")
                graph.add_edge(
                    f"edge_req_{req.id}_traces_{constraint.id}",
                    req.id,
                    constraint.id,
                    GraphEdgeType.TRACES_TO,
                    description=f"Requirement {req.id} generates constraint {constraint.id}",
                )

        return graph

    def add_design_nodes(self, graph: ConstraintGraph, design_graph: EngineeringDesignGraph) -> None:
        for assembly in design_graph.assemblies.values():
            graph.add_node(
                ConstraintGraphNode(
                    id=assembly.id,
                    node_type=GraphNodeType.ASSEMBLY,
                    label=assembly.name,
                    data={"function": assembly.function},
                )
            )
        for component in design_graph.components.values():
            graph.add_node(
                ConstraintGraphNode(
                    id=component.id,
                    node_type=GraphNodeType.COMPONENT,
                    label=component.name,
                    data={"function": component.function, "parent_assembly_id": component.parent_assembly_id},
                )
            )

    def add_physics_analysis(
        self,
        graph: ConstraintGraph,
        physics_analysis: PhysicsAnalysis,
        requirement_spec: RequirementSpecification,
    ) -> None:
        source_req = self._best_requirement_for_physics(requirement_spec)
        for calculation in physics_analysis.calculations:
            constraint = Constraint(
                id=f"constraint_{calculation.id}",
                type=calculation.name.lower().replace(" ", "_"),
                description=calculation.assessment or calculation.name,
                value=calculation.result,
                unit=calculation.unit,
                severity=ConstraintSeverity.SOFT_LIMIT if calculation.passes is not False else ConstraintSeverity.HARD_LIMIT,
                source="physics_engine",
            )
            graph.add_constraint(constraint, applies_to="root")
            # Emit one traces_to edge per declared dependency (not just dependency_ids[-1]).
            emitted_any = False
            for upstream in calculation.dependency_ids:
                calc_node = f"constraint_{upstream}"
                if calc_node not in graph.nodes:
                    continue
                graph.add_edge(
                    f"edge_{calc_node}_{constraint.id}",
                    calc_node,
                    constraint.id,
                    GraphEdgeType.TRACES_TO,
                    description=(
                        f"{constraint.id} traces to {upstream} "
                        f"(result={calculation.result} {calculation.unit})"
                    ),
                )
                emitted_any = True
            if not emitted_any and source_req:
                graph.add_edge(
                    f"edge_{source_req}_{constraint.id}",
                    source_req,
                    constraint.id,
                    GraphEdgeType.TRACES_TO,
                    description=(
                        f"{constraint.id} traces to calculation {calculation.id} "
                        f"(result={calculation.result} {calculation.unit}), "
                        f"derived downstream of {source_req}"
                    ),
                )

        for constraint in physics_analysis.constraints:
            graph.add_constraint(constraint, applies_to=constraint.component_id or "root")
            calc_id = self._physics_constraint_source_calc(constraint.id)
            calc_node = f"constraint_{calc_id}" if calc_id else None
            calc = physics_analysis.by_id(calc_id) if calc_id else None
            if calc_node and calc_node in graph.nodes and calc is not None:
                value_text = (
                    f"result={calc.result} {calc.unit}"
                    if calc.result is not None
                    else f"range={calc.value_range}"
                )
                if calc.value_range is not None:
                    value_text = f"upper_bound={max(calc.value_range):g} {calc.unit}"
                graph.add_edge(
                    f"edge_{calc_node}_{constraint.id}",
                    calc_node,
                    constraint.id,
                    GraphEdgeType.TRACES_TO,
                    description=(
                        f"{constraint.id} traces to {calc_id} ({value_text}) "
                        f"applied to {constraint.component_id or 'root'}"
                    ),
                )
            elif source_req:
                graph.add_edge(
                    f"edge_{source_req}_{constraint.id}",
                    source_req,
                    constraint.id,
                    GraphEdgeType.TRACES_TO,
                    description=f"Physics constraint {constraint.id} derived downstream of {source_req}",
                )

    def apply_to_graph(
        self,
        design_graph: EngineeringDesignGraph,
        requirement_spec: RequirementSpecification,
        constraint_graph: ConstraintGraph,
        functional_analysis: FunctionalAnalysis | None = None,
        physics_analysis: PhysicsAnalysis | None = None,
    ) -> EngineeringDesignGraph:
        design_graph.metadata["requirement_spec_status"] = requirement_spec.status.value
        req_nodes = requirement_spec.to_requirement_nodes()
        for assembly in design_graph.assemblies.values():
            assembly.requirements = list(req_nodes)

        for node in constraint_graph.nodes.values():
            if node.node_type == GraphNodeType.CONSTRAINT:
                constraint = Constraint(
                    id=node.id,
                    type=str(node.data.get("type", "unknown")),
                    description=node.label,
                    value=node.data.get("value"),
                    unit=node.data.get("unit"),
                    severity=ConstraintSeverity(node.data.get("severity", "hard_limit")),
                    source=str(node.data.get("source", "requirement_compiler")),
                )
                if design_graph.root_id in design_graph.assemblies:
                    target_ids = [
                        e.target_id
                        for e in constraint_graph.edges
                        if e.source_id == node.id and e.edge_type == GraphEdgeType.CONSTRAINT_APPLIES_TO
                    ]
                    applied = False
                    for target_id in target_ids:
                        if target_id in design_graph.components:
                            constraint.component_id = target_id
                            design_graph.components[target_id].constraints.append(constraint)
                            applied = True
                        elif target_id in design_graph.assemblies:
                            design_graph.assemblies[target_id].constraints.append(constraint)
                            applied = True
                    if not applied:
                        design_graph.assemblies[design_graph.root_id].constraints.append(constraint)

        if functional_analysis:
            self._add_thermal_constraints(
                design_graph,
                functional_analysis,
                constraint_graph,
                requirement_spec,
                physics_analysis,
            )

        design_graph.metadata["constraint_count"] = len(
            [n for n in constraint_graph.nodes.values() if n.node_type == GraphNodeType.CONSTRAINT]
        )
        return design_graph

    def _requirement_to_constraint(self, req: CompiledRequirement, constraint_id: int) -> Constraint:
        mapping = self._METRIC_TO_CONSTRAINT.get(req.metric or "", {})
        return Constraint(
            id=f"constraint_{constraint_id}",
            type=mapping.get("type", req.metric or req.id),
            description=req.description,
            value=req.target_value,
            unit=req.unit,
            severity=mapping.get("severity", ConstraintSeverity.HARD_LIMIT),
            goal=mapping.get("goal"),
            source=req.source,
        )

    def _add_thermal_constraints(
        self,
        graph: EngineeringDesignGraph,
        functional_analysis: FunctionalAnalysis,
        constraint_graph: ConstraintGraph,
        requirement_spec: RequirementSpecification,
        physics_analysis: PhysicsAnalysis | None = None,
    ) -> None:
        thermal_functions = {
            f.id for f in functional_analysis.functions if "thermal" in f.name.lower()
        }
        if not thermal_functions:
            return

        start_id = int(graph.metadata.get("constraint_count", 0))
        source_req = self._best_requirement_for_physics(requirement_spec)
        for comp in graph.components.values():
            if comp.material_spec and comp.material_spec.temperature_limit_c:
                start_id += 1
                constraint = Constraint(
                    id=f"constraint_thermal_{start_id}",
                    type="maximum_temperature",
                    description=f"{comp.name} material temperature limit",
                    component_id=comp.id,
                    value=comp.material_spec.temperature_limit_c,
                    unit="C",
                    severity=ConstraintSeverity.HARD_LIMIT,
                    source="material_spec",
                )
                comp.constraints.append(constraint)
                constraint_graph.add_constraint(constraint, applies_to=comp.id)
                trace_source, trace_description = self._thermal_trace_for_component(
                    comp.id,
                    comp.name,
                    comp.function,
                    constraint,
                    constraint_graph,
                    source_req,
                    physics_analysis,
                )
                if trace_source:
                    constraint_graph.add_edge(
                        f"edge_{trace_source}_{constraint.id}",
                        trace_source,
                        constraint.id,
                        GraphEdgeType.TRACES_TO,
                        description=trace_description,
                    )

    @staticmethod
    def _thermal_trace_for_component(
        component_id: str,
        name: str,
        function: str,
        constraint: Constraint,
        constraint_graph: ConstraintGraph,
        fallback_requirement_id: str | None,
        physics_analysis: PhysicsAnalysis | None,
    ) -> tuple[str | None, str]:
        text = f"{component_id} {name} {function}".lower()
        available_nodes = constraint_graph.nodes

        def source_or_fallback(preferred: str) -> str | None:
            return preferred if preferred in available_nodes else fallback_requirement_id

        limit = (
            f"{constraint.value:g} {constraint.unit}"
            if isinstance(constraint.value, (int, float)) and constraint.unit
            else "the material temperature limit"
        )

        # Camshaft is valvetrain/mechanical — match by id/name BEFORE generic "valve"
        # (function text often contains "valve timing" and would mis-route to combustion).
        if component_id == "camshaft" or "camshaft" in name.lower():
            source = source_or_fallback("constraint_calc_piston_acceleration")
            acceleration = (
                physics_analysis.resolve_operating("peak_piston_acceleration_m_s2") if physics_analysis else None
            )
            accel_text = (
                f" driven by estimated {float(acceleration):g} m/s^2 reciprocating/valvetrain mechanical load"
                if isinstance(acceleration, (int, float))
                else " from valvetrain/mechanical friction loading"
            )
            return (
                source,
                f"{name} thermal limit of {limit} traces to friction/mechanical-load heating{accel_text}.",
            )

        if "radiator" in text or "water pump" in text or "thermostat" in text or (
            "cooling" in text and "oil" not in text and "piston" not in text
        ):
            source = source_or_fallback("constraint_calc_heat_rejection")
            heat_kw = physics_analysis.resolve_operating("cooling_heat_rejection_kw") if physics_analysis else None
            heat_text = (
                f" estimated {float(heat_kw):g} kW coolant heat rejection"
                if isinstance(heat_kw, (int, float))
                else " coolant heat rejection"
            )
            return source, f"{name} thermal limit of {limit} traces to combustion heat rejection via{heat_text}."

        # Lubrication: oil pan sits near combustion heat rejection (proximity), not chamber exposure.
        if component_id in {"oil_pan"} or "oil pan" in name.lower():
            source = source_or_fallback("constraint_calc_heat_rejection")
            heat_kw = physics_analysis.resolve_operating("cooling_heat_rejection_kw") if physics_analysis else None
            heat_text = (
                f" estimated {float(heat_kw):g} kW coolant/combustion heat rejection"
                if isinstance(heat_kw, (int, float))
                else " coolant/combustion heat rejection"
            )
            return (
                source,
                f"{name} thermal limit of {limit} traces to proximity heat from the crankcase/"
                f"combustion heat-rejection path via{heat_text} "
                "(not direct combustion-chamber exposure).",
            )

        # Oil circuits primarily pick up bearing/friction heat from the reciprocating assembly.
        if component_id in {"oil_pickup_tube", "main_oil_gallery"} or any(
            token in text for token in ("oil pickup", "oil gallery", "oil_circuit")
        ):
            source = source_or_fallback("constraint_calc_piston_acceleration")
            acceleration = (
                physics_analysis.resolve_operating("peak_piston_acceleration_m_s2") if physics_analysis else None
            )
            if isinstance(acceleration, (int, float)):
                mechanism = (
                    f"bearing friction and oil heat pickup driven by estimated "
                    f"{float(acceleration):g} m/s^2 reciprocating mechanical load "
                    f"(proxy via calc_piston_acceleration; dedicated bearing-friction/"
                    f"oil-bulk-temperature calculation not yet available)"
                )
            else:
                mechanism = (
                    "bearing friction and oil heat pickup "
                    "(approximate pending dedicated bearing-friction/oil-temperature calculation)"
                )
            return source, f"{name} thermal limit of {limit} traces to {mechanism}."

        if "exhaust" in text or "combustion" in text or "cylinder head" in text or "cylinder_head" in text or "cylinder bore" in text or "cylinder_bore" in text or (
            "piston" in text and "oil" not in text and "cooling jet" not in text
        ) or ("valve" in text and "camshaft" not in text):
            # Most proximate source of the combustion-side temperature figure.
            source = source_or_fallback("constraint_calc_combustion_side_temperature")
            temp_c = (
                physics_analysis.resolve_operating("combustion_side_temperature_c") if physics_analysis else None
            )
            temp_text = (
                f" estimated {float(temp_c):g} C from calc_combustion_side_temperature"
                if isinstance(temp_c, (int, float))
                else " combustion-side temperature from calc_combustion_side_temperature"
            )
            return source, f"{name} thermal limit of {limit} traces to combustion/exhaust gas exposure via{temp_text}."

        if "crankshaft" in text or "bearing" in text or "shaft" in text or "gear" in text:
            source = source_or_fallback("constraint_calc_piston_acceleration")
            acceleration = (
                physics_analysis.resolve_operating("peak_piston_acceleration_m_s2") if physics_analysis else None
            )
            rpm_text = ""
            if isinstance(acceleration, (int, float)):
                rpm_text = f" driven by estimated {float(acceleration):g} m/s^2 reciprocating acceleration"
            return source, f"{name} thermal limit of {limit} traces to friction/mechanical-load heating{rpm_text}."

        source = source_or_fallback("constraint_calc_heat_rejection")
        return (
            source,
            f"{name} thermal limit of {limit} traces approximately to the heat-rejection path "
            f"(causal chain is approximate pending a more specific thermal calculation for this component).",
        )

    @staticmethod
    def _physics_constraint_source_calc(constraint_id: str) -> str | None:
        """Map physics-derived constraint IDs to their proximate calculation."""
        mapping = {
            "constraint_physics_rod_stress": "calc_rod_stress_requirement",
            "constraint_physics_temperature_pistons": "calc_combustion_side_temperature",
            "constraint_physics_temperature_cylinder_head": "calc_combustion_side_temperature",
        }
        return mapping.get(constraint_id)

    @staticmethod
    def _best_requirement_for_physics(requirement_spec: RequirementSpecification) -> str | None:
        for metric in ("max_rpm", "horsepower", "object_type"):
            for req in requirement_spec.requirements:
                if req.metric == metric:
                    return req.id
        return requirement_spec.requirements[0].id if requirement_spec.requirements else None
