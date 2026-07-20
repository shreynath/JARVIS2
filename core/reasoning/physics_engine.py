"""Physics engine — deterministic quantitative engineering calculations."""

from __future__ import annotations

import math
from typing import Any

from pydantic import BaseModel, Field

from core.epistemology import KnowledgeState
from core.epistemology.assumption_registry import AssumptionRegistry
from core.epistemology.input_requirement import (
    InputRequirement,
    InputState,
    MissingEngineeringInputError,
)
from core.engineering.connecting_rod_model import ConnectingRodModel, RodSectionType
from core.engineering.engine_cycle_model import EngineCycleModel
from core.engineering.geometry_model import GeometryModel
from core.engineering.reciprocating_mass import ReciprocatingMassModel
from core.engineering.thermal_model import ThermalModel
from core.ir.constraint import Constraint, ConstraintPriority, ConstraintSeverity
from core.ir.requirement_spec import RequirementSpecification
from core.verification.model_registry import maturity_for_calc
from knowledge.equations.catalog import provenance_for_calc

HP_TO_KW = 0.745699872
KW_TORQUE_CONSTANT = 9549.0
FOUR_STROKE_POWER_FACTOR = 120.0
NA_BMEP_RANGE_PA = (1.2e6, 1.6e6)
BOOSTED_BMEP_RANGE_PA = (1.6e6, 2.5e6)
BRAKE_THERMAL_EFFICIENCY_RANGE = (0.28, 0.34)
COOLANT_HEAT_FRACTION_RANGE = (0.25, 0.35)
PEAK_PRESSURE_TO_BMEP_RANGE = (8.0, 12.0)
BORE_STROKE_RATIO_RANGE = (1.0, 1.25)
PISTON_MASS_PER_DISPLACEMENT_KG_PER_L = (0.9, 1.3)
ROD_SECTION_AREA_M2_RANGE = (3.5e-4, 5.5e-4)
DEFAULT_DISPLACEMENT_PER_CYLINDER_L_RANGE = (0.35, 0.65)


class PhysicsCalculation(BaseModel):
    """A derived physics quantity with traceability and uncertainty."""

    id: str
    name: str
    formula: str
    inputs: dict[str, float | int | str] = Field(default_factory=dict)
    result: float | None = None
    value_range: tuple[float, float] | None = None
    unit: str = ""
    status: str = "computed"
    missing_inputs: list[str] = Field(default_factory=list)
    reason: str = ""
    method: str = ""
    assumptions: list[str] = Field(default_factory=list)
    dependency_ids: list[str] = Field(default_factory=list)
    knowledge_state: KnowledgeState = KnowledgeState.DERIVED
    confidence: str = "medium"
    assessment: str = ""
    passes: bool | None = None
    # Phase 4 provenance — no anonymous formulas.
    equation_id: str | None = None
    equation_source: str | None = None
    engineering_reference: dict | None = None
    validation_status: str | None = None
    # Phase 4.5 — model sophistication (orthogonal to confidence / validation_status).
    model_maturity: str | None = None


UNKNOWN_INPUT = "unknown"


def _sanitize_calc_inputs(inputs: dict[str, Any]) -> dict[str, float | int | str]:
    """Coerce calculation inputs to float|int|str; never leave required values as None.

    Call sites historically stuffed Optional values (e.g. bmep_source) into the inputs
    dict. Pydantic rejects None for ``dict[str, float | int | str]``. Unknowns are
    recorded as the explicit sentinel ``\"unknown\"`` so validation reports can surface
    missing provenance instead of crashing.
    """
    cleaned: dict[str, float | int | str] = {}
    for key, value in inputs.items():
        if value is None:
            cleaned[key] = UNKNOWN_INPUT
        elif isinstance(value, bool):
            # bool is a subclass of int; keep as explicit 0/1 for schema stability
            cleaned[key] = int(value)
        elif isinstance(value, (float, int, str)):
            cleaned[key] = value
        else:
            cleaned[key] = str(value)
    return cleaned


def _attach_provenance(calc_id: str, kwargs: dict) -> dict:
    """Merge equation provenance into PhysicsCalculation constructor kwargs."""
    prov = provenance_for_calc(calc_id)
    kwargs.setdefault("equation_id", prov.get("equation_id"))
    kwargs.setdefault("equation_source", prov.get("equation_source"))
    kwargs.setdefault("engineering_reference", prov.get("engineering_reference"))
    kwargs.setdefault("validation_status", prov.get("validation_status"))
    maturity = maturity_for_calc(calc_id)
    if maturity is not None:
        kwargs.setdefault("model_maturity", maturity.name)
    return kwargs


