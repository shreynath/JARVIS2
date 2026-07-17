"""Top-level engine system taxonomy."""

ENGINE_SYSTEMS: list[dict] = [
    {"id": "block_assembly", "name": "Block Assembly", "function": "Houses cylinders and crankshaft"},
    {"id": "crankshaft_assembly", "name": "Crankshaft Assembly", "function": "Converts reciprocating to rotational motion"},
    {"id": "cylinder_head_assembly", "name": "Cylinder Head Assembly", "function": "Seals combustion chambers"},
    {"id": "fuel_system", "name": "Fuel System", "function": "Delivers fuel to combustion chambers"},
    {"id": "cooling_system", "name": "Cooling System", "function": "Maintains operating temperature"},
    {"id": "lubrication_system", "name": "Lubrication System", "function": "Reduces friction and removes heat"},
    {"id": "electrical_system", "name": "Electrical System", "function": "Ignition and engine management"},
    {"id": "intake_system", "name": "Intake System", "function": "Delivers air to combustion chambers"},
    {"id": "exhaust_system", "name": "Exhaust System", "function": "Removes combustion products"},
]
