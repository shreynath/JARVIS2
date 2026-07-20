"""Non-ICE functional templates — domain knowledge packs for generality.

Adding a domain here (plus matching COMPONENT_TEMPLATES entries) should not
require changing ``SemanticKernelPipeline`` orchestration.
"""

from __future__ import annotations

from core.ir.functional import FlowEdge, FlowType, FunctionalAnalysis, RequiredAssembly, SystemFunction


def _build(
    primary: str,
    functions: list[dict],
    flows: list[dict],
    assemblies: list[dict],
    domains: list[str],
) -> FunctionalAnalysis:
    return FunctionalAnalysis(
        primary_function=primary,
        functions=[SystemFunction(**f) for f in functions],
        flows=[FlowEdge(**f) for f in flows],
        required_assemblies=[RequiredAssembly(**a) for a in assemblies],
        required_domains=domains,
    )


DINING_CHAIR = _build(
    primary="Support a seated human load with stable structural furniture",
    functions=[
        {"id": "support_load", "name": "Support Vertical Load", "description": "Carry seated user weight to the floor", "requires": ["provide_seat", "stabilize"], "domain": "structural_analysis"},
        {"id": "provide_seat", "name": "Provide Seating Surface", "description": "Comfortable horizontal support surface", "requires": [], "domain": "mechanical_design"},
        {"id": "provide_backrest", "name": "Provide Back Support", "description": "Support the user's back", "requires": [], "domain": "mechanical_design"},
        {"id": "stabilize", "name": "Stabilize Against Tip/Rack", "description": "Resist tipping and racking under lateral loads", "requires": [], "domain": "structural_analysis"},
    ],
    flows=[
        {"id": "load_to_legs", "flow_type": FlowType.ENERGY, "source_function_id": "provide_seat", "target_function_id": "stabilize", "description": "Seat load transferred into leg/frame structure"},
    ],
    assemblies=[
        {"id": "seat_assembly", "name": "Seat Assembly", "function": "Primary seating surface", "purpose": "Support user", "serves_functions": ["provide_seat", "support_load"], "parent_assembly_id": "root"},
        {"id": "backrest_assembly", "name": "Backrest Assembly", "function": "Back support structure", "purpose": "User back support", "serves_functions": ["provide_backrest"], "parent_assembly_id": "root"},
        {"id": "leg_frame_assembly", "name": "Leg and Frame Assembly", "function": "Structural support to floor", "purpose": "Stability and load path", "serves_functions": ["stabilize", "support_load"], "parent_assembly_id": "root"},
    ],
    domains=["structural_analysis", "mechanical_design", "materials"],
)

BICYCLE_FRAME = _build(
    primary="Provide a lightweight structural chassis for a human-powered bicycle",
    functions=[
        {"id": "carry_rider", "name": "Carry Rider and Components", "description": "Support rider, wheels, and drivetrain loads", "requires": ["resist_bending", "locate_interfaces"], "domain": "structural_analysis"},
        {"id": "resist_bending", "name": "Resist Bending and Torsion", "description": "Maintain geometry under pedaling and road loads", "requires": [], "domain": "structural_analysis"},
        {"id": "locate_interfaces", "name": "Locate Interfaces", "description": "Position head tube, BB, dropouts to tolerance", "requires": [], "domain": "mechanical_design"},
    ],
    flows=[
        {"id": "pedal_to_bb", "flow_type": FlowType.ENERGY, "source_function_id": "carry_rider", "target_function_id": "resist_bending", "description": "Pedaling loads into frame tubes"},
    ],
    assemblies=[
        {"id": "main_triangle", "name": "Main Triangle", "function": "Primary load-bearing tube set", "purpose": "Rider and drivetrain support", "serves_functions": ["carry_rider", "resist_bending"], "parent_assembly_id": "root"},
        {"id": "rear_triangle", "name": "Rear Triangle", "function": "Wheel and brake mount structure", "purpose": "Locate rear wheel", "serves_functions": ["locate_interfaces", "resist_bending"], "parent_assembly_id": "root"},
        {"id": "interface_nodes", "name": "Interface Nodes", "function": "Head tube, BB shell, dropouts", "purpose": "Component interfaces", "serves_functions": ["locate_interfaces"], "parent_assembly_id": "root"},
    ],
    domains=["structural_analysis", "mechanical_design", "materials"],
)

