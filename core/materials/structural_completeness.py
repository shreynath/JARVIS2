"""Structural / load-bearing material completeness — Phase E gate."""

from __future__ import annotations

from core.ir.design_graph import EngineeringDesignGraph
from core.materials.component_role import ComponentRole, role_for_component


def is_structural_load_bearing(component_id: str) -> bool:
    """True when ontology registry marks this component as structural load path."""
    return role_for_component(component_id) == ComponentRole.STRUCTURAL_LOAD_PATH


def unassigned_structural_components(graph: EngineeringDesignGraph) -> list[str]:
    """Component IDs tagged structural/load-bearing with no material assigned."""
    missing: list[str] = []
    for comp_id, comp in graph.components.items():
        if not is_structural_load_bearing(comp_id):
            continue
        if not comp.material and comp.material_spec is None:
            missing.append(comp_id)
    return sorted(missing)


def structural_materials_complete(graph: EngineeringDesignGraph) -> bool:
    """All structural/load-bearing components must have a non-null material."""
    return len(unassigned_structural_components(graph)) == 0