def make_physics_calculation(**kwargs) -> PhysicsCalculation:
    """Construct a PhysicsCalculation with mandatory equation provenance.

    Sanitizes ``inputs`` so None never reaches the Pydantic model — unknown values
    become the string sentinel ``\"unknown\"``.
    """
    calc_id = str(kwargs["id"])
    raw_inputs = kwargs.get("inputs")
    if isinstance(raw_inputs, dict):
        kwargs["inputs"] = _sanitize_calc_inputs(raw_inputs)
    return PhysicsCalculation(**_attach_provenance(calc_id, kwargs))


class PhysicsAnalysis(BaseModel):
    """Quantitative physics layer output."""

    calculations: list[PhysicsCalculation] = Field(default_factory=list)
    constraints: list[Constraint] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    unresolved_inputs: list[str] = Field(default_factory=list)
    input_requirements: list[dict[str, str | float | int | None]] = Field(default_factory=list)
    # Single source of truth: keys bind to calculation IDs (+ optional range mode).
    # operating_conditions is ALWAYS derived from these refs — never independently populated.
    operating_condition_refs: dict[str, str] = Field(default_factory=dict)
    operating_condition_modes: dict[str, str] = Field(default_factory=dict)  # result | high | low
    # Phase 5.0 — isolated engineering-model attachments (provenance only; not operating inputs).
    engineering_attachments: dict[str, Any] = Field(default_factory=dict)

    def by_id(self, calculation_id: str) -> PhysicsCalculation | None:
        return next((c for c in self.calculations if c.id == calculation_id), None)

    def resolve_operating(self, key: str) -> float | int | str | bool | None:
        """Resolve an operating condition exclusively from its referenced calculation."""
        calc_id = self.operating_condition_refs.get(key)
        if not calc_id:
            return None
        return self._value_from_calc(calc_id, self.operating_condition_modes.get(key, "result"))

    @property
    def operating_conditions(self) -> dict[str, float | int | str | bool | None]:
        """Derived view — every value is resolved from operating_condition_refs."""
        return {key: self.resolve_operating(key) for key in self.operating_condition_refs}

    def bind_operating(self, key: str, calculation_id: str, *, use_high: bool = False, use_low: bool = False) -> None:
        """Bind an operating-condition key to a calculation ID (no value copy)."""
        self.operating_condition_refs[key] = calculation_id
        if use_high:
            self.operating_condition_modes[key] = "high"
        elif use_low:
            self.operating_condition_modes[key] = "low"
        else:
            self.operating_condition_modes[key] = "result"

    def _value_from_calc(self, calculation_id: str, mode: str) -> float | int | str | bool | None:
        calc = self.by_id(calculation_id)
        if calc is None:
            return None
        if mode == "high" and calc.value_range is not None:
            return max(calc.value_range)
        if mode == "low" and calc.value_range is not None:
            return min(calc.value_range)
        return calc.result

    def model_dump(self, **kwargs):  # type: ignore[override]
        data = super().model_dump(**kwargs)
        # Always emit operating_conditions as a derived resolution of refs.
        data["operating_conditions"] = {
            key: self.resolve_operating(key) for key in self.operating_condition_refs
        }
        return data