STEEL_TRUSS_BRIDGE = _build(
    primary="Span a gap and carry design traffic loads via a steel truss",
    functions=[
        {"id": "span_gap", "name": "Span Gap", "description": "Provide clear span between supports", "requires": ["carry_deck_load", "transfer_to_supports"], "domain": "structural_analysis"},
        {"id": "carry_deck_load", "name": "Carry Deck Load", "description": "Support roadway/live loads", "requires": [], "domain": "structural_analysis"},
        {"id": "transfer_to_supports", "name": "Transfer to Supports", "description": "Deliver reactions to abutments/piers", "requires": [], "domain": "structural_analysis"},
    ],
    flows=[
        {"id": "deck_to_truss", "flow_type": FlowType.ENERGY, "source_function_id": "carry_deck_load", "target_function_id": "transfer_to_supports", "description": "Deck loads into truss members then supports"},
    ],
    assemblies=[
        {"id": "deck_system", "name": "Deck System", "function": "Traffic surface and stringers", "purpose": "Carry live load", "serves_functions": ["carry_deck_load"], "parent_assembly_id": "root"},
        {"id": "truss_superstructure", "name": "Truss Superstructure", "function": "Primary spanning truss", "purpose": "Span and stiffness", "serves_functions": ["span_gap", "transfer_to_supports"], "parent_assembly_id": "root"},
        {"id": "substructure", "name": "Substructure", "function": "Abutments and bearings", "purpose": "Support reactions", "serves_functions": ["transfer_to_supports"], "parent_assembly_id": "root"},
    ],
    domains=["structural_analysis", "civil_engineering", "materials"],
)

QUADCOPTER_FRAME = _build(
    primary="Provide a rigid lightweight airframe for a multirotor drone",
    functions=[
        {"id": "mount_propulsion", "name": "Mount Propulsion", "description": "Locate motors at arm tips", "requires": ["resist_vibration"], "domain": "mechanical_design"},
        {"id": "protect_avionics", "name": "Protect Avionics", "description": "House flight controller and battery", "requires": [], "domain": "mechanical_design"},
        {"id": "resist_vibration", "name": "Resist Vibration", "description": "Maintain stiffness under rotor loads", "requires": [], "domain": "structural_analysis"},
    ],
    flows=[
        {"id": "thrust_to_center", "flow_type": FlowType.ENERGY, "source_function_id": "mount_propulsion", "target_function_id": "resist_vibration", "description": "Motor thrust into central frame"},
    ],
    assemblies=[
        {"id": "center_plate", "name": "Center Plate Assembly", "function": "Avionics and battery bay", "purpose": "Core structure", "serves_functions": ["protect_avionics"], "parent_assembly_id": "root"},
        {"id": "arm_assembly", "name": "Arm Assembly", "function": "Motor mount arms", "purpose": "Propulsion spacing", "serves_functions": ["mount_propulsion", "resist_vibration"], "parent_assembly_id": "root"},
        {"id": "landing_gear", "name": "Landing Gear", "function": "Ground contact supports", "purpose": "Landing loads", "serves_functions": ["resist_vibration"], "parent_assembly_id": "root"},
    ],
    domains=["structural_analysis", "mechanical_design", "materials", "aerodynamics"],
)

