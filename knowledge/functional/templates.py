"""Functional decomposition templates — engineering reasoning before parts."""

from core.ir.functional import FlowEdge, FlowType, FunctionalAnalysis, RequiredAssembly, SystemFunction

VEHICLE_ENGINE_FUNCTIONS: list[dict] = [
    {
        "id": "generate_power",
        "name": "Generate Mechanical Power",
        "description": "Convert fuel chemical energy into rotational mechanical output",
        "requires": ["combustion", "fuel_delivery", "thermal_management", "motion_conversion"],
        "domain": "thermodynamics",
    },
    {
        "id": "combustion",
        "name": "Controlled Combustion",
        "description": "Burn fuel-air mixture in sealed chambers at controlled timing",
        "requires": ["fuel_delivery", "air_induction", "ignition"],
        "domain": "thermodynamics",
    },
    {
        "id": "fuel_delivery",
        "name": "Fuel Delivery",
        "description": "Meter and inject fuel at correct pressure and timing",
        "requires": [],
        "domain": "fluid_dynamics",
    },
    {
        "id": "air_induction",
        "name": "Air Induction",
        "description": "Supply and meter intake air for combustion",
        "requires": [],
        "domain": "fluid_dynamics",
    },
    {
        "id": "ignition",
        "name": "Ignition",
        "description": "Initiate combustion at precise crank angle",
        "requires": [],
        "domain": "electrical",
    },
    {
        "id": "motion_conversion",
        "name": "Motion Conversion",
        "description": "Convert reciprocating piston force into crankshaft rotation",
        "requires": [],
        "domain": "mechanical_design",
    },
    {
        "id": "thermal_management",
        "name": "Thermal Management",
        "description": "Reject combustion heat to maintain safe operating temperatures",
        "requires": [],
        "domain": "thermodynamics",
    },
    {
        "id": "lubrication",
        "name": "Lubrication",
        "description": "Reduce friction and carry heat away from moving surfaces",
        "requires": [],
        "domain": "mechanical_design",
    },
    {
        "id": "structural_containment",
        "name": "Structural Containment",
        "description": "Contain combustion forces and maintain alignment of moving parts",
        "requires": [],
        "domain": "mechanical_design",
    },
]

VEHICLE_ENGINE_FLOWS: list[dict] = [
    {
        "id": "fuel_to_combustion",
        "flow_type": FlowType.MATERIAL,
        "source_function_id": "fuel_delivery",
        "target_function_id": "combustion",
        "description": "Fuel flows from injection system to combustion chamber",
    },
    {
        "id": "air_to_combustion",
        "flow_type": FlowType.MATERIAL,
        "source_function_id": "air_induction",
        "target_function_id": "combustion",
        "description": "Intake air enters combustion chamber",
    },
    {
        "id": "combustion_to_motion",
        "flow_type": FlowType.ENERGY,
        "source_function_id": "combustion",
        "target_function_id": "motion_conversion",
        "description": "Expansion force drives pistons and crankshaft",
    },
    {
        "id": "motion_to_power",
        "flow_type": FlowType.ENERGY,
        "source_function_id": "motion_conversion",
        "target_function_id": "generate_power",
        "description": "Rotational output delivered to transmission",
    },
    {
        "id": "heat_rejection",
        "flow_type": FlowType.ENERGY,
        "source_function_id": "combustion",
        "target_function_id": "thermal_management",
        "description": "Combustion heat transferred to coolant and exhaust",
    },
    {
        "id": "ignition_signal",
        "flow_type": FlowType.INFORMATION,
        "source_function_id": "ignition",
        "target_function_id": "combustion",
        "description": "ECU triggers spark at computed crank angle",
    },
]

