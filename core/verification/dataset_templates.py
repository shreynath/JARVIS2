"""Official dataset templates — headers only; missing values stay empty in submissions."""

from __future__ import annotations

from pathlib import Path

TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "datasets" / "templates"

ROD_TEMPLATE = TEMPLATES_DIR / "rod_validation_template.csv"
BMEP_TEMPLATE = TEMPLATES_DIR / "bmep_validation_template.csv"
MATERIAL_TEMPLATE = TEMPLATES_DIR / "material_validation_template.csv"

ROD_REQUIRED_COLUMNS = (
    "engine_name",
    "manufacturer",
    "year",
    "application",
    "rpm",
    "stroke_mm",
    "bore_mm",
    "rod_length_mm",
    "piston_mass_g",
    "rod_mass_g",
    "rod_material",
    "yield_strength_mpa",
    "fatigue_strength_mpa",
    "failure_data_available",
    "source_id",
    "source_type",
    "measurement_method",
    "uncertainty",
    "notes",
)

BMEP_REQUIRED_COLUMNS = (
    "engine_name",
    "family",
    "manufacturer",
    "rpm",
    "horsepower",
    "torque_nm",
    "displacement_l",
    "aspiration",
    "fuel_type",
    "peak_or_continuous",
    "source_id",
    "measurement_method",
    "uncertainty",
    "notes",
)

MATERIAL_REQUIRED_COLUMNS = (
    "component",
    "engine_name",
    "material",
    "yield_strength_mpa",
    "fatigue_strength_mpa",
    "temperature_limit_c",
    "operating_temperature_c",
    "source_id",
    "measurement_method",
    "uncertainty",
    "notes",
)

# Fields required for M4 rod campaign completeness (per case).
ROD_M4_CASE_FIELDS = (
    "engine_name",
    "rpm",
    "stroke_mm",
    "bore_mm",
    "rod_length_mm",
    "piston_mass_g",
    "rod_mass_g",
    "rod_material",
    "source_id",
    "measurement_method",
    "uncertainty",
)

BMEP_M4_PAIR_RULES = (
    ("horsepower", "rpm"),
    ("torque_nm", "displacement_l"),
)

MATERIAL_M4_FIELDS = (
    "component",
    "engine_name",
    "material",
    "yield_strength_mpa",
    "fatigue_strength_mpa",
    "temperature_limit_c",
    "source_id",
    "measurement_method",
    "uncertainty",
)


def template_headers(path: Path) -> list[str]:
    line = path.read_text(encoding="utf-8").strip().splitlines()[0]
    return [c.strip() for c in line.split(",")]
