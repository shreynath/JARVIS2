"""Connecting-rod structural model — geometry-aware stress / buckling / fatigue margins.

Supports simple I-beam and H-beam section approximations. Not FEA.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from core.epistemology.assumption_registry import AssumptionRegistry
from core.verification.model_maturity import ModelMaturity


class RodSectionType(Enum):
    I_BEAM = "i_beam"
    H_BEAM = "h_beam"


# Transparent section heuristics (fractions of bore / stroke).
ROD_LENGTH_STROKE_RATIO = 1.65  # L/S typical gasoline band
I_BEAM_WEB_THICKNESS_FRACTION = 0.08
I_BEAM_FLANGE_WIDTH_FRACTION = 0.35
I_BEAM_FLANGE_THICKNESS_FRACTION = 0.10
I_BEAM_DEPTH_FRACTION = 0.55
H_BEAM_WEB_THICKNESS_FRACTION = 0.12
H_BEAM_FLANGE_WIDTH_FRACTION = 0.40
H_BEAM_FLANGE_THICKNESS_FRACTION = 0.12
H_BEAM_DEPTH_FRACTION = 0.50
STEEL_E_GPA = 200.0
END_FIXITY_FACTOR = 1.0  # pinned-pinned Euler
FATIGUE_DERATE = 0.45  # endurance approx as fraction of yield for ranking


@dataclass
class ConnectingRodResult:
    rod_length_mm: float
    section_type: str
    cross_section_area_m2: float
    second_moment_m4: float
    tensile_load_n: float
    compressive_load_n: float
    maximum_tensile_stress_mpa: float
    compressive_stress_mpa: float
    euler_critical_load_n: float
    buckling_margin: float
    fatigue_margin: float
    confidence: str
    maturity: str = "M3"
    assumptions: list[str] = field(default_factory=list)
    assumption_records: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rod_length_mm": self.rod_length_mm,
            "section_type": self.section_type,
            "cross_section_area_m2": self.cross_section_area_m2,
            "second_moment_m4": self.second_moment_m4,
            "tensile_load_n": self.tensile_load_n,
            "compressive_load_n": self.compressive_load_n,
            "maximum_tensile_stress_mpa": self.maximum_tensile_stress_mpa,
            "compressive_stress_mpa": self.compressive_stress_mpa,
            "euler_critical_load_n": self.euler_critical_load_n,
            "buckling_margin": self.buckling_margin,
            "fatigue_margin": self.fatigue_margin,
            "confidence": self.confidence,
            "maturity": self.maturity,
            "assumptions": list(self.assumptions),
            "assumption_records": list(self.assumption_records),
        }


class ConnectingRodModel:
    """Geometry-derived rod stress with Euler buckling and endurance-style fatigue margin."""

    MATURITY = ModelMaturity.M3

    def analyze(
        self,
        *,
        bore_mm: float,
        stroke_mm: float,
        tensile_load_n: float,
        compressive_load_n: float,
        section_type: RodSectionType | str = RodSectionType.I_BEAM,
        material_yield_mpa: float = 700.0,
        youngs_modulus_gpa: float | None = None,
        rod_length_mm: float | None = None,
        registry: AssumptionRegistry | None = None,
    ) -> ConnectingRodResult:
        reg = registry if registry is not None else AssumptionRegistry()
        st = (
            section_type
            if isinstance(section_type, RodSectionType)
            else RodSectionType(str(section_type))
        )
        bore_m = bore_mm / 1000.0
        stroke_m = stroke_mm / 1000.0

        if rod_length_mm is None:
            reg.record(
                id="rod_length_ratio",
                field="rod_length_stroke_ratio",
                assumed_value=ROD_LENGTH_STROKE_RATIO,
                rationale="Typical gasoline L/S ratio when rod length unknown",
                source_model="ConnectingRodModel",
                confidence="medium",
                category="geometry",
            )
            length_m = ROD_LENGTH_STROKE_RATIO * stroke_m
        else:
            length_m = rod_length_mm / 1000.0

        e_gpa = youngs_modulus_gpa if youngs_modulus_gpa is not None else STEEL_E_GPA
        if youngs_modulus_gpa is None:
            reg.record(
                id="rod_E",
                field="youngs_modulus_gpa",
                assumed_value=e_gpa,
                rationale="Default steel Young's modulus for buckling estimate",
                source_model="ConnectingRodModel",
                confidence="medium",
                category="material",
            )

        area, ixx = self._section_props(st, bore_m, reg)
        e_pa = e_gpa * 1e9
        # Euler: Pcr = π² E I / (K L)²
        reg.record(
            id="rod_end_fixity",
            field="end_fixity_factor_K",
            assumed_value=END_FIXITY_FACTOR,
            rationale="Pinned-pinned Euler column assumption",
            source_model="ConnectingRodModel",
            confidence="low",
            category="engineering",
        )
        p_cr = (math.pi**2) * e_pa * ixx / (END_FIXITY_FACTOR * length_m) ** 2

        tensile_stress = (tensile_load_n / area) / 1e6 if area else float("inf")
        compressive_stress = (compressive_load_n / area) / 1e6 if area else float("inf")
        buckling_margin = p_cr / compressive_load_n if compressive_load_n > 0 else float("inf")

        reg.record(
            id="rod_fatigue_derate",
            field="fatigue_derate",
            assumed_value=FATIGUE_DERATE,
            rationale="Endurance allowance as fraction of yield for margin ranking (not S-N)",
            source_model="ConnectingRodModel",
            confidence="low",
            category="engineering",
        )
        endurance = material_yield_mpa * FATIGUE_DERATE
        fatigue_margin = endurance / tensile_stress if tensile_stress > 0 else float("inf")

        return ConnectingRodResult(
            rod_length_mm=round(length_m * 1000.0, 2),
            section_type=st.value,
            cross_section_area_m2=area,
            second_moment_m4=ixx,
            tensile_load_n=tensile_load_n,
            compressive_load_n=compressive_load_n,
            maximum_tensile_stress_mpa=round(tensile_stress, 2),
            compressive_stress_mpa=round(compressive_stress, 2),
            euler_critical_load_n=round(p_cr, 1),
            buckling_margin=round(buckling_margin, 3),
            fatigue_margin=round(fatigue_margin, 3),
            confidence="medium",
            maturity=self.MATURITY.name,
            assumptions=reg.as_strings(),
            assumption_records=reg.as_dicts(),
        )

    def _section_props(
        self,
        section_type: RodSectionType,
        bore_m: float,
        reg: AssumptionRegistry,
    ) -> tuple[float, float]:
        """Approximate I/H-beam area and I about buckling axis from bore-scaled dimensions."""
        if section_type == RodSectionType.I_BEAM:
            tw = I_BEAM_WEB_THICKNESS_FRACTION * bore_m
            bf = I_BEAM_FLANGE_WIDTH_FRACTION * bore_m
            tf = I_BEAM_FLANGE_THICKNESS_FRACTION * bore_m
            d = I_BEAM_DEPTH_FRACTION * bore_m
            prefix = "i_beam"
            fracs = {
                "web_thickness_fraction": I_BEAM_WEB_THICKNESS_FRACTION,
                "flange_width_fraction": I_BEAM_FLANGE_WIDTH_FRACTION,
                "flange_thickness_fraction": I_BEAM_FLANGE_THICKNESS_FRACTION,
                "depth_fraction": I_BEAM_DEPTH_FRACTION,
            }
        else:
            tw = H_BEAM_WEB_THICKNESS_FRACTION * bore_m
            bf = H_BEAM_FLANGE_WIDTH_FRACTION * bore_m
            tf = H_BEAM_FLANGE_THICKNESS_FRACTION * bore_m
            d = H_BEAM_DEPTH_FRACTION * bore_m
            prefix = "h_beam"
            fracs = {
                "web_thickness_fraction": H_BEAM_WEB_THICKNESS_FRACTION,
                "flange_width_fraction": H_BEAM_FLANGE_WIDTH_FRACTION,
                "flange_thickness_fraction": H_BEAM_FLANGE_THICKNESS_FRACTION,
                "depth_fraction": H_BEAM_DEPTH_FRACTION,
            }

        for name, value in fracs.items():
            reg.record(
                id=f"rod_{prefix}_{name}",
                field=f"{prefix}_{name}",
                assumed_value=value,
                rationale=f"{section_type.value} section heuristic scaled to bore",
                source_model="ConnectingRodModel",
                confidence="low",
                category="geometry",
            )

        # Area ≈ web + two flanges
        area = tw * (d - 2 * tf) + 2 * bf * tf
        # I about major axis (strong axis for I-beam): flanges dominate
        i_web = tw * (d - 2 * tf) ** 3 / 12.0
        i_flange = 2 * (
            bf * tf**3 / 12.0 + bf * tf * ((d - tf) / 2.0) ** 2
        )
        ixx = i_web + i_flange
        return area, ixx