HVAC_DUCTWORK = _build(
    primary="Distribute conditioned air through a residential duct network",
    functions=[
        {"id": "convey_air", "name": "Convey Air", "description": "Move supply/return air with acceptable pressure drop", "requires": ["seal_paths", "control_flow"], "domain": "fluid_dynamics"},
        {"id": "seal_paths", "name": "Seal Duct Paths", "description": "Limit leakage", "requires": [], "domain": "mechanical_design"},
        {"id": "control_flow", "name": "Control Flow", "description": "Balance rooms via dampers", "requires": [], "domain": "fluid_dynamics"},
    ],
    flows=[
        {"id": "supply_flow", "flow_type": FlowType.MATERIAL, "source_function_id": "convey_air", "target_function_id": "control_flow", "description": "Supply air to terminal devices"},
    ],
    assemblies=[
        {"id": "supply_trunk", "name": "Supply Trunk", "function": "Primary supply duct", "purpose": "Main distribution", "serves_functions": ["convey_air"], "parent_assembly_id": "root"},
        {"id": "branch_runs", "name": "Branch Runs", "function": "Room branches", "purpose": "Zone delivery", "serves_functions": ["convey_air", "control_flow"], "parent_assembly_id": "root"},
        {"id": "return_path", "name": "Return Path", "function": "Return air path", "purpose": "Air recirculation", "serves_functions": ["convey_air", "seal_paths"], "parent_assembly_id": "root"},
    ],
    domains=["fluid_dynamics", "thermal", "mechanical_design"],
)

BATTERY_PACK_ENCLOSURE = _build(
    primary="Mechanically protect and thermally manage a lithium-ion battery pack",
    functions=[
        {"id": "contain_cells", "name": "Contain Cells", "description": "Structural enclosure for cell modules", "requires": ["manage_thermal", "electrical_isolation"], "domain": "mechanical_design"},
        {"id": "manage_thermal", "name": "Manage Thermal", "description": "Reject or distribute cell heat", "requires": [], "domain": "thermal"},
        {"id": "electrical_isolation", "name": "Electrical Isolation", "description": "Prevent short circuits and shock", "requires": [], "domain": "electrical"},
    ],
    flows=[
        {"id": "heat_out", "flow_type": FlowType.ENERGY, "source_function_id": "contain_cells", "target_function_id": "manage_thermal", "description": "Cell heat to thermal path"},
    ],
    assemblies=[
        {"id": "enclosure_shell", "name": "Enclosure Shell", "function": "Outer mechanical case", "purpose": "Impact and sealing", "serves_functions": ["contain_cells"], "parent_assembly_id": "root"},
        {"id": "module_tray", "name": "Module Tray", "function": "Cell module retention", "purpose": "Locate modules", "serves_functions": ["contain_cells", "electrical_isolation"], "parent_assembly_id": "root"},
        {"id": "thermal_system", "name": "Thermal System", "function": "Cooling/heating path", "purpose": "Temperature control", "serves_functions": ["manage_thermal"], "parent_assembly_id": "root"},
    ],
    domains=["mechanical_design", "thermal", "electrical", "materials"],
)

CENTRIFUGAL_PUMP = _build(
    primary="Convert shaft power into fluid head via a centrifugal impeller",
    functions=[
        {"id": "impart_momentum", "name": "Impart Momentum", "description": "Accelerate fluid with impeller", "requires": ["guide_flow", "seal_shaft"], "domain": "fluid_dynamics"},
        {"id": "guide_flow", "name": "Guide Flow", "description": "Volute/diffuser pressure recovery", "requires": [], "domain": "fluid_dynamics"},
        {"id": "seal_shaft", "name": "Seal Shaft", "description": "Prevent leakage at shaft penetration", "requires": [], "domain": "mechanical_design"},
    ],
    flows=[
        {"id": "suction_to_discharge", "flow_type": FlowType.MATERIAL, "source_function_id": "impart_momentum", "target_function_id": "guide_flow", "description": "Process fluid through pump"},
    ],
    assemblies=[
        {"id": "impeller_assembly", "name": "Impeller Assembly", "function": "Rotating hydraulic element", "purpose": "Energy transfer to fluid", "serves_functions": ["impart_momentum"], "parent_assembly_id": "root"},
        {"id": "casing_volute", "name": "Casing / Volute", "function": "Pressure boundary and diffuser", "purpose": "Flow guidance", "serves_functions": ["guide_flow"], "parent_assembly_id": "root"},
        {"id": "shaft_seal_bearing", "name": "Shaft, Seal, Bearings", "function": "Rotordynamics and sealing", "purpose": "Support and seal rotor", "serves_functions": ["seal_shaft", "impart_momentum"], "parent_assembly_id": "root"},
    ],
    domains=["fluid_dynamics", "mechanical_design", "materials"],
)