VEHICLE_ENGINE_ASSEMBLIES: list[dict] = [
    {
        "id": "short_block",
        "name": "Short Block",
        "function": "Houses crankshaft, pistons, and cylinders",
        "purpose": "Provide structural foundation and motion conversion",
        "serves_functions": ["structural_containment", "motion_conversion"],
        "parent_assembly_id": "root",
    },
    {
        "id": "cylinder_head_assembly",
        "name": "Cylinder Head Assembly",
        "function": "Seals combustion chambers and controls gas exchange",
        "purpose": "Complete combustion chamber and valve train",
        "serves_functions": ["combustion", "air_induction"],
        "parent_assembly_id": "root",
    },
    {
        "id": "fuel_system",
        "name": "Fuel System",
        "function": "Delivers metered fuel to combustion chambers",
        "purpose": "Enable controlled fuel delivery",
        "serves_functions": ["fuel_delivery"],
        "parent_assembly_id": "root",
    },
    {
        "id": "cooling_system",
        "name": "Cooling System",
        "function": "Maintains engine operating temperature",
        "purpose": "Reject combustion heat",
        "serves_functions": ["thermal_management"],
        "parent_assembly_id": "root",
    },
    {
        "id": "lubrication_system",
        "name": "Lubrication System",
        "function": "Lubricates and cools moving surfaces",
        "purpose": "Reduce wear and frictional losses",
        "serves_functions": ["lubrication"],
        "parent_assembly_id": "root",
    },
    {
        "id": "electrical_system",
        "name": "Electrical System",
        "function": "Ignition timing and engine management",
        "purpose": "Control combustion initiation",
        "serves_functions": ["ignition"],
        "parent_assembly_id": "root",
    },
]

AIRCRAFT_ENGINE_FUNCTIONS: list[dict] = [
    {
        "id": "generate_thrust",
        "name": "Generate Thrust",
        "description": "Produce propulsive force for aircraft propulsion",
        "requires": ["air_compression", "combustion", "energy_extraction", "exhaust_acceleration"],
        "domain": "thermodynamics",
    },
    {
        "id": "air_compression",
        "name": "Air Compression",
        "description": "Raise intake air pressure for efficient combustion",
        "requires": [],
        "domain": "fluid_dynamics",
    },
    {
        "id": "combustion",
        "name": "Continuous Combustion",
        "description": "Burn fuel-air mixture in annular combustor at high pressure",
        "requires": ["fuel_delivery"],
        "domain": "thermodynamics",
    },
    {
        "id": "fuel_delivery",
        "name": "Fuel Delivery",
        "description": "Atomize and inject fuel into combustor",
        "requires": [],
        "domain": "fluid_dynamics",
    },
    {
        "id": "energy_extraction",
        "name": "Energy Extraction",
        "description": "Extract work from hot gas via turbine stages",
        "requires": [],
        "domain": "thermodynamics",
    },
    {
        "id": "exhaust_acceleration",
        "name": "Exhaust Acceleration",
        "description": "Accelerate exhaust gas to produce thrust",
        "requires": [],
        "domain": "fluid_dynamics",
    },
    {
        "id": "thermal_management",
        "name": "Thermal Management",
        "description": "Manage extreme turbine inlet temperatures",
        "requires": [],
        "domain": "materials",
    },
    {
        "id": "accessory_drive",
        "name": "Accessory Drive",
        "description": "Drive fuel pumps, generators, and hydraulic pumps",
        "requires": [],
        "domain": "mechanical_design",
    },
]

AIRCRAFT_ENGINE_FLOWS: list[dict] = [
    {
        "id": "air_to_compressor",
        "flow_type": FlowType.MATERIAL,
        "source_function_id": "air_compression",
        "target_function_id": "combustion",
        "description": "Compressed air enters combustor",
    },
    {
        "id": "fuel_to_combustor",
        "flow_type": FlowType.MATERIAL,
        "source_function_id": "fuel_delivery",
        "target_function_id": "combustion",
        "description": "Atomized fuel injected into combustor",
    },
    {
        "id": "hot_gas_to_turbine",
        "flow_type": FlowType.ENERGY,
        "source_function_id": "combustion",
        "target_function_id": "energy_extraction",
        "description": "High-energy gas expands through turbine",
    },
    {
        "id": "turbine_to_exhaust",
        "flow_type": FlowType.ENERGY,
        "source_function_id": "energy_extraction",
        "target_function_id": "exhaust_acceleration",
        "description": "Remaining gas energy accelerates exhaust nozzle",
    },
    {
        "id": "thrust_output",
        "flow_type": FlowType.ENERGY,
        "source_function_id": "exhaust_acceleration",
        "target_function_id": "generate_thrust",
        "description": "Momentum change produces thrust",
    },
]

