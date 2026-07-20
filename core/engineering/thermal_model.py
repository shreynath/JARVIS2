"""Thermal engineering model — calculated heat rejection vs empirical combustion temperature.

Does not remove existing PE empirical mappings; wraps them with explicit status/maturity.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from core.epistemology.assumption_registry import AssumptionRegistry
from core.verification.model_maturity import ModelMaturity

HP_TO_KW = 0.745699872
# Preserve PE historical bands.
BRAKE_THERMAL_EFFICIENCY_RANGE = (0.28, 0.34)
COOLANT_HEAT_FRACTION_RANGE = (0.25, 0.35)


@dataclass(frozen=True)
class ThermalQuantity:
    value: float | tuple[float, float]
    unit: str
    kind: Literal["calculated", "empirical"]
    validation_status: str
    maturity: str
    confidence: str
    formula: str | None = None
    assumptions: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        raw = asdict(self)
        raw["assumptions"] = list(self.assumptions)
        return raw


@dataclass
class ThermalModelResult:
    heat_rejection_kw: ThermalQuantity | None = None
    combustion_side_temperature_c: ThermalQuantity | None = None
    assumption_records: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "heat_rejection_kw": None
            if self.heat_rejection_kw is None
            else self.heat_rejection_kw.to_dict(),
            "combustion_side_temperature_c": None
            if self.combustion_side_temperature_c is None
            else self.combustion_side_temperature_c.to_dict(),
            "assumption_records": list(self.assumption_records),
        }


class ThermalModel:
    """Separates energy-split (calculated) from combustion-side temperature (empirical)."""

    HEAT_MATURITY = ModelMaturity.M3
    TEMP_MATURITY = ModelMaturity.M3

    def analyze(
        self,
        *,
        horsepower: float,
        cooling_heat_kw_for_temp: float | None = None,
        registry: AssumptionRegistry | None = None,
    ) -> ThermalModelResult:
        reg = registry if registry is not None else AssumptionRegistry()
        brake_kw = horsepower * HP_TO_KW
        values = [
            brake_kw / eta * frac
            for eta in BRAKE_THERMAL_EFFICIENCY_RANGE
            for frac in COOLANT_HEAT_FRACTION_RANGE
        ]
        heat_range = (min(values), max(values))
        for name, value, why in (
            ("eta_th_low", BRAKE_THERMAL_EFFICIENCY_RANGE[0], "brake thermal efficiency band"),
            ("eta_th_high", BRAKE_THERMAL_EFFICIENCY_RANGE[1], "brake thermal efficiency band"),
            ("cool_frac_low", COOLANT_HEAT_FRACTION_RANGE[0], "coolant heat fraction band"),
            ("cool_frac_high", COOLANT_HEAT_FRACTION_RANGE[1], "coolant heat fraction band"),
        ):
            reg.record(
                id=f"thermal_{name}",
                field=name,
                assumed_value=value,
                rationale=why,
                source_model="ThermalModel",
                confidence="medium",
                category="engineering",
            )

        heat = ThermalQuantity(
            value=(round(heat_range[0], 1), round(heat_range[1], 1)),
            unit="kW",
            kind="calculated",
            validation_status="FORMULA_VERIFIED_PARAMETERS_ASSUMED",
            maturity=self.HEAT_MATURITY.name,
            confidence="medium",
            formula="Q_cool = P_brake / η_th * f_cool",
            assumptions=tuple(reg.as_strings()),
        )

        # Preserve PhysicsEngine historical mapping: use upper heat bound when unbound.
        q_for_temp = (
            float(cooling_heat_kw_for_temp)
            if cooling_heat_kw_for_temp is not None
            else heat_range[1]
        )
        temp = round(180.0 + min(120.0, q_for_temp / 8.0), 1)
        reg.record(
            id="thermal_combustion_map",
            field="combustion_temp_empirical_map",
            assumed_value="T ≈ 180 + min(120, Q_cool_kw / 8)",
            rationale="Internal empirical combustion-side temperature map — UNVALIDATED vs measured metal temps",
            source_model="ThermalModel",
            confidence="low",
            category="engineering",
        )
        combustion = ThermalQuantity(
            value=temp,
            unit="C",
            kind="empirical",
            validation_status="UNVALIDATED",
            maturity=self.TEMP_MATURITY.name,
            confidence="low",
            formula="T ≈ 180 + min(120, Q_cool_kw / 8)",
            assumptions=("Empirical map — not peer-reviewed / not CFD",),
        )
        return ThermalModelResult(
            heat_rejection_kw=heat,
            combustion_side_temperature_c=combustion,
            assumption_records=reg.as_dicts(),
        )