ROBOTIC_GRIPPER = _build(
    primary="Grasp and release objects with controlled contact force",
    functions=[
        {"id": "actuate_jaws", "name": "Actuate Jaws", "description": "Open/close gripping elements", "requires": ["sense_force"], "domain": "mechatronics"},
        {"id": "contact_object", "name": "Contact Object", "description": "Apply friction/form closure", "requires": [], "domain": "mechanical_design"},
        {"id": "sense_force", "name": "Sense Force", "description": "Limit grasp force", "requires": [], "domain": "electrical"},
    ],
    flows=[
        {"id": "actuation_to_contact", "flow_type": FlowType.ENERGY, "source_function_id": "actuate_jaws", "target_function_id": "contact_object", "description": "Actuator force to fingertips"},
    ],
    assemblies=[
        {"id": "finger_mechanism", "name": "Finger Mechanism", "function": "Jaw/finger kinematics", "purpose": "Grasp geometry", "serves_functions": ["actuate_jaws", "contact_object"], "parent_assembly_id": "root"},
        {"id": "actuator_drive", "name": "Actuator Drive", "function": "Motion source", "purpose": "Power grasp", "serves_functions": ["actuate_jaws"], "parent_assembly_id": "root"},
        {"id": "sensor_mount", "name": "Sensor Mount", "function": "Force/tactile sensing", "purpose": "Force feedback", "serves_functions": ["sense_force"], "parent_assembly_id": "root"},
    ],
    domains=["mechatronics", "mechanical_design", "electrical"],
)

PRESSURE_VESSEL = _build(
    primary="Safely contain compressed nitrogen under design pressure",
    functions=[
        {"id": "contain_pressure", "name": "Contain Pressure", "description": "Primary pressure boundary", "requires": ["seal_ports", "relieve_overpressure"], "domain": "structural_analysis"},
        {"id": "seal_ports", "name": "Seal Ports", "description": "Nozzles, manways, fittings", "requires": [], "domain": "mechanical_design"},
        {"id": "relieve_overpressure", "name": "Relieve Overpressure", "description": "PRV / rupture path", "requires": [], "domain": "safety"},
    ],
    flows=[
        {"id": "gas_containment", "flow_type": FlowType.MATERIAL, "source_function_id": "seal_ports", "target_function_id": "contain_pressure", "description": "Nitrogen retained in vessel"},
    ],
    assemblies=[
        {"id": "shell_heads", "name": "Shell and Heads", "function": "Pressure boundary", "purpose": "Containment", "serves_functions": ["contain_pressure"], "parent_assembly_id": "root"},
        {"id": "nozzles_closures", "name": "Nozzles and Closures", "function": "Access and piping interfaces", "purpose": "Sealed ports", "serves_functions": ["seal_ports"], "parent_assembly_id": "root"},
        {"id": "safety_devices", "name": "Safety Devices", "function": "Overpressure protection", "purpose": "Code-required relief", "serves_functions": ["relieve_overpressure"], "parent_assembly_id": "root"},
    ],
    domains=["structural_analysis", "mechanical_design", "safety", "materials"],
)

