"""Engine cycle estimate — explicit BMEP / efficiency bands with provenance.

Numerical band endpoints match PhysicsEngine historical constants so baseline
displacement geometry is unchanged. Every value carries source provenance.
No naked constants.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from core.epistemology.assumption_registry import AssumptionRegistry
from core.verification.model_maturity import ModelMaturity

ValueSource = Literal["known", "assumed", "empirical", "derived"]

# Historical PE band endpoints — preserved for baseline invariance.
NA_BMEP_BAR = (12.0, 16.0)  # 1.2–1.6 MPa
BOOSTED_BMEP_BAR = (16.0, 25.0)  # 1.6–2.5 MPa
THERMAL_EFFICIENCY = (0.28, 0.34)
MECHANICAL_EFFICIENCY = (0.85, 0.92)
VOLUMETRIC_EFFICIENCY_NA = (0.85, 1.05)
VOLUMETRIC_EFFICIENCY_BOOSTED = (0.95, 1.25)


@dataclass(frozen=True)
class ProvenancedValue:
    value: float | tuple[float, float]
    unit: str
    source: ValueSource
    reference: str | None = None
    confidence: str = "medium"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EngineCycleEstimate:
    displacement_l: ProvenancedValue | None = None
    bmep: ProvenancedValue | None = None
    volumetric_efficiency: ProvenancedValue | None = None
    thermal_efficiency: ProvenancedValue | None = None
    mechanical_efficiency: ProvenancedValue | None = None
    confidence: str = "medium"
    provenance: dict[str, Any] = field(default_factory=dict)
    assumptions: list[str] = field(default_factory=list)
    maturity: str = "M2"

    def to_dict(self) -> dict[str, Any]:
        return {
            "displacement_l": None if self.displacement_l is None else self.displacement_l.to_dict(),
            "bmep": None if self.bmep is None else self.bmep.to_dict(),
            "volumetric_efficiency": None
            if self.volumetric_efficiency is None
            else self.volumetric_efficiency.to_dict(),
            "thermal_efficiency": None
            if self.thermal_efficiency is None
            else self.thermal_efficiency.to_dict(),
            "mechanical_efficiency": None
            if self.mechanical_efficiency is None
            else self.mechanical_efficiency.to_dict(),
            "confidence": self.confidence,
            "provenance": dict(self.provenance),
            "assumptions": list(self.assumptions),
            "maturity": self.maturity,
        }


class EngineCycleModel:
    """Cycle / BMEP sizing assumptions made explicit and auditable."""

    MATURITY = ModelMaturity.M2

    def estimate(
        self,
        *,
        aspiration: str | None,
        horsepower: float | None = None,
        rpm: float | None = None,
        displacement_l: float | None = None,
        registry: AssumptionRegistry | None = None,
    ) -> EngineCycleEstimate:
        reg = registry if registry is not None else AssumptionRegistry()
        boosted = bool(aspiration) and (
            "turbo" in aspiration.lower() or "super" in aspiration.lower()
        )
        category = "boosted" if boosted else ("na" if aspiration else "unknown")

        if boosted:
            bmep_bar = BOOSTED_BMEP_BAR
            ve = VOLUMETRIC_EFFICIENCY_BOOSTED
            bmep_ref = "boosted / forced-induction high-performance gasoline BMEP band"
        else:
            bmep_bar = NA_BMEP_BAR
            ve = VOLUMETRIC_EFFICIENCY_NA
            bmep_ref = "naturally aspirated high-performance gasoline BMEP band"

        if aspiration is None:
            # Still emit structure but mark unknown — PE will skip displacement sizing.
            result = EngineCycleEstimate(
                confidence="low",
                provenance={"aspiration": "UNKNOWN", "category": "unknown"},
                maturity=self.MATURITY.name,
            )
            reg.record(
                id="cycle_aspiration_unknown",
                field="aspiration",
                assumed_value=None,
                rationale="Aspiration unresolved — BMEP band not selected",
                source_model="EngineCycleModel",
                confidence="low",
                category="engineering",
            )
            result.assumptions = reg.as_strings()
            return result

        bmep_pa = (bmep_bar[0] * 1e5, bmep_bar[1] * 1e5)
        for name, value, why in (
            ("bmep_bar_low", bmep_bar[0], bmep_ref),
            ("bmep_bar_high", bmep_bar[1], bmep_ref),
            ("volumetric_efficiency_low", ve[0], f"{category} volumetric efficiency band"),
            ("volumetric_efficiency_high", ve[1], f"{category} volumetric efficiency band"),
            ("thermal_efficiency_low", THERMAL_EFFICIENCY[0], "brake thermal efficiency band"),
            ("thermal_efficiency_high", THERMAL_EFFICIENCY[1], "brake thermal efficiency band"),
            ("mechanical_efficiency_low", MECHANICAL_EFFICIENCY[0], "mechanical efficiency band"),
            ("mechanical_efficiency_high", MECHANICAL_EFFICIENCY[1], "mechanical efficiency band"),
        ):
            reg.record(
                id=f"cycle_{name}",
                field=name,
                assumed_value=value,
                rationale=why,
                source_model="EngineCycleModel",
                confidence="medium",
                category="engineering",
            )

        disp: ProvenancedValue | None
        if displacement_l is not None:
            disp = ProvenancedValue(
                value=float(displacement_l),
                unit="L",
                source="known",
                reference="explicit requirement / published geometry",
                confidence="high",
            )
        elif horsepower is not None and rpm is not None:
            # Same identity PE uses: V[L] = P[W]*120/(BMEP[Pa]*N)*1000
            power_w = horsepower * 0.745699872 * 1000.0
            high_l = power_w * 120.0 / (bmep_pa[0] * rpm) * 1000.0
            low_l = power_w * 120.0 / (bmep_pa[1] * rpm) * 1000.0
            disp = ProvenancedValue(
                value=(low_l, high_l),
                unit="L",
                source="derived",
                reference="four-stroke BMEP power identity with empirical BMEP band",
                confidence="medium",
            )
        else:
            disp = None

        result = EngineCycleEstimate(
            displacement_l=disp,
            bmep=ProvenancedValue(
                value=bmep_bar,
                unit="bar",
                source="empirical",
                reference=bmep_ref,
                confidence="medium",
            ),
            volumetric_efficiency=ProvenancedValue(
                value=ve,
                unit="fraction",
                source="empirical",
                reference=f"{category} VE band",
                confidence="low",
            ),
            thermal_efficiency=ProvenancedValue(
                value=THERMAL_EFFICIENCY,
                unit="fraction",
                source="empirical",
                reference="brake thermal efficiency band for gasoline ICE",
                confidence="medium",
            ),
            mechanical_efficiency=ProvenancedValue(
                value=MECHANICAL_EFFICIENCY,
                unit="fraction",
                source="assumed",
                reference="typical gasoline mechanical efficiency band",
                confidence="low",
            ),
            confidence="medium",
            provenance={
                "aspiration": aspiration,
                "category": category,
                "bmep_pa": bmep_pa,
                "model": "EngineCycleModel",
                "note": "Bands are empirical catalog floors — not measured BSFC maps.",
            },
            assumptions=reg.as_strings(),
            maturity=self.MATURITY.name,
        )
        return result

    def bmep_range_pa(self, aspiration: str) -> tuple[float, float]:
        """Pa endpoints identical to PhysicsEngine historical constants."""
        est = self.estimate(aspiration=aspiration)
        assert est.provenance.get("bmep_pa") is not None
        low, high = est.provenance["bmep_pa"]
        return float(low), float(high)
