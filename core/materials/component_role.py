"""Explicit component roles — never inferred from substring name matching."""

from __future__ import annotations

from enum import Enum


class ComponentRole(Enum):
    STRUCTURAL_LOAD_PATH = "structural_load_path"
    THERMAL_SYSTEM = "thermal_system"
    PRESSURE_BOUNDARY = "pressure_boundary"
    ROTATING_MASS = "rotating_mass"
    FLUID_COMPONENT = "fluid_component"
    UNKNOWN = "unknown"


# Explicit registry: component_id → role. Name/string matching is forbidden.
COMPONENT_ROLE_REGISTRY: dict[str, ComponentRole] = {
    "connecting_rods": ComponentRole.STRUCTURAL_LOAD_PATH,
    "rod_primary": ComponentRole.STRUCTURAL_LOAD_PATH,
    "rotating_link": ComponentRole.STRUCTURAL_LOAD_PATH,
    "rod_piece_xyz": ComponentRole.STRUCTURAL_LOAD_PATH,
    "pistons": ComponentRole.ROTATING_MASS,
    "crankshaft": ComponentRole.ROTATING_MASS,
    "camshaft": ComponentRole.ROTATING_MASS,
    "main_bearings": ComponentRole.ROTATING_MASS,
    "engine_block": ComponentRole.PRESSURE_BOUNDARY,
    "cylinder_head": ComponentRole.PRESSURE_BOUNDARY,
    "cylinder_bores": ComponentRole.PRESSURE_BOUNDARY,
    "valves": ComponentRole.PRESSURE_BOUNDARY,
    "exhaust_valves": ComponentRole.PRESSURE_BOUNDARY,
    "radiator": ComponentRole.THERMAL_SYSTEM,
    "main_oil_gallery": ComponentRole.THERMAL_SYSTEM,
    "thermal_fluid_nozzle": ComponentRole.THERMAL_SYSTEM,
    "oil_pan": ComponentRole.FLUID_COMPONENT,
    "oil_pickup_tube": ComponentRole.FLUID_COMPONENT,
    "water_pump": ComponentRole.FLUID_COMPONENT,
    "oil_pump": ComponentRole.FLUID_COMPONENT,
    # Bridge / civil structural members
    "top_chord": ComponentRole.STRUCTURAL_LOAD_PATH,
    "bottom_chord": ComponentRole.STRUCTURAL_LOAD_PATH,
    "web_diagonals": ComponentRole.STRUCTURAL_LOAD_PATH,
    "verticals": ComponentRole.STRUCTURAL_LOAD_PATH,
    "stringers": ComponentRole.STRUCTURAL_LOAD_PATH,
    # Bicycle frame tubes
    "top_tube": ComponentRole.STRUCTURAL_LOAD_PATH,
    "down_tube": ComponentRole.STRUCTURAL_LOAD_PATH,
    "seat_tube": ComponentRole.STRUCTURAL_LOAD_PATH,
    "seat_stays": ComponentRole.STRUCTURAL_LOAD_PATH,
    "chain_stays": ComponentRole.STRUCTURAL_LOAD_PATH,
    # Chair load path
    "front_legs": ComponentRole.STRUCTURAL_LOAD_PATH,
    "rear_legs": ComponentRole.STRUCTURAL_LOAD_PATH,
    "stretchers": ComponentRole.STRUCTURAL_LOAD_PATH,
    "seat_rails": ComponentRole.STRUCTURAL_LOAD_PATH,
}


def role_for_component(component_id: str) -> ComponentRole:
    """Resolve role solely from the explicit registry — never from name text."""
    return COMPONENT_ROLE_REGISTRY.get(component_id, ComponentRole.UNKNOWN)
