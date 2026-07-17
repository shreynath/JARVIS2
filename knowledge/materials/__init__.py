"""Common engineering materials."""

MATERIALS: dict[str, dict] = {
    "aluminum_alloy": {
        "name": "Aluminum Alloy",
        "suitable_for": ["engine_block", "cylinder_head", "structural_housing"],
        "max_service_temp_c": 200,
        "density_kg_m3": 2700,
    },
    "forged_steel": {
        "name": "Forged Steel",
        "suitable_for": ["crankshaft", "connecting_rod", "bearing_cap"],
        "max_service_temp_c": 400,
        "density_kg_m3": 7850,
    },
    "cast_iron": {
        "name": "Cast Iron",
        "suitable_for": ["cylinder_liner", "engine_block"],
        "max_service_temp_c": 500,
        "density_kg_m3": 7200,
    },
    "titanium_alloy": {
        "name": "Titanium Alloy",
        "suitable_for": ["connecting_rod", "valve", "exhaust_component"],
        "max_service_temp_c": 600,
        "density_kg_m3": 4500,
    },
}