AIRCRAFT_ENGINE_ASSEMBLIES: list[dict] = [
    {
        "id": "fan_module",
        "name": "Fan Module",
        "function": "Accelerates bypass air for propulsive efficiency",
        "purpose": "Primary thrust generation in high-bypass turbofan",
        "serves_functions": ["exhaust_acceleration"],
        "parent_assembly_id": "root",
    },
    {
        "id": "compressor_module",
        "name": "Compressor Module",
        "function": "Multi-stage axial compression of core airflow",
        "purpose": "Raise pressure ratio for efficient combustion",
        "serves_functions": ["air_compression"],
        "parent_assembly_id": "root",
    },
    {
        "id": "combustor_module",
        "name": "Combustor Module",
        "function": "Annular combustion chamber with fuel injectors",
        "purpose": "Continuous high-pressure combustion",
        "serves_functions": ["combustion", "fuel_delivery"],
        "parent_assembly_id": "root",
    },
    {
        "id": "turbine_module",
        "name": "Turbine Module",
        "function": "Extract energy from hot gas to drive compressor and fan",
        "purpose": "Power extraction and thermal management",
        "serves_functions": ["energy_extraction", "thermal_management"],
        "parent_assembly_id": "root",
    },
    {
        "id": "exhaust_module",
        "name": "Exhaust Module",
        "function": "Nozzle and exhaust duct assembly",
        "purpose": "Accelerate exhaust for thrust",
        "serves_functions": ["exhaust_acceleration"],
        "parent_assembly_id": "root",
    },
    {
        "id": "accessory_gearbox",
        "name": "Accessory Gearbox",
        "function": "Drive engine accessories from turbine spool",
        "purpose": "Power fuel pumps, generators, hydraulics",
        "serves_functions": ["accessory_drive"],
        "parent_assembly_id": "root",
    },
]

GEARBOX_FUNCTIONS: list[dict] = [
    {
        "id": "torque_transmission",
        "name": "Torque Transmission",
        "description": "Transfer input torque to output shaft at selected ratio",
        "requires": ["gear_meshing", "shaft_support", "lubrication"],
        "domain": "mechanical_design",
    },
    {
        "id": "gear_meshing",
        "name": "Gear Meshing",
        "description": "Mesh gears at correct contact pattern and backlash",
        "requires": [],
        "domain": "mechanical_design",
    },
    {
        "id": "shaft_support",
        "name": "Shaft Support",
        "description": "Support and align rotating shafts under load",
        "requires": [],
        "domain": "mechanical_design",
    },
    {
        "id": "ratio_selection",
        "name": "Ratio Selection",
        "description": "Select gear ratio via shift mechanism",
        "requires": [],
        "domain": "mechanical_design",
    },
    {
        "id": "lubrication",
        "name": "Lubrication",
        "description": "Lubricate gear teeth and bearings under load",
        "requires": [],
        "domain": "mechanical_design",
    },
    {
        "id": "structural_housing",
        "name": "Structural Housing",
        "description": "Contain gear train and maintain alignment",
        "requires": [],
        "domain": "mechanical_design",
    },
]

GEARBOX_FLOWS: list[dict] = [
    {
        "id": "input_torque",
        "flow_type": FlowType.ENERGY,
        "source_function_id": "torque_transmission",
        "target_function_id": "gear_meshing",
        "description": "Input torque transmitted through gear pairs",
    },
    {
        "id": "output_torque",
        "flow_type": FlowType.ENERGY,
        "source_function_id": "gear_meshing",
        "target_function_id": "torque_transmission",
        "description": "Modified torque delivered to output shaft",
    },
    {
        "id": "shift_command",
        "flow_type": FlowType.INFORMATION,
        "source_function_id": "ratio_selection",
        "target_function_id": "gear_meshing",
        "description": "Shift mechanism selects active gear pair",
    },
]

GEARBOX_ASSEMBLIES: list[dict] = [
    {
        "id": "input_shaft_assembly",
        "name": "Input Shaft Assembly",
        "function": "Receives torque from power source",
        "purpose": "Input interface and primary shaft support",
        "serves_functions": ["torque_transmission", "shaft_support"],
        "parent_assembly_id": "root",
    },
    {
        "id": "gear_train",
        "name": "Gear Train",
        "function": "Meshing gear pairs providing speed/torque ratios",
        "purpose": "Core ratio transformation",
        "serves_functions": ["gear_meshing", "ratio_selection"],
        "parent_assembly_id": "root",
    },
    {
        "id": "output_shaft_assembly",
        "name": "Output Shaft Assembly",
        "function": "Delivers transformed torque to load",
        "purpose": "Output interface and shaft support",
        "serves_functions": ["torque_transmission", "shaft_support"],
        "parent_assembly_id": "root",
    },
    {
        "id": "housing",
        "name": "Housing",
        "function": "Structural enclosure maintaining gear alignment",
        "purpose": "Contain gear train and retain lubricant",
        "serves_functions": ["structural_housing"],
        "parent_assembly_id": "root",
    },
    {
        "id": "gearbox_lubrication_system",
        "name": "Lubrication System",
        "function": "Circulate oil to gears and bearings",
        "purpose": "Reduce wear and dissipate heat",
        "serves_functions": ["lubrication"],
        "parent_assembly_id": "root",
    },
    {
        "id": "shift_mechanism",
        "name": "Shift Mechanism",
        "function": "Select and engage gear ratios",
        "purpose": "Enable ratio selection",
        "serves_functions": ["ratio_selection"],
        "parent_assembly_id": "root",
    },
]


