"""Reciprocating mass model — geometry-based estimates with explicit assumptions.

Does not hide mass factors: every density / thickness / fraction enters AssumptionRegistry.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from core.epistemology.assumption_registry import AssumptionRegistry
from core.verification.model_maturity import ModelMaturity

# Transparent defaults — always registered as assumptions when used.
AL_PISTON_DENSITY_KG_M3 = 2700.0
STEEL_PIN_DENSITY_KG_M3 = 7850.0
PISTON_CROWN_THICKNESS_FRACTION_OF_BORE = 0.08
PISTON_SKIRT_HEIGHT_FRACTION_OF_STROKE = 0.55
PISTON_WALL_THICKNESS_FRACTION_OF_BORE = 0.04
RING_PACK_MASS_FRACTION_OF_PISTON = 0.08
PIN_OD_FRACTION_OF_BORE = 0.22
PIN_ID_FRACTION_OF_OD = 0.55
PIN_LENGTH_FRACTION_OF_BORE = 0.75
ROD_SMALL_END_FRACTION_OF_PISTON = 0.35


@dataclass
class ReciprocatingMassResult:
    piston_mass_kg: float
    pin_mass_kg: float
    ring_mass_kg: float
    rod_small_end_mass_kg: float
    reciprocating_mass_kg: float
    confidence: str
    assumptions: list[str] = field(default_factory=list)
    assumption_records: list[dict[str, Any]] = field(default_factory=list)
    maturity: str = "M2"
    method: str = "geometry_density_shell"

    def to_dict(self) -> dict[str, Any]:
        return {
            "piston_mass_kg": self.piston_mass_kg,
            "pin_mass_kg": self.pin_mass_kg,
            "ring_mass_kg": self.ring_mass_kg,
            "rod_small_end_mass_kg": self.rod_small_end_mass_kg,
            "reciprocating_mass_kg": self.reciprocating_mass_kg,
            "confidence": self.confidence,
            "maturity": self.maturity,
            "method": self.method,
            "assumptions": list(self.assumptions),
            "assumption_records": list(self.assumption_records),
        }


class ReciprocatingMassModel:
    """Estimate reciprocating mass from bore/stroke + explicit geometry heuristics."""

    MATURITY = ModelMaturity.M2

    def estimate(
        self,
        *,
        bore_mm: float,
        stroke_mm: float,
        piston_density_kg_m3: float | None = None,
        pin_density_kg_m3: float | None = None,
        registry: AssumptionRegistry | None = None,
    ) -> ReciprocatingMassResult:
        reg = registry if registry is not None else AssumptionRegistry()
        bore_m = bore_mm / 1000.0
        stroke_m = stroke_mm / 1000.0

        density = piston_density_kg_m3 if piston_density_kg_m3 is not None else AL_PISTON_DENSITY_KG_M3
        pin_density = pin_density_kg_m3 if pin_density_kg_m3 is not None else STEEL_PIN_DENSITY_KG_M3

        if piston_density_kg_m3 is None:
            reg.record(
                id="mass_piston_density",
                field="piston_density_kg_m3",
                assumed_value=density,
                rationale="Default aluminum piston alloy density",
                source_model="ReciprocatingMassModel",
                confidence="medium",
                category="material",
            )
        if pin_density_kg_m3 is None:
            reg.record(
                id="mass_pin_density",
                field="pin_density_kg_m3",
                assumed_value=pin_density,
                rationale="Default steel wrist-pin density",
                source_model="ReciprocatingMassModel",
                confidence="medium",
                category="material",
            )

        # Piston as annular shell: crown disk + skirt cylinder wall (order-of-magnitude).
        crown_t = PISTON_CROWN_THICKNESS_FRACTION_OF_BORE * bore_m
        skirt_h = PISTON_SKIRT_HEIGHT_FRACTION_OF_STROKE * stroke_m
        wall_t = PISTON_WALL_THICKNESS_FRACTION_OF_BORE * bore_m
        for aid, field_name, value, why in (
            (
                "mass_crown_t",
                "piston_crown_thickness_fraction_of_bore",
                PISTON_CROWN_THICKNESS_FRACTION_OF_BORE,
                "Heuristic crown thickness as fraction of bore",
            ),
            (
                "mass_skirt_h",
                "piston_skirt_height_fraction_of_stroke",
                PISTON_SKIRT_HEIGHT_FRACTION_OF_STROKE,
                "Heuristic skirt height as fraction of stroke",
            ),
            (
                "mass_wall_t",
                "piston_wall_thickness_fraction_of_bore",
                PISTON_WALL_THICKNESS_FRACTION_OF_BORE,
                "Heuristic skirt wall thickness as fraction of bore",
            ),
        ):
            reg.record(
                id=aid,
                field=field_name,
                assumed_value=value,
                rationale=why,
                source_model="ReciprocatingMassModel",
                confidence="low",
                category="geometry",
            )

        crown_vol = math.pi * bore_m**2 / 4.0 * crown_t
        skirt_vol = math.pi * ((bore_m / 2.0) ** 2 - ((bore_m / 2.0) - wall_t) ** 2) * skirt_h
        piston_mass = density * (crown_vol + skirt_vol)

        reg.record(
            id="mass_ring_frac",
            field="ring_pack_mass_fraction_of_piston",
            assumed_value=RING_PACK_MASS_FRACTION_OF_PISTON,
            rationale="Ring pack mass as fraction of piston body",
            source_model="ReciprocatingMassModel",
            confidence="low",
            category="geometry",
        )
        ring_mass = piston_mass * RING_PACK_MASS_FRACTION_OF_PISTON

        pin_od = PIN_OD_FRACTION_OF_BORE * bore_m
        pin_id = PIN_ID_FRACTION_OF_OD * pin_od
        pin_len = PIN_LENGTH_FRACTION_OF_BORE * bore_m
        for aid, field_name, value, why in (
            ("mass_pin_od", "pin_od_fraction_of_bore", PIN_OD_FRACTION_OF_BORE, "Wrist pin OD vs bore"),
            ("mass_pin_id", "pin_id_fraction_of_od", PIN_ID_FRACTION_OF_OD, "Wrist pin hollow fraction"),
            ("mass_pin_len", "pin_length_fraction_of_bore", PIN_LENGTH_FRACTION_OF_BORE, "Wrist pin length vs bore"),
        ):
            reg.record(
                id=aid,
                field=field_name,
                assumed_value=value,
                rationale=why,
                source_model="ReciprocatingMassModel",
                confidence="low",
                category="geometry",
            )
        pin_vol = math.pi / 4.0 * (pin_od**2 - pin_id**2) * pin_len
        pin_mass = pin_density * pin_vol

        reg.record(
            id="mass_rod_small_end",
            field="rod_small_end_fraction_of_piston",
            assumed_value=ROD_SMALL_END_FRACTION_OF_PISTON,
            rationale="Small-end reciprocating share of piston mass (not full rod)",
            source_model="ReciprocatingMassModel",
            confidence="low",
            category="geometry",
        )
        rod_small_end = piston_mass * ROD_SMALL_END_FRACTION_OF_PISTON

        reciprocating = piston_mass + pin_mass + ring_mass + rod_small_end

        return ReciprocatingMassResult(
            piston_mass_kg=round(piston_mass, 4),
            pin_mass_kg=round(pin_mass, 4),
            ring_mass_kg=round(ring_mass, 4),
            rod_small_end_mass_kg=round(rod_small_end, 4),
            reciprocating_mass_kg=round(reciprocating, 4),
            confidence="medium",
            assumptions=reg.as_strings(),
            assumption_records=reg.as_dicts(),
            maturity=self.MATURITY.name,
        )
