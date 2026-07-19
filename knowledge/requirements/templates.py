"""Domain-specific requirement templates and reference design profiles."""

from core.ir.constraint import ConstraintPriority
from core.ir.requirement_spec import (
    CompiledRequirement,
    DecisionCategory,
    DecisionStatus,
    RequiredDecision,
)

ICE_REQUIRED_DECISIONS: list[dict] = [
    {
        "id": "engine_architecture",
        "category": DecisionCategory.ARCHITECTURE,
        "question": "Engine architecture (cylinder layout and count)?",
        "options": ["Inline 4", "Inline 6", "V6", "V8", "V10", "V12", "Flat 6", "Flat 4"],
    },
    {
        "id": "aspiration",
        "category": DecisionCategory.ASPIRATION,
        "question": "Aspiration type?",
        "options": ["Naturally aspirated", "Turbocharged", "Supercharged", "Twin-turbo"],
    },
    {
        "id": "target_horsepower",
        "category": DecisionCategory.TARGET_OUTPUT,
        "question": "Target horsepower?",
        "options": [],
    },
    {
        "id": "target_torque",
        "category": DecisionCategory.TARGET_OUTPUT,
        "question": "Target torque (Nm)?",
        "options": [],
    },
    {
        "id": "duty_cycle",
        "category": DecisionCategory.DUTY_CYCLE,
        "question": "Intended duty cycle / application?",
        "options": ["Street", "Endurance racing", "Drag", "Aviation", "Marine", "Industrial"],
    },
    {
        "id": "fuel_type",
        "category": DecisionCategory.FUEL,
        "question": "Fuel type?",
        "options": ["Gasoline", "Diesel", "E85", "Racing fuel", "Aviation gasoline"],
    },
]

REFERENCE_PROFILES: dict[str, dict] = {
    "ferrari_v12": {
        "match_keywords": ["ferrari", "v12"],
        "resolved_parameters": {
            "engine_architecture": "V12",
            "cylinder_count": 12,
            "displacement_l": 6.5,
            "aspiration": "Naturally aspirated",
            "max_rpm": 8500,
            "target_horsepower": 800,
            "target_torque_nm": 700,
            "duty_cycle": "Endurance racing",
            "fuel_type": "Gasoline",
            "mass_kg": 250,
            "specific_power_hp_l": 123,
            "nvh_priority": "medium",
            "emissions_priority": "low",
        },
        "requirements": [
            {
                "id": "req_architecture",
                "description": "V12 naturally aspirated architecture",
                "metric": "engine_architecture",
                "target_value": "V12",
                "priority": ConstraintPriority.CRITICAL,
            },
            {
                "id": "req_displacement",
                "description": "6.5L displacement target",
                "metric": "displacement",
                "target_value": 6.5,
                "unit": "L",
                "priority": ConstraintPriority.HIGH,
            },
            {
                "id": "req_max_rpm",
                "description": "8500 RPM redline",
                "metric": "max_rpm",
                "target_value": 8500,
                "unit": "rpm",
                "priority": ConstraintPriority.HIGH,
            },
            {
                "id": "req_power",
                "description": "800 hp target output",
                "metric": "horsepower",
                "target_value": 800,
                "unit": "hp",
                "priority": ConstraintPriority.CRITICAL,
            },
            {
                "id": "req_mass",
                "description": "Total engine mass under 250 kg",
                "metric": "mass",
                "target_value": 250,
                "unit": "kg",
                "priority": ConstraintPriority.HIGH,
            },
            {
                "id": "req_specific_power",
                "description": "Specific power above 120 hp/L",
                "metric": "specific_power",
                "target_value": 120,
                "unit": "hp/L",
                "priority": ConstraintPriority.HIGH,
            },
            {
                "id": "req_duty_cycle",
                "description": "Road endurance duty cycle",
                "metric": "duty_cycle",
                "target_value": "Endurance racing",
                "priority": ConstraintPriority.MEDIUM,
            },
        ],
    },
    "high_rpm_v8": {
        "match_keywords": ["9000 rpm", "9000rpm", "high rpm v8", "na v8"],
        "resolved_parameters": {
            "engine_architecture": "V8",
            "cylinder_count": 8,
            "displacement_l": 4.0,
            "aspiration": "Naturally aspirated",
            "max_rpm": 9000,
            "target_horsepower": 600,
            "target_torque_nm": 450,
            "duty_cycle": "Endurance racing",
            "fuel_type": "Gasoline",
            "mass_kg": 180,
        },
        "requirements": [
            {
                "id": "req_max_rpm",
                "description": "9000 RPM operating speed",
                "metric": "max_rpm",
                "target_value": 9000,
                "unit": "rpm",
                "priority": ConstraintPriority.CRITICAL,
            },
            {
                "id": "req_mass",
                "description": "Total engine mass under 180 kg",
                "metric": "mass",
                "target_value": 180,
                "unit": "kg",
                "priority": ConstraintPriority.HIGH,
            },
        ],
    },
}

PARAMETER_PATTERNS: list[tuple[str, str, str | float]] = [
    (r"\bv12\b", "engine_architecture", "V12"),
    (r"\bv8\b", "engine_architecture", "V8"),
    (r"\bv6\b", "engine_architecture", "V6"),
    (r"\binline\s*4\b|\bi4\b", "engine_architecture", "Inline 4"),
    (r"\bflat\s*6\b|\bflat\s*six\b", "engine_architecture", "Flat 6"),
    (r"\bnaturally\s*aspirated\b|\bna\b", "aspiration", "Naturally aspirated"),
    (r"\bturbocharged\b|\bturbo\b", "aspiration", "Turbocharged"),
    (r"\bsupercharged\b", "aspiration", "Supercharged"),
    (r"(\d+(?:\.\d+)?)\s*l(?:itre|iter)?\b", "displacement_l", 0),  # special: regex group
    (r"(\d+)\s*hp\b", "target_horsepower", 0),
    (r"(\d+)\s*rpm\b", "max_rpm", 0),
    (r"under\s*(\d+)\s*kg", "mass_kg", 0),
]


def build_ice_required_decisions() -> list[RequiredDecision]:
    return [RequiredDecision(**d) for d in ICE_REQUIRED_DECISIONS]


def match_reference_profile(text: str) -> str | None:
    lower = text.lower()
    for profile_id, profile in REFERENCE_PROFILES.items():
        keywords = profile["match_keywords"]
        if all(kw in lower for kw in keywords):
            return profile_id
    return None


def get_reference_profile(profile_id: str) -> dict | None:
    return REFERENCE_PROFILES.get(profile_id)


def compile_reference_requirements(profile_id: str) -> list[CompiledRequirement]:
    profile = REFERENCE_PROFILES.get(profile_id)
    if not profile:
        return []
    return [CompiledRequirement(**r) for r in profile["requirements"]]