SOLAR_MOUNTING_RACK = _build(
    primary="Support solar modules against gravity and environmental loads",
    functions=[
        {"id": "support_modules", "name": "Support Modules", "description": "Carry panel weight and wind/snow", "requires": ["anchor_to_structure", "orient_array"], "domain": "structural_analysis"},
        {"id": "anchor_to_structure", "name": "Anchor to Structure", "description": "Transfer loads to roof/ground", "requires": [], "domain": "structural_analysis"},
        {"id": "orient_array", "name": "Orient Array", "description": "Hold tilt/azimuth", "requires": [], "domain": "mechanical_design"},
    ],
    flows=[
        {"id": "wind_to_anchor", "flow_type": FlowType.ENERGY, "source_function_id": "support_modules", "target_function_id": "anchor_to_structure", "description": "Environmental loads into foundation"},
    ],
    assemblies=[
        {"id": "rail_system", "name": "Rail System", "function": "Module mounting rails", "purpose": "Panel support", "serves_functions": ["support_modules", "orient_array"], "parent_assembly_id": "root"},
        {"id": "supports_legs", "name": "Supports / Legs", "function": "Vertical load path", "purpose": "Elevation and tilt", "serves_functions": ["support_modules", "orient_array"], "parent_assembly_id": "root"},
        {"id": "anchorage", "name": "Anchorage", "function": "Roof/ground anchors", "purpose": "Reaction path", "serves_functions": ["anchor_to_structure"], "parent_assembly_id": "root"},
    ],
    domains=["structural_analysis", "civil_engineering", "mechanical_design", "materials"],
)


GENERAL_DOMAIN_TEMPLATES: dict[str, FunctionalAnalysis] = {
    "dining_chair": DINING_CHAIR,
    "wooden_dining_chair": DINING_CHAIR,
    "chair": DINING_CHAIR,
    "furniture_chair": DINING_CHAIR,
    "bicycle_frame": BICYCLE_FRAME,
    "bike_frame": BICYCLE_FRAME,
    "road_bicycle_frame": BICYCLE_FRAME,
    "steel_truss_bridge": STEEL_TRUSS_BRIDGE,
    "truss_bridge": STEEL_TRUSS_BRIDGE,
    "bridge": STEEL_TRUSS_BRIDGE,
    "quadcopter_frame": QUADCOPTER_FRAME,
    "drone_frame": QUADCOPTER_FRAME,
    "multirotor_frame": QUADCOPTER_FRAME,
    "hvac_ductwork": HVAC_DUCTWORK,
    "ductwork": HVAC_DUCTWORK,
    "residential_hvac_ductwork": HVAC_DUCTWORK,
    "battery_pack_enclosure": BATTERY_PACK_ENCLOSURE,
    "battery_enclosure": BATTERY_PACK_ENCLOSURE,
    "lithium_ion_battery_pack_enclosure": BATTERY_PACK_ENCLOSURE,
    "centrifugal_pump": CENTRIFUGAL_PUMP,
    "centrifugal_water_pump": CENTRIFUGAL_PUMP,
    "water_pump": CENTRIFUGAL_PUMP,
    "robotic_arm_gripper": ROBOTIC_GRIPPER,
    "robotic_gripper": ROBOTIC_GRIPPER,
    "gripper": ROBOTIC_GRIPPER,
    "pressure_vessel": PRESSURE_VESSEL,
    "nitrogen_pressure_vessel": PRESSURE_VESSEL,
    "solar_panel_mounting_rack": SOLAR_MOUNTING_RACK,
    "solar_mounting_rack": SOLAR_MOUNTING_RACK,
    "solar_rack": SOLAR_MOUNTING_RACK,
}


# Keyword → template key for resolve when object_type is novel but text is clear.
GENERAL_DOMAIN_KEYWORDS: list[tuple[tuple[str, ...], str]] = [
    (("dining chair", "wooden chair", "chair"), "dining_chair"),
    (("bicycle frame", "bike frame", "road racing bike"), "bicycle_frame"),
    (("truss bridge", "steel truss", "bridge spanning"), "steel_truss_bridge"),
    (("quadcopter", "drone frame", "multirotor"), "quadcopter_frame"),
    (("hvac", "ductwork"), "hvac_ductwork"),
    (("battery pack", "battery enclosure", "lithium-ion", "lithium ion"), "battery_pack_enclosure"),
    (("centrifugal", "water pump"), "centrifugal_pump"),
    (("gripper", "robotic arm"), "robotic_arm_gripper"),
    (("pressure vessel", "compressed nitrogen"), "pressure_vessel"),
    (("solar panel", "solar mounting", "mounting rack"), "solar_panel_mounting_rack"),
]
