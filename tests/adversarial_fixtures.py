"""Shared adversarial graph fixtures (importable from tests/ on PYTHONPATH)."""

from __future__ import annotations

from core.ir.assembly import AssemblyNode
from core.ir.component import ComponentNode
from core.ir.constraint import Constraint, ConstraintSeverity
from core.ir.design_graph import EngineeringDesignGraph, EngineeringIntent
from core.ir.material import MaterialSpec
from core.reasoning.physics_engine import PhysicsAnalysis, PhysicsCalculation


def base_intent(**kwargs) -> EngineeringIntent:
    defaults = dict(object_type="internal_combustion_engine", design_goal="test engine")
    defaults.update(kwargs)
    return EngineeringIntent(**defaults)


def minimal_graph(**intent_kwargs) -> EngineeringDesignGraph:
    graph = EngineeringDesignGraph(
        name="test",
        type="internal_combustion_engine",
        intent=base_intent(**intent_kwargs),
        root_id="root",
    )
    graph.add_component(
        ComponentNode(
            id="root",
            name="Root",
            function="Root assembly",
            children=["block"],
            is_leaf=False,
        )
    )
    graph.add_component(
        ComponentNode(
            id="block",
            name="Engine Block",
            function="Structural housing for combustion cylinders",
            material="Aluminum 356-T6",
            parent_id="root",
            parent_assembly_id="short_block",
            purpose="Contain combustion",
            justification="Required structural member",
            is_leaf=True,
        )
    )
    graph.add_assembly(
        AssemblyNode(
            id="short_block",
            name="Short Block",
            function="Core structure",
            member_ids=["block"],
        )
    )
    return graph


def graph_no_components() -> EngineeringDesignGraph:
    return EngineeringDesignGraph(
        name="empty",
        type="test",
        intent=base_intent(object_type="test", design_goal="empty"),
        root_id="root",
    )


def graph_bad_root() -> EngineeringDesignGraph:
    graph = minimal_graph()
    graph.root_id = "missing_root"
    return graph


def graph_undefined_child() -> EngineeringDesignGraph:
    graph = minimal_graph()
    graph.components["root"].children = ["phantom_child"]
    return graph


def graph_undefined_parent() -> EngineeringDesignGraph:
    graph = minimal_graph()
    graph.components["block"].parent_id = "nonexistent_parent"
    return graph


def graph_cycle() -> EngineeringDesignGraph:
    graph = EngineeringDesignGraph(
        name="cycle",
        type="test",
        intent=base_intent(object_type="test", design_goal="cycle"),
        root_id="a",
    )
    graph.add_component(ComponentNode(id="a", name="A", function="A", children=["b"]))
    graph.add_component(ComponentNode(id="b", name="B", function="B", children=["a"]))
    return graph


def graph_undefined_assembly_member() -> EngineeringDesignGraph:
    graph = minimal_graph()
    graph.assemblies["short_block"].member_ids = ["ghost_member"]
    return graph


def graph_carbon_fiber_combustion() -> EngineeringDesignGraph:
    graph = minimal_graph()
    block = graph.components["block"]
    block.material = "Carbon fiber"
    block.function = "Cylinder bore combustion chamber lining"
    return graph


def graph_wood_engine() -> EngineeringDesignGraph:
    graph = minimal_graph()
    block = graph.components["block"]
    block.material = "Oak timber"
    block.function = "Engine block structural housing"
    return graph


def graph_glass_crankshaft() -> EngineeringDesignGraph:
    graph = minimal_graph()
    graph.add_component(
        ComponentNode(
            id="crankshaft",
            name="Crankshaft",
            function="Crankshaft — convert reciprocating motion to rotation",
            material="Glass",
            parent_id="root",
            is_leaf=True,
        )
    )
    return graph


def graph_yield_strength_violation() -> tuple[EngineeringDesignGraph, PhysicsAnalysis]:
    graph = minimal_graph()
    block = graph.components["block"]
    block.material = "Aluminum 356-T6"
    block.material_spec = MaterialSpec(
        name="Aluminum 356-T6",
        density_kg_m3=2680,
        yield_strength_mpa=150,
        temperature_limit_c=200,
    )
    physics = PhysicsAnalysis(
        constraints=[
            Constraint(
                id="constraint_yield",
                type="minimum_yield_strength",
                description="Rod yield requirement",
                component_id="block",
                value=400,
                unit="MPa",
                severity=ConstraintSeverity.HARD_LIMIT,
                source="physics_engine",
            )
        ]
    )
    return graph, physics


def graph_excessive_piston_speed() -> tuple[EngineeringDesignGraph, PhysicsAnalysis]:
    graph = minimal_graph()
    physics = PhysicsAnalysis(
        calculations=[
            PhysicsCalculation(
                id="calc_mean_piston_speed",
                name="Mean piston speed",
                formula="Vp = 2 × stroke × RPM / 60",
                result=30.0,
                value_range=(28.0, 30.0),
                unit="m/s",
                passes=False,
                assessment="Exceeds 26 m/s hard limit",
            )
        ]
    )
    return graph, physics


def graph_no_assemblies() -> EngineeringDesignGraph:
    graph = EngineeringDesignGraph(
        name="flat",
        type="internal_combustion_engine",
        intent=base_intent(),
        root_id="root",
    )
    graph.add_component(
        ComponentNode(
            id="root",
            name="Lonely part",
            function="Only component",
            material="Steel",
            is_leaf=True,
        )
    )
    return graph


def graph_generic_placeholder() -> EngineeringDesignGraph:
    graph = minimal_graph()
    graph.add_component(
        ComponentNode(
            id="generic_sub_component",
            name="Generic sub-component",
            function="Unknown",
            parent_id="root",
            is_leaf=True,
        )
    )
    return graph


def graph_no_constraints() -> EngineeringDesignGraph:
    graph = minimal_graph()
    for comp in graph.components.values():
        comp.constraints = []
    for asm in graph.assemblies.values():
        asm.constraints = []
    return graph
