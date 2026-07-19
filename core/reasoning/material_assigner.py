"""Material assigner — deterministic selection from calculated operating conditions."""

from __future__ import annotations

from dataclasses import dataclass

from core.ir.design_graph import EngineeringDesignGraph
from core.ir.material import MaterialSpec
from core.ir.requirement_spec import RequirementSpecification
from core.reasoning.physics_engine import PhysicsAnalysis
from knowledge.materials.catalog import MATERIAL_CATALOG


@dataclass(frozen=True)
class MaterialRequirement:
    """Physical requirements used to rank material candidates."""

    role: str
    required_yield_mpa: float
    required_fatigue_mpa: float
    required_temperature_c: float
    mass_sensitive: bool
    source: str


class MaterialAssigner:
    """Assign MaterialSpec by comparing catalog properties against physics requirements."""

    _NAME_TO_CATALOG: dict[str, str] = {
        entry["name"].lower(): key for key, entry in MATERIAL_CATALOG.items()
    }
    _NAME_TO_CATALOG.update(
        {
            "aluminum alloy": "al_356_t6",
            "2618 aluminum": "al_2618",
            "4032 aluminum": "al_4032",
            "forged aluminum alloy": "al_2618",
            "forged steel": "forged_steel_4340",
            "cast iron liners": "cast_iron_gray",
            "cast iron": "cast_iron_gray",
            "titanium": "ti_6al4v",
            "inconel": "in718",
            "stainless steel": "stainless_steel_21_4n",
            "bronze": "bronze_sae660",
        }
    )

    _ROLE_CANDIDATES: dict[str, list[str]] = {
        "reciprocating": ["forged_steel_4340", "ti_6al4v"],
        "piston": ["al_2618", "al_4032", "ti_6al4v"],
        "hot_gas": ["stainless_steel_21_4n", "in718", "ti_6al4v"],
        "structural_hot": ["al_356_t6", "cast_iron_gray", "forged_steel_4340"],
        "shaft": ["forged_steel_4340", "nitrided_steel", "ti_6al4v"],
        "bearing": ["bronze_sae660", "forged_steel_4340", "nitrided_steel"],
        "housing": ["al_356_t6", "cast_iron_gray", "forged_steel_4340"],
    }

    def __init__(self) -> None:
        self.selection_failures: list[dict[str, object]] = []

    def assign(
        self,
        graph: EngineeringDesignGraph,
        requirement_spec: RequirementSpecification | None = None,
        physics_analysis: PhysicsAnalysis | None = None,
    ) -> EngineeringDesignGraph:
        self.selection_failures = []
        # Unrecognized material terms must not be silently replaced with catalog properties.
        blocked_roles = set()
        if requirement_spec is not None:
            for term in requirement_spec.unrecognized_terms:
                if term.get("category") == "material":
                    blocked_roles.add("reciprocating")

        for comp in graph.components.values():
            role = self._component_role(comp.id, comp.name, comp.function)
            if role in blocked_roles:
                comp.material = None
                comp.material_spec = None
                continue

            requirement = self._requirement_for_component(
                comp.id, comp.name, comp.function, physics_analysis
            )
            if requirement is None:
                # No real computed requirement → leave unassigned (clear template ghosts).
                if role is not None:
                    comp.material = None
                    comp.material_spec = None
                continue

            selected, rankings = self.select_material(requirement)
            if selected is not None:
                comp.material_spec = selected
                comp.material = selected.name
                continue

            comp.material = None
            comp.material_spec = None
            best = rankings[0] if rankings else {}
            self.selection_failures.append(
                {
                    "component_id": comp.id,
                    "role": requirement.role,
                    "required_yield_mpa": requirement.required_yield_mpa,
                    "required_fatigue_mpa": requirement.required_fatigue_mpa,
                    "required_temperature_c": requirement.required_temperature_c,
                    "source": requirement.source,
                    "candidate_rankings": rankings,
                    "best_catalog_name": best.get("name"),
                    "best_limiting_margin": best.get("limiting_margin"),
                    "reason": (
                        f"No catalog material meets hard thresholds for {comp.id}: "
                        f"required yield {requirement.required_yield_mpa:g} MPa, "
                        f"fatigue {requirement.required_fatigue_mpa:g} MPa, "
                        f"temperature {requirement.required_temperature_c:g} C "
                        f"(best candidate {best.get('name')!r} limiting_margin="
                        f"{best.get('limiting_margin')})."
                    ),
                }
            )
        return graph

    def select_material(
        self, requirement: MaterialRequirement
    ) -> tuple[MaterialSpec | None, list[dict[str, str | float | int | bool | None]]]:
        candidates = self._ROLE_CANDIDATES.get(requirement.role, [])
        ranked: list[dict[str, str | float | int | bool | None]] = []

        for key in candidates:
            entry = MATERIAL_CATALOG[key]
            yield_strength = float(entry.get("yield_strength_mpa") or 0)
            fatigue_strength = float(entry.get("fatigue_strength_mpa") or 0)
            temp_limit = float(entry.get("temperature_limit_c") or 0)
            density = float(entry.get("density_kg_m3") or 0)
            relative_cost = float(entry.get("relative_cost") or 1)
            yield_margin = yield_strength / requirement.required_yield_mpa if requirement.required_yield_mpa else 999.0
            fatigue_margin = fatigue_strength / requirement.required_fatigue_mpa if requirement.required_fatigue_mpa else 999.0
            thermal_margin = temp_limit / requirement.required_temperature_c if requirement.required_temperature_c else 999.0
            hard_constraints_met = yield_margin >= 1.0 and fatigue_margin >= 1.0 and thermal_margin >= 1.0
            limiting_margin = min(yield_margin, fatigue_margin, thermal_margin)
            density_penalty = density if requirement.mass_sensitive else 0.0

            ranked.append(
                {
                    "catalog_key": key,
                    "name": str(entry["name"]),
                    "hard_constraints_met": hard_constraints_met,
                    "yield_margin": round(yield_margin, 3),
                    "fatigue_margin": round(fatigue_margin, 3),
                    "thermal_margin": round(thermal_margin, 3),
                    "limiting_margin": round(limiting_margin, 3),
                    "density_kg_m3": density,
                    "mass_sensitive_density_penalty": density_penalty,
                    "relative_cost": relative_cost,
                }
            )

        if requirement.mass_sensitive:
            ranked.sort(
                key=lambda item: (
                    not bool(item["hard_constraints_met"]),
                    float(item["density_kg_m3"] or 0),
                    float(item["relative_cost"] or 0),
                    -float(item["limiting_margin"] or 0),
                )
            )
        else:
            ranked.sort(
                key=lambda item: (
                    not bool(item["hard_constraints_met"]),
                    float(item["relative_cost"] or 0),
                    float(item["density_kg_m3"] or 0),
                    -float(item["limiting_margin"] or 0),
                )
            )
        if not ranked or not ranked[0]["hard_constraints_met"]:
            return None, ranked

        best_key = str(ranked[0]["catalog_key"])
        spec = MaterialSpec.from_catalog(best_key)
        if not spec:
            return None, ranked
        spec.selection_metrics = {
            "role": requirement.role,
            "required_yield_mpa": round(requirement.required_yield_mpa, 1),
            "required_fatigue_mpa": round(requirement.required_fatigue_mpa, 1),
            "required_temperature_c": round(requirement.required_temperature_c, 1),
            "mass_sensitive": requirement.mass_sensitive,
            "source": requirement.source,
        }
        spec.candidate_rankings = ranked
        spec.selection_rationale = (
            f"Selected by deterministic threshold-satisfaction comparison for {requirement.role}: "
            f"yield, fatigue, and thermal margins must exceed 1.0; qualifying candidates are ranked by "
            f"{'lower density, then lower cost' if requirement.mass_sensitive else 'lower cost, then lower density'}, "
            "with extra margin used only as a final tie-break."
        )
        return spec, ranked

    def _requirement_for_component(
        self,
        component_id: str,
        name: str,
        function: str,
        physics_analysis: PhysicsAnalysis | None,
    ) -> MaterialRequirement | None:
        role = self._component_role(component_id, name, function)
        if role is None:
            return None

        rod_stress = self._computed_value(physics_analysis, "calc_rod_stress_requirement")
        combustion_temp = self._computed_value(physics_analysis, "calc_combustion_side_temperature")
        rod_loading = self._computed_value(physics_analysis, "calc_rod_loading")

        # No invented defaults: if the driving calculation did not run, do not assign material.
        if role in {"reciprocating", "piston", "shaft"} and rod_stress is None:
            return None
        if role in {"hot_gas", "structural_hot", "piston"} and combustion_temp is None:
            return None
        if role in {"bearing"} and rod_loading is None:
            return None
        if role == "housing" and rod_loading is None and rod_stress is None:
            # Housing only when some load pathway exists (physics chain at least started).
            return None

        assert rod_stress is not None or role in {"hot_gas", "structural_hot", "bearing", "housing"}
        stress = float(rod_stress) if rod_stress is not None else 0.0
        temp = float(combustion_temp) if combustion_temp is not None else 0.0

        if role == "reciprocating":
            return MaterialRequirement(
                role=role,
                required_yield_mpa=max(stress * 1.25, 220.0),
                required_fatigue_mpa=max(stress * 0.65, 160.0),
                required_temperature_c=160.0,
                mass_sensitive=True,
                source="calc_rod_stress_requirement",
            )
        if role == "piston":
            return MaterialRequirement(
                role=role,
                required_yield_mpa=max(stress * 0.55, 180.0),
                required_fatigue_mpa=max(stress * 0.30, 90.0),
                required_temperature_c=temp,
                mass_sensitive=True,
                source="calc_rod_loading + calc_heat_rejection",
            )
        if role == "hot_gas":
            return MaterialRequirement(
                role=role,
                required_yield_mpa=280.0,
                required_fatigue_mpa=180.0,
                required_temperature_c=max(temp + 250.0, 650.0),
                mass_sensitive=False,
                source="calc_heat_rejection",
            )
        if role == "structural_hot":
            return MaterialRequirement(
                role=role,
                required_yield_mpa=180.0,
                required_fatigue_mpa=80.0,
                required_temperature_c=temp,
                mass_sensitive=False,
                source="calc_heat_rejection",
            )
        if role == "shaft":
            return MaterialRequirement(
                role=role,
                required_yield_mpa=max(stress * 0.9, 350.0),
                required_fatigue_mpa=max(stress * 0.45, 220.0),
                required_temperature_c=180.0,
                mass_sensitive=False,
                source="calc_torque + calc_rod_loading",
            )
        if role == "bearing":
            return MaterialRequirement(
                role=role,
                required_yield_mpa=120.0,
                required_fatigue_mpa=70.0,
                required_temperature_c=160.0,
                mass_sensitive=False,
                source="calc_rod_loading",
            )
        if role == "housing":
            return MaterialRequirement(
                role=role,
                required_yield_mpa=140.0,
                required_fatigue_mpa=70.0,
                required_temperature_c=140.0,
                mass_sensitive=True,
                source="structural containment requirement",
            )
        return None

    @staticmethod
    def _computed_value(physics_analysis: PhysicsAnalysis | None, calc_id: str) -> float | None:
        if physics_analysis is None:
            return None
        calc = physics_analysis.by_id(calc_id)
        if calc is None or calc.status == "skipped":
            return None
        if calc.value_range is not None:
            return float(max(calc.value_range))
        if calc.result is not None:
            return float(calc.result)
        return None

    @staticmethod
    def _component_role(component_id: str, name: str, function: str) -> str | None:
        text = f"{component_id} {name} {function}".lower()
        # Order matters: piston functions often mention connecting rods.
        if "piston" in text and "connecting_rod" not in component_id.lower():
            return "piston"
        if "connecting rod" in text or "connecting_rods" in text or component_id == "connecting_rods":
            return "reciprocating"
        if "exhaust" in text or "combustor" in text or "turbine" in text:
            return "hot_gas"
        if "cylinder head" in text or "engine block" in text or "cylinder bore" in text:
            return "structural_hot"
        if "crankshaft" in text or "camshaft" in text or "shaft" in text or "gear" in text:
            return "shaft"
        if "bearing" in text or "bushing" in text:
            return "bearing"
        if "housing" in text or "pan" in text or "radiator" in text:
            return "housing"
        return None

    def _catalog_key_from_declared_material(self, material: str | None) -> str | None:
        if not material:
            return None
        lower = material.lower()
        key = self._NAME_TO_CATALOG.get(lower)
        if key:
            return key
        for catalog_key, entry in MATERIAL_CATALOG.items():
            if str(entry["name"]).lower() in lower:
                return catalog_key
        return None