from knowledge.functional.general_domains import (
    GENERAL_DOMAIN_KEYWORDS,
    GENERAL_DOMAIN_TEMPLATES,
)


def _build_analysis(
    primary_function: str,
    functions: list[dict],
    flows: list[dict],
    assemblies: list[dict],
    domains: list[str],
) -> FunctionalAnalysis:
    return FunctionalAnalysis(
        primary_function=primary_function,
        functions=[SystemFunction(**f) for f in functions],
        flows=[FlowEdge(**f) for f in flows],
        required_assemblies=[RequiredAssembly(**a) for a in assemblies],
        required_domains=domains,
    )


FUNCTIONAL_TEMPLATES: dict[str, FunctionalAnalysis] = {
    "internal_combustion_engine": _build_analysis(
        primary_function="Generate mechanical power for vehicle propulsion",
        functions=VEHICLE_ENGINE_FUNCTIONS,
        flows=VEHICLE_ENGINE_FLOWS,
        assemblies=VEHICLE_ENGINE_ASSEMBLIES,
        domains=["thermodynamics", "mechanical_design", "materials", "fluid_dynamics"],
    ),
    "turbofan_engine": _build_analysis(
        primary_function="Generate thrust for aircraft propulsion",
        functions=AIRCRAFT_ENGINE_FUNCTIONS,
        flows=AIRCRAFT_ENGINE_FLOWS,
        assemblies=AIRCRAFT_ENGINE_ASSEMBLIES,
        domains=["thermodynamics", "fluid_dynamics", "materials", "structural_analysis"],
    ),
    "gearbox": _build_analysis(
        primary_function="Transmit and modify torque between input and output shafts",
        functions=GEARBOX_FUNCTIONS,
        flows=GEARBOX_FLOWS,
        assemblies=GEARBOX_ASSEMBLIES,
        domains=["mechanical_design", "materials", "tribology"],
    ),
}
FUNCTIONAL_TEMPLATES.update(GENERAL_DOMAIN_TEMPLATES)


def resolve_functional_template(object_type: str, raw_input: str) -> FunctionalAnalysis | None:
    """Select functional template from object type and user input.

    ICE is never the default for unrelated objects. Only explicit ICE / turbofan /
    gearbox cues (or an exact template key) select those packs.
    """
    lower = raw_input.lower()
    norm = (object_type or "").strip().lower().replace("-", "_").replace(" ", "_")

    for keywords, key in GENERAL_DOMAIN_KEYWORDS:
        if any(k in lower for k in keywords):
            return FUNCTIONAL_TEMPLATES.get(key) or GENERAL_DOMAIN_TEMPLATES.get(key)

    if "gearbox" in lower or "transmission" in lower or norm == "gearbox":
        return FUNCTIONAL_TEMPLATES["gearbox"]
    if any(p in lower for p in ("turbofan", "jet engine", "turbojet")) or norm == "turbofan_engine":
        return FUNCTIONAL_TEMPLATES["turbofan_engine"]

    if norm in FUNCTIONAL_TEMPLATES:
        return FUNCTIONAL_TEMPLATES[norm]

    # ICE only when clearly requested — not because the word "engine" appeared in a
    # longer phrase about something else, and never as a universal default.
    ice_cues = (
        "internal combustion",
        "combustion engine",
        "v8",
        "v-8",
        "v12",
        "v-12",
        "ferrari",
        "pagani",
    )
    if norm in {"internal_combustion_engine", "reciprocating_engine", "v8_engine", "v12_engine", "engine"}:
        return FUNCTIONAL_TEMPLATES["internal_combustion_engine"]
    if any(c in lower for c in ice_cues) and "jet" not in lower and "turbofan" not in lower:
        return FUNCTIONAL_TEMPLATES["internal_combustion_engine"]

    return None
