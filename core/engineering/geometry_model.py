"""Geometry engineering model — closed-form cylinder / crank geometry.

Isolated from evaluator and CandidateDesign. Emits provenance on every field.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from core.epistemology.assumption_registry import AssumptionRegistry
from core.verification.model_maturity import ModelMaturity


@dataclass(frozen=True)
class GeometryQuantity:
    value: float
    unit: str
    source: str
    calculation_method: str
    maturity: str
    confidence: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "unit": self.unit,
            "geometry_source": self.source,
            "calculation_method": self.calculation_method,
            "maturity": self.maturity,
            "confidence": self.confidence,
        }


@dataclass
class GeometryModelResult:
    bore_mm: GeometryQuantity | None = None
    stroke_mm: GeometryQuantity | None = None
    cylinder_count: GeometryQuantity | None = None
    displacement_l: GeometryQuantity | None = None
    crank_radius_mm: GeometryQuantity | None = None
    piston_area_mm2: GeometryQuantity | None = None
    cylinder_volume_l: GeometryQuantity | None = None
    assumptions: list[str] = field(default_factory=list)
    registry: AssumptionRegistry | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        for key in (
            "bore_mm",
            "stroke_mm",
            "cylinder_count",
            "displacement_l",
            "crank_radius_mm",
            "piston_area_mm2",
            "cylinder_volume_l",
        ):
            q = getattr(self, key)
            if q is not None:
                payload[key] = q.to_dict()
        payload["assumptions"] = list(self.assumptions)
        if self.registry is not None:
            payload["assumption_records"] = self.registry.as_dicts()
        return payload


def _q(
    value: float,
    unit: str,
    source: str,
    method: str,
    *,
    maturity: str = "M2",
    confidence: str = "high",
) -> GeometryQuantity:
    return GeometryQuantity(
        value=value,
        unit=unit,
        source=source,
        calculation_method=method,
        maturity=maturity,
        confidence=confidence,
    )


class GeometryModel:
    """Analytical geometry identities for ICE packaging / loads."""

    MATURITY = ModelMaturity.M2

    def resolve(
        self,
        *,
        bore_mm: float | None = None,
        stroke_mm: float | None = None,
        cylinder_count: float | int | None = None,
        displacement_l: float | None = None,
        bore_stroke_ratio: float | None = None,
        registry: AssumptionRegistry | None = None,
    ) -> GeometryModelResult:
        reg = registry if registry is not None else AssumptionRegistry()
        result = GeometryModelResult(registry=reg)

        cyl = float(cylinder_count) if cylinder_count is not None else None
        if cyl is not None:
            result.cylinder_count = _q(
                cyl, "count", "explicit_input", "known_parameter", confidence="high"
            )

        # Stroke path
        if stroke_mm is not None:
            result.stroke_mm = _q(
                float(stroke_mm), "mm", "explicit_input", "known_parameter", confidence="high"
            )
        elif displacement_l is not None and cyl and bore_stroke_ratio:
            per_cyl_m3 = (displacement_l / 1000.0) / cyl
            stroke_m = (4.0 * per_cyl_m3 / (math.pi * bore_stroke_ratio**2)) ** (1.0 / 3.0)
            reg.record(
                id="geom_bore_stroke_ratio",
                field="bore_stroke_ratio",
                assumed_value=bore_stroke_ratio,
                rationale="Bore/stroke ratio used to close geometry when stroke unknown",
                source_model="GeometryModel",
                confidence="medium",
                category="geometry",
            )
            result.stroke_mm = _q(
                stroke_m * 1000.0,
                "mm",
                "derived_from_displacement_and_ratio",
                "stroke = cbrt(4*V_cyl/(π*λ²))",
                maturity="M2",
                confidence="medium",
            )
        elif displacement_l is not None and cyl and bore_mm is not None:
            per_cyl_m3 = (displacement_l / 1000.0) / cyl
            bore_m = bore_mm / 1000.0
            stroke_m = per_cyl_m3 / (math.pi * bore_m**2 / 4.0)
            result.stroke_mm = _q(
                stroke_m * 1000.0,
                "mm",
                "derived_from_displacement_and_bore",
                "stroke = V_cyl / (π/4 * bore²)",
                maturity="M2",
                confidence="high",
            )

        # Bore path
        if bore_mm is not None:
            result.bore_mm = _q(
                float(bore_mm), "mm", "explicit_input", "known_parameter", confidence="high"
            )
        elif result.stroke_mm is not None and bore_stroke_ratio is not None:
            if stroke_mm is None:
                reg.record(
                    id="geom_bore_from_ratio",
                    field="bore_stroke_ratio",
                    assumed_value=bore_stroke_ratio,
                    rationale="Bore derived as λ * stroke",
                    source_model="GeometryModel",
                    confidence="medium",
                    category="geometry",
                )
            result.bore_mm = _q(
                result.stroke_mm.value * bore_stroke_ratio,
                "mm",
                "derived_from_stroke_and_ratio",
                "bore = λ * stroke",
                maturity="M2",
                confidence="medium",
            )
        elif displacement_l is not None and cyl and result.stroke_mm is not None:
            per_cyl_m3 = (displacement_l / 1000.0) / cyl
            stroke_m = result.stroke_mm.value / 1000.0
            bore_m = math.sqrt(4.0 * per_cyl_m3 / (math.pi * stroke_m))
            result.bore_mm = _q(
                bore_m * 1000.0,
                "mm",
                "derived_from_displacement_and_stroke",
                "bore = sqrt(4*V_cyl/(π*stroke))",
                maturity="M2",
                confidence="high",
            )

        if displacement_l is not None:
            result.displacement_l = _q(
                float(displacement_l),
                "L",
                "explicit_input" if displacement_l else "unknown",
                "known_parameter",
                confidence="high",
            )
        elif result.bore_mm and result.stroke_mm and cyl:
            bore_m = result.bore_mm.value / 1000.0
            stroke_m = result.stroke_mm.value / 1000.0
            disp_m3 = cyl * (math.pi / 4.0) * bore_m**2 * stroke_m
            result.displacement_l = _q(
                disp_m3 * 1000.0,
                "L",
                "derived_from_bore_stroke_cylinders",
                "V = n * (π/4) * bore² * stroke",
                maturity="M2",
                confidence="high",
            )

        if result.stroke_mm is not None:
            result.crank_radius_mm = _q(
                result.stroke_mm.value / 2.0,
                "mm",
                "derived_from_stroke",
                "crank_radius = stroke / 2",
                maturity="M2",
                confidence="high",
            )

        if result.bore_mm is not None:
            bore_m = result.bore_mm.value / 1000.0
            area_m2 = math.pi * bore_m**2 / 4.0
            result.piston_area_mm2 = _q(
                area_m2 * 1e6,
                "mm^2",
                "derived_from_bore",
                "A = π/4 * bore²",
                maturity="M2",
                confidence="high",
            )

        if result.displacement_l is not None and cyl:
            result.cylinder_volume_l = _q(
                result.displacement_l.value / cyl,
                "L",
                "derived_from_displacement",
                "V_cyl = V_total / n",
                maturity="M2",
                confidence="high",
            )

        result.assumptions = reg.as_strings()
        return result