class PhysicsEngine:
    """Compute engineering quantities from requirement parameters without lookup rules."""

    def analyze(
        self,
        requirement_spec: RequirementSpecification,
        stroke_mm: float | None = None,
    ) -> PhysicsAnalysis:
        params = requirement_spec.resolved_parameters
        if not params:
            raise MissingEngineeringInputError(
                "resolved_parameters",
                "PhysicsEngine.analyze requires resolved parameters; empty input must not be defaulted.",
            )

        analysis = PhysicsAnalysis()
        input_reqs = self._resolve_input_requirements(params)
        analysis.input_requirements = [req.as_dict() for req in input_reqs]

        max_rpm = self._float_param(params, "max_rpm")
        target_hp = self._float_param(params, "target_horsepower")
        displacement_l = self._float_param(params, "displacement_l")
        cylinder_count = self._float_param(params, "cylinder_count")
        aspiration_req = next((r for r in input_reqs if r.name == "aspiration"), None)
        aspiration = (
            str(aspiration_req.value)
            if aspiration_req is not None and aspiration_req.state != InputState.UNKNOWN and aspiration_req.value
            else None
        )

        for key in ("target_horsepower", "max_rpm", "displacement_l", "cylinder_count", "aspiration"):
            if key not in params:
                analysis.unresolved_inputs.append(key)

        if target_hp and max_rpm:
            power_kw = target_hp * HP_TO_KW
            torque_nm = power_kw * KW_TORQUE_CONSTANT / max_rpm
            analysis.calculations.append(
                make_physics_calculation(
                    id="calc_torque",
                    name="Torque",
                    formula="torque_nm = power_kw * 9549 / rpm",
                    inputs={"horsepower": target_hp, "power_kw": power_kw, "rpm": max_rpm},
                    result=round(torque_nm, 1),
                    value_range=(round(torque_nm, 1), round(torque_nm, 1)),
                    unit="Nm",
                    method="Converted horsepower to kW, then applied rotational power relationship.",
                    assumptions=[],
                    dependency_ids=[],
                    knowledge_state=KnowledgeState.DERIVED,
                    confidence="high",
                    assessment="Torque derived directly from specified power and RPM.",
                    passes=True,
                )
            )
            analysis.bind_operating("torque_nm", "calc_torque")
        else:
            self._add_skipped(
                analysis,
                calculation_id="calc_torque",
                name="Torque",
                formula="torque_nm = power_kw * 9549 / rpm",
                missing_inputs=[
                    key for key, value in (("target_horsepower", target_hp), ("max_rpm", max_rpm)) if value is None
                ],
                reason="Torque = Power * 9549 / RPM requires resolved horsepower and RPM.",
            )

        displacement_range = self._displacement_range(
            target_hp=target_hp,
            max_rpm=max_rpm,
            displacement_l=displacement_l,
            aspiration=aspiration,
            cylinder_count=cylinder_count,
        )
        if displacement_range:
            displacement_depends_on_power = bool(target_hp and max_rpm and aspiration) or bool(displacement_l)
            cycle = (
                EngineCycleModel().estimate(
                    aspiration=aspiration,
                    horsepower=target_hp,
                    rpm=max_rpm,
                    displacement_l=displacement_l,
                )
                if aspiration
                else None
            )
            if cycle is not None:
                analysis.engineering_attachments["engine_cycle"] = cycle.to_dict()
            bmep = self._bmep_range(aspiration) if aspiration else (0.0, 0.0)
            cycle_assumptions = list(cycle.assumptions) if cycle is not None else []
            analysis.calculations.append(
                make_physics_calculation(
                    id="calc_displacement",
                    name="Displacement estimate",
                    formula=(
                        "displacement_m3 = brake_power_w * 120 / (bmep_pa * rpm)"
                        if displacement_depends_on_power
                        else "displacement_l = cylinder_count * representative_per_cylinder_displacement"
                    ),
                    inputs={
                        "horsepower": target_hp or 0.0,
                        "rpm": max_rpm or 0.0,
                        "bmep_low_pa": bmep[0],
                        "bmep_high_pa": bmep[1],
                        "cylinder_count": cylinder_count or 0.0,
                        "cycle_model": "EngineCycleModel",
                        "bmep_source": (
                            UNKNOWN_INPUT
                            if cycle is None or cycle.bmep is None
                            else cycle.bmep.source
                        ),
                    },
                    result=round(sum(displacement_range) / 2, 2),
                    value_range=(round(displacement_range[0], 2), round(displacement_range[1], 2)),
                    unit="L",
                    method=(
                        "Used four-stroke BMEP power relation via EngineCycleModel empirical bands. "
                        "If displacement was provided, the range collapses to that known input."
                        if displacement_depends_on_power
                        else "Used cylinder count with a representative per-cylinder displacement range so RPM-only physics can proceed."
                    ),
                    assumptions=(
                        []
                        if displacement_l
                        else (
                            cycle_assumptions
                            or (
                                [f"BMEP range inferred from aspiration type: {aspiration}"]
                                if target_hp and max_rpm and aspiration
                                else [
                                    "Displacement not provided; estimated from cylinder count "
                                    "and representative per-cylinder displacement range."
                                ]
                            )
                        )
                    ),
                    dependency_ids=["calc_torque"] if target_hp and max_rpm else [],
                    knowledge_state=KnowledgeState.KNOWN if displacement_l else KnowledgeState.ASSUMED,
                    confidence="high" if displacement_l else "medium",
                    assessment="Feasible displacement range derived from power, RPM, BMEP, and aspiration.",
                    passes=True,
                )
            )
            analysis.bind_operating("displacement_l_low", "calc_displacement", use_low=True)
            analysis.bind_operating("displacement_l_high", "calc_displacement", use_high=True)
        else:
            missing = ["target_horsepower", "displacement_l", "cylinder_count"]
            if target_hp and max_rpm and not aspiration:
                missing = ["aspiration"]
            self._add_skipped(
                analysis,
                calculation_id="calc_displacement",
                name="Displacement estimate",
                formula="displacement_m3 = brake_power_w * 120 / (bmep_pa * rpm)",
                missing_inputs=missing,
                reason=(
                    "Displacement requires known aspiration for BMEP derivation (no silent default), "
                    if target_hp and max_rpm and not aspiration
                    else "Displacement requires a known displacement, power/RPM for BMEP derivation, "
                    "or cylinder count for a representative geometry estimate."
                ),
            )

        stroke_range = self._stroke_range(
            displacement_l=displacement_range,
            cylinder_count=cylinder_count,
            stroke_mm=stroke_mm,
        )
        if stroke_range:
            assumptions = [] if stroke_mm else [
                "Stroke estimated from displacement per cylinder and bore/stroke ratio range."
            ]
            analysis.calculations.append(
                make_physics_calculation(
                    id="calc_stroke",
                    name="Stroke estimate",
                    formula="stroke = cubic_root(4 * displacement_per_cylinder / (pi * bore_stroke_ratio^2))",
                    inputs={
                        "cylinder_count": cylinder_count or 0.0,
                        "bore_stroke_ratio_low": BORE_STROKE_RATIO_RANGE[0],
                        "bore_stroke_ratio_high": BORE_STROKE_RATIO_RANGE[1],
                    },
                    result=round(sum(stroke_range) / 2, 1),
                    value_range=(round(stroke_range[0], 1), round(stroke_range[1], 1)),
                    unit="mm",
                    method="Derived geometry from per-cylinder swept volume and plausible bore/stroke ratios.",
                    assumptions=assumptions,
                    dependency_ids=["calc_displacement"],
                    knowledge_state=KnowledgeState.KNOWN if stroke_mm else KnowledgeState.ASSUMED,
                    confidence="high" if stroke_mm else "medium",
                    assessment="Geometry estimate for downstream piston-speed and inertia calculations.",
                    passes=True,
                )
            )
        else:
            self._add_skipped(
                analysis,
                calculation_id="calc_stroke",
                name="Stroke estimate",
                formula="stroke = cubic_root(4 * displacement_per_cylinder / (pi * bore_stroke_ratio^2))",
                missing_inputs=["displacement_l", "cylinder_count"],
                reason="Stroke estimate requires displacement per cylinder or a cylinder-count-based displacement estimate.",
            )

        if max_rpm and stroke_range:
            mps_range = tuple(2 * (stroke / 1000.0) * max_rpm / 60.0 for stroke in stroke_range)
            assessment = self._piston_speed_assessment(max(mps_range))
            passes = max(mps_range) <= 26.0
            analysis.calculations.append(
                make_physics_calculation(
                    id="calc_mean_piston_speed",
                    name="Mean piston speed",
                    formula="Vp = 2 × stroke × RPM / 60",
                    inputs={"stroke_mm_low": stroke_range[0], "stroke_mm_high": stroke_range[1], "max_rpm": max_rpm},
                    result=round(sum(mps_range) / 2, 2),
                    value_range=(round(min(mps_range), 2), round(max(mps_range), 2)),
                    unit="m/s",
                    method="Calculated from estimated stroke range and specified RPM.",
                    assumptions=[] if stroke_mm else ["Stroke is estimated, so piston speed is a range."],
                    dependency_ids=["calc_stroke"],
                    knowledge_state=KnowledgeState.DERIVED,
                    confidence="medium" if not stroke_mm else "high",
                    assessment=assessment,
                    passes=passes,
                )
            )
            analysis.bind_operating("mean_piston_speed_m_s", "calc_mean_piston_speed")
            analysis.bind_operating("mean_piston_speed_m_s_high", "calc_mean_piston_speed", use_high=True)
            if not passes:
                analysis.warnings.append(
                    "Mean piston speed exceeds the 26 m/s hard limit "
                    "(see calculation calc_mean_piston_speed for value_range)."
                )
        else:
            self._add_skipped(
                analysis,
                calculation_id="calc_mean_piston_speed",
                name="Mean piston speed",
                formula="Vp = 2 × stroke × RPM / 60",
                missing_inputs=[
                    key for key, value in (("max_rpm", max_rpm), ("stroke_estimate", stroke_range)) if value is None
                ],
                reason="Mean piston speed requires RPM and either known or estimated stroke.",
            )

        acceleration_range: tuple[float, float] | None = None
        if max_rpm and stroke_range:
            acceleration_range = tuple((stroke / 1000.0 / 2.0) * (2.0 * math.pi * max_rpm / 60.0) ** 2 for stroke in stroke_range)
            analysis.calculations.append(
                make_physics_calculation(
                    id="calc_piston_acceleration",
                    name="Peak piston acceleration estimate",
                    formula="a_peak = crank_radius * angular_velocity^2",
                    inputs={"stroke_mm_low": stroke_range[0], "stroke_mm_high": stroke_range[1], "rpm": max_rpm},
                    result=round(sum(acceleration_range) / 2, 0),
                    value_range=(round(min(acceleration_range), 0), round(max(acceleration_range), 0)),
                    unit="m/s^2",
                    method="Slider-crank first-order peak acceleration estimate.",
                    assumptions=["Rod ratio and secondary acceleration terms are not modeled."],
                    dependency_ids=["calc_stroke"],
                    knowledge_state=KnowledgeState.DERIVED,
                    confidence="medium",
                    assessment="Acceleration used as the driver for inertial rod and bearing loading.",
                    passes=True,
                )
            )
            analysis.bind_operating("peak_piston_acceleration_m_s2", "calc_piston_acceleration", use_high=True)
        else:
            self._add_skipped(
                analysis,
                calculation_id="calc_piston_acceleration",
                name="Peak piston acceleration estimate",
                formula="a_peak = crank_radius * angular_velocity^2",
                missing_inputs=[
                    key for key, value in (("max_rpm", max_rpm), ("stroke_estimate", stroke_range)) if value is None
                ],
                reason="Piston acceleration requires RPM and stroke.",
            )

        if acceleration_range and stroke_range and displacement_range and cylinder_count and aspiration:
            force_range, stress_range, rod_meta = self._reciprocating_load_ranges(
                displacement_range,
                stroke_range,
                cylinder_count,
                acceleration_range,
                aspiration,
            )
            analysis.engineering_attachments["reciprocating_mass"] = rod_meta.get("mass_samples", [])
            analysis.engineering_attachments["connecting_rod"] = rod_meta.get("rod_samples", [])
            analysis.engineering_attachments["geometry"] = rod_meta.get("geometry_samples", [])
            analysis.engineering_attachments["assumption_records"] = rod_meta.get("assumptions", [])
            analysis.calculations.append(
                make_physics_calculation(
                    id="calc_rod_loading",
                    name="Connecting rod loading estimate",
                    formula="rod_load = reciprocating_mass * acceleration + peak_pressure * bore_area",
                    inputs={
                        "cylinder_count": cylinder_count,
                        "acceleration_low_m_s2": acceleration_range[0],
                        "acceleration_high_m_s2": acceleration_range[1],
                        "peak_pressure_factor_low": PEAK_PRESSURE_TO_BMEP_RANGE[0],
                        "peak_pressure_factor_high": PEAK_PRESSURE_TO_BMEP_RANGE[1],
                        "mass_model": "ReciprocatingMassModel",
                        "reciprocating_mass_kg_mid": rod_meta.get("mass_mid"),
                    },
                    result=round(sum(force_range) / 2, 0),
                    value_range=(round(force_range[0], 0), round(force_range[1], 0)),
                    unit="N",
                    method=(
                        "Combined inertial tensile load with pressure-driven compressive load; "
                        "reciprocating mass from GeometryModel + ReciprocatingMassModel."
                    ),
                    assumptions=rod_meta.get("assumption_strings", [])
                    or [
                        "Reciprocating mass from geometry/density shell model.",
                        "Peak cylinder pressure estimated from BMEP multiplier.",
                    ],
                    dependency_ids=["calc_piston_acceleration", "calc_displacement"],
                    knowledge_state=KnowledgeState.ASSUMED,
                    confidence="medium",
                    assessment="Load range supports fatigue and material requirement generation.",
                    passes=True,
                )
            )
            analysis.calculations.append(
                make_physics_calculation(
                    id="calc_rod_stress_requirement",
                    name="Rod stress requirement estimate",
                    formula="stress = rod_load / section_area (I/H-beam); buckling via Euler",
                    inputs={
                        "load_low_n": force_range[0],
                        "load_high_n": force_range[1],
                        "rod_model": "ConnectingRodModel",
                        "section_type": "i_beam",
                        "tensile_stress_mpa_mid": rod_meta.get("stress_mid"),
                        "buckling_margin_min": rod_meta.get("buckling_margin_min"),
                        "fatigue_margin_min": rod_meta.get("fatigue_margin_min"),
                    },
                    result=round(sum(stress_range) / 2, 1),
                    value_range=(round(stress_range[0], 1), round(stress_range[1], 1)),
                    unit="MPa",
                    method=(
                        "Geometry-aware I-beam connecting-rod section with Euler buckling and "
                        "endurance-style fatigue margin (ConnectingRodModel)."
                    ),
                    assumptions=rod_meta.get("rod_assumption_strings", [])
                    or [
                        "Rod section dimensions scaled from bore via explicit heuristics — not FEA."
                    ],
                    dependency_ids=["calc_rod_loading"],
                    knowledge_state=KnowledgeState.ASSUMED,
                    confidence="medium",
                    assessment="Material must provide yield and fatigue margin above the upper stress estimate.",
                    passes=True,
                )
            )
            analysis.bind_operating("rod_stress_requirement_mpa", "calc_rod_stress_requirement", use_high=True)
            analysis.constraints.append(
                Constraint(
                    id="constraint_physics_rod_stress",
                    type="minimum_yield_strength",
                    description="Connecting rod material yield strength must exceed calculated stress requirement range.",
                    component_id="connecting_rods",
                    priority=ConstraintPriority.HIGH,
                    value=None,  # resolved from calc_rod_stress_requirement via bind
                    unit="MPa",
                    severity=ConstraintSeverity.HARD_LIMIT,
                    goal="meet",
                    source="physics_engine",
                )
            )
            # Value is the canonical calc upper bound — never a re-typed literal.
            rod_calc = analysis.by_id("calc_rod_stress_requirement")
            if rod_calc and rod_calc.value_range:
                analysis.constraints[-1].value = round(max(rod_calc.value_range), 1)
            elif rod_calc and rod_calc.result is not None:
                analysis.constraints[-1].value = rod_calc.result
        else:
            self._add_skipped(
                analysis,
                calculation_id="calc_rod_loading",
                name="Connecting rod loading estimate",
                formula="rod_load = piston_mass * acceleration + peak_pressure * bore_area",
                missing_inputs=[
                    key
                    for key, value in (
                        ("piston_acceleration", acceleration_range),
                        ("stroke_estimate", stroke_range),
                        ("displacement_l", displacement_range),
                        ("cylinder_count", cylinder_count),
                        ("aspiration", aspiration),
                    )
                    if value is None
                ],
                reason=(
                    "Rod loading requires acceleration, geometry, displacement, cylinder count, "
                    "and known aspiration (no silent default)."
                ),
            )
            self._add_skipped(
                analysis,
                calculation_id="calc_rod_stress_requirement",
                name="Rod stress requirement estimate",
                formula="stress = rod_load / effective_section_area",
                missing_inputs=["calc_rod_loading"],
                reason="Rod stress requirement depends on rod loading estimate.",
            )

        if target_hp:
            thermal = ThermalModel().analyze(horsepower=target_hp)
            analysis.engineering_attachments["thermal"] = thermal.to_dict()
            heat_q = thermal.heat_rejection_kw
            assert heat_q is not None and isinstance(heat_q.value, tuple)
            thermal_range = heat_q.value
            analysis.calculations.append(
                make_physics_calculation(
                    id="calc_heat_rejection",
                    name="Cooling heat rejection estimate",
                    formula="cooling_heat = brake_power / thermal_efficiency * coolant_heat_fraction",
                    inputs={
                        "horsepower": target_hp,
                        "brake_thermal_efficiency_low": BRAKE_THERMAL_EFFICIENCY_RANGE[0],
                        "brake_thermal_efficiency_high": BRAKE_THERMAL_EFFICIENCY_RANGE[1],
                        "coolant_heat_fraction_low": COOLANT_HEAT_FRACTION_RANGE[0],
                        "coolant_heat_fraction_high": COOLANT_HEAT_FRACTION_RANGE[1],
                        "thermal_model": "ThermalModel",
                        "thermal_kind": heat_q.kind,
                        "validation_status_model": heat_q.validation_status,
                    },
                    result=round(sum(thermal_range) / 2, 1),
                    value_range=(round(thermal_range[0], 1), round(thermal_range[1], 1)),
                    unit="kW",
                    method=(
                        "Calculated coolant heat rejection via ThermalModel energy-split "
                        f"(maturity {heat_q.maturity})."
                    ),
                    assumptions=list(heat_q.assumptions),
                    dependency_ids=["calc_torque"] if max_rpm else [],
                    knowledge_state=KnowledgeState.ASSUMED,
                    confidence=heat_q.confidence,
                    assessment="Cooling system must reject this heat range at the design duty cycle.",
                    passes=True,
                )
            )
            analysis.bind_operating("cooling_heat_rejection_kw", "calc_heat_rejection", use_high=True)

            # Temperature uses upper heat bound (historical PE operating-condition binding).
            heat_high = float(max(thermal_range))
            thermal_temp = ThermalModel().analyze(
                horsepower=target_hp, cooling_heat_kw_for_temp=heat_high
            )
            analysis.engineering_attachments["thermal"] = thermal_temp.to_dict()
            temp_q = thermal_temp.combustion_side_temperature_c
            assert temp_q is not None
            required_temp = float(temp_q.value)  # type: ignore[arg-type]
            heat_calc = analysis.by_id("calc_heat_rejection")
            analysis.calculations.append(
                make_physics_calculation(
                    id="calc_combustion_side_temperature",
                    name="Combustion-side temperature estimate",
                    formula="T ≈ 180 + min(120, cooling_heat_kw / 8)",
                    inputs={
                        "cooling_heat_rejection_kw": heat_high,
                        "thermal_model": "ThermalModel",
                        "thermal_kind": temp_q.kind,
                        "validation_status_model": temp_q.validation_status,
                    },
                    result=required_temp,
                    value_range=(required_temp, required_temp),
                    unit="C",
                    method=(
                        f"Empirical combustion-side temperature via ThermalModel "
                        f"(maturity {temp_q.maturity}, {temp_q.kind})."
                    ),
                    assumptions=list(temp_q.assumptions),
                    dependency_ids=["calc_heat_rejection"] if heat_calc else [],
                    knowledge_state=KnowledgeState.ASSUMED,
                    confidence=temp_q.confidence,
                    assessment="Used for material temperature-limit requirements on combustion-exposed parts.",
                    passes=True,
                )
            )
            analysis.bind_operating("combustion_side_temperature_c", "calc_combustion_side_temperature")
            for component_id in ("pistons", "cylinder_head"):
                analysis.constraints.append(
                    Constraint(
                        id=f"constraint_physics_temperature_{component_id}",
                        type="minimum_temperature_limit",
                        description=f"{component_id.replace('_', ' ').title()} material must tolerate estimated combustion-side operating temperature.",
                        component_id=component_id,
                        priority=ConstraintPriority.HIGH,
                        value=required_temp,
                        unit="C",
                        severity=ConstraintSeverity.HARD_LIMIT,
                        goal="meet",
                        source="physics_engine",
                    )
                )
        else:
            self._add_skipped(
                analysis,
                calculation_id="calc_heat_rejection",
                name="Cooling heat rejection estimate",
                formula="cooling_heat = brake_power / thermal_efficiency * coolant_heat_fraction",
                missing_inputs=["target_horsepower"],
                reason="Cooling heat rejection requires resolved brake power.",
            )

        return analysis

    @staticmethod
    def _add_skipped(
        analysis: PhysicsAnalysis,
        calculation_id: str,
        name: str,
        formula: str,
        missing_inputs: list[str],
        reason: str,
    ) -> None:
        analysis.calculations.append(
            make_physics_calculation(
                id=calculation_id,
                name=name,
                formula=formula,
                status="skipped",
                missing_inputs=missing_inputs,
                reason=reason,
                knowledge_state=KnowledgeState.UNKNOWN,
                confidence="low",
                passes=None,
            )
        )

    @staticmethod
    def _resolve_input_requirements(
        params: dict[str, str | float | int],
    ) -> list[InputRequirement]:
        """Expose every physics-critical input as KNOWN / ASSUMED / UNKNOWN — never silent default."""
        reqs: list[InputRequirement] = []
        for name in ("target_horsepower", "max_rpm", "displacement_l", "cylinder_count", "aspiration"):
            if name in params and params[name] is not None:
                reqs.append(
                    InputRequirement(
                        name=name,
                        value=params[name],
                        state=InputState.KNOWN,
                        source="explicit_prompt",
                    )
                )
            else:
                reqs.append(
                    InputRequirement(
                        name=name,
                        value=None,
                        state=InputState.UNKNOWN,
                        source="unresolved",
                    )
                )
        return reqs

    @staticmethod
    def _float_param(params: dict[str, str | float | int], key: str) -> float | None:
        value = params.get(key)
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _bmep_range(aspiration: str) -> tuple[float, float]:
        """BMEP Pa band from EngineCycleModel (endpoints identical to legacy constants)."""
        return EngineCycleModel().bmep_range_pa(aspiration)

    def _displacement_range(
        self,
        target_hp: float | None,
        max_rpm: float | None,
        displacement_l: float | None,
        aspiration: str | None,
        cylinder_count: float | None,
    ) -> tuple[float, float] | None:
        if displacement_l:
            return displacement_l, displacement_l
        # Power/RPM BMEP path requires known aspiration — never invent NA.
        if target_hp and max_rpm:
            if not aspiration:
                return None
            power_w = target_hp * HP_TO_KW * 1000.0
            bmep_low, bmep_high = self._bmep_range(aspiration)
            high_l = power_w * FOUR_STROKE_POWER_FACTOR / (bmep_low * max_rpm) * 1000.0
            low_l = power_w * FOUR_STROKE_POWER_FACTOR / (bmep_high * max_rpm) * 1000.0
            return low_l, high_l
        if cylinder_count:
            return (
                cylinder_count * DEFAULT_DISPLACEMENT_PER_CYLINDER_L_RANGE[0],
                cylinder_count * DEFAULT_DISPLACEMENT_PER_CYLINDER_L_RANGE[1],
            )
        return None

    @staticmethod
    def _stroke_range(
        displacement_l: tuple[float, float] | None,
        cylinder_count: float | None,
        stroke_mm: float | None,
    ) -> tuple[float, float] | None:
        if stroke_mm:
            return stroke_mm, stroke_mm
        if not displacement_l or not cylinder_count:
            return None
        strokes: list[float] = []
        for disp_l in displacement_l:
            per_cylinder_m3 = disp_l / 1000.0 / cylinder_count
            for ratio in BORE_STROKE_RATIO_RANGE:
                stroke_m = (4.0 * per_cylinder_m3 / (math.pi * ratio**2)) ** (1.0 / 3.0)
                strokes.append(stroke_m * 1000.0)
        return min(strokes), max(strokes)

    @staticmethod
    def _piston_speed_assessment(upper_mps: float) -> str:
        if upper_mps <= 20:
            return "Mean piston speed is in normal production-engine range."
        if upper_mps <= 25:
            return "Mean piston speed is high-performance but within common racing practice."
        return "Mean piston speed is extreme; reciprocating mass, fatigue, and stroke reduction require validation."

    def _reciprocating_load_ranges(
        self,
        displacement_range_l: tuple[float, float],
        stroke_range_mm: tuple[float, float],
        cylinder_count: float,
        acceleration_range_m_s2: tuple[float, float],
        aspiration: str,
    ) -> tuple[tuple[float, float], tuple[float, float], dict[str, Any]]:
        """Geometry-derived reciprocating mass + connecting-rod section stress."""
        forces: list[float] = []
        stresses_mpa: list[float] = []
        buckling_margins: list[float] = []
        fatigue_margins: list[float] = []
        mass_samples: list[dict[str, Any]] = []
        rod_samples: list[dict[str, Any]] = []
        geometry_samples: list[dict[str, Any]] = []
        assumption_reg = AssumptionRegistry()

        mass_model = ReciprocatingMassModel()
        rod_model = ConnectingRodModel()
        geom_model = GeometryModel()
        bmep_low, bmep_high = self._bmep_range(aspiration)

        # Corner sampling: keep enumeration bounded (endpoints only).
        for disp_l in displacement_range_l:
            for stroke_mm in stroke_range_mm:
                stroke_m = stroke_mm / 1000.0
                per_cylinder_l = disp_l / cylinder_count
                bore_area_m2 = (per_cylinder_l / 1000.0) / stroke_m

                geom = geom_model.resolve(
                    displacement_l=disp_l,
                    cylinder_count=cylinder_count,
                    stroke_mm=stroke_mm,
                    registry=AssumptionRegistry(),
                )
                assumption_reg.extend(geom.registry or AssumptionRegistry())
                geometry_samples.append(geom.to_dict())
                if geom.bore_mm is None:
                    # Analytical fallback identical to bore_area identity.
                    bore_mm = (4.0 * bore_area_m2 / math.pi) ** 0.5 * 1000.0
                else:
                    bore_mm = geom.bore_mm.value

                mass_reg = AssumptionRegistry()
                mass_est = mass_model.estimate(
                    bore_mm=bore_mm,
                    stroke_mm=stroke_mm,
                    registry=mass_reg,
                )
                assumption_reg.extend(mass_reg)
                mass_samples.append(mass_est.to_dict())
                recip_mass = mass_est.reciprocating_mass_kg

                for acceleration in acceleration_range_m_s2:
                    inertial_force = recip_mass * acceleration
                    for bmep in (bmep_low, bmep_high):
                        for pressure_factor in PEAK_PRESSURE_TO_BMEP_RANGE:
                            gas_force = bmep * pressure_factor * bore_area_m2
                            load = inertial_force + gas_force
                            forces.append(load)

                            rod_reg = AssumptionRegistry()
                            rod = rod_model.analyze(
                                bore_mm=bore_mm,
                                stroke_mm=stroke_mm,
                                tensile_load_n=load,
                                compressive_load_n=max(gas_force, load * 0.5),
                                section_type=RodSectionType.I_BEAM,
                                registry=rod_reg,
                            )
                            assumption_reg.extend(rod_reg)
                            rod_samples.append(rod.to_dict())
                            stresses_mpa.append(rod.maximum_tensile_stress_mpa)
                            stresses_mpa.append(rod.compressive_stress_mpa)
                            buckling_margins.append(rod.buckling_margin)
                            fatigue_margins.append(rod.fatigue_margin)

        meta: dict[str, Any] = {
            "mass_samples": mass_samples[:4],
            "rod_samples": rod_samples[:4],
            "geometry_samples": geometry_samples[:4],
            "assumptions": assumption_reg.as_dicts()[:40],
            "assumption_strings": assumption_reg.as_strings()[:20],
            "rod_assumption_strings": [
                a for a in assumption_reg.as_strings() if a.startswith("rod_") or "rod_" in a
            ][:12],
            "mass_mid": round(sum(m["reciprocating_mass_kg"] for m in mass_samples) / max(len(mass_samples), 1), 4)
            if mass_samples
            else None,
            "stress_mid": round(sum(stresses_mpa) / max(len(stresses_mpa), 1), 2) if stresses_mpa else None,
            "buckling_margin_min": round(min(buckling_margins), 3) if buckling_margins else None,
            "fatigue_margin_min": round(min(fatigue_margins), 3) if fatigue_margins else None,
        }
        return (min(forces), max(forces)), (min(stresses_mpa), max(stresses_mpa)), meta

    @staticmethod
    def _cooling_heat_rejection_range(target_hp: float) -> tuple[float, float]:
        brake_power_kw = target_hp * HP_TO_KW
        values = [
            brake_power_kw / efficiency * fraction
            for efficiency in BRAKE_THERMAL_EFFICIENCY_RANGE
            for fraction in COOLANT_HEAT_FRACTION_RANGE
        ]
        return min(values), max(values)

    @staticmethod
    def _estimate_component_temperature(analysis: PhysicsAnalysis, target_hp: float | None) -> float | None:
        if target_hp is None:
            return None
        heat_kw = analysis.resolve_operating("cooling_heat_rejection_kw")
        if heat_kw is None:
            return None
        return round(180.0 + min(120.0, float(heat_kw) / 8.0), 1)
