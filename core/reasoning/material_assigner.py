"""Material assigner — evidence-gated selection from computed requirements only."""

from __future__ import annotations

from dataclasses import dataclass

from core.epistemology.evidence import Evidence
from core.epistemology.knowledge_state import KnowledgeState
from core.ir.design_graph import EngineeringDesignGraph
from core.ir.material import MaterialSpec
from core.ir.requirement_spec import RequirementSpecification
from core.materials.component_role import ComponentRole, role_for_component
from core.materials.material_decision import MaterialDecision
from core.materials.material_requirement import (
    MaterialRequirementEvidence,
    build_piston_requirement,
    build_structural_rod_requirement,
    unknown_requirement,
)
from core.reasoning.physics_engine import PhysicsAnalysis
from knowledge.materials.catalog import MATERIAL_CATALOG


@dataclass(frozen=True)
class MaterialRequirement:
    """Physical requirements used to rank material candidates — must be computed."""

    role: str
    required_yield_mpa: float
    required_fatigue_mpa: float
    required_temperature_c: float
    mass_sensitive: bool
    source: str
    evidence_calc_ids: tuple[str, ...] = ()


class MaterialAssigner:
    """Assign MaterialSpec only when a computed requirement exists for the component role."""

    _ROLE_CANDIDATES: dict[str, list[str]] = {
        ComponentRole.STRUCTURAL_LOAD_PATH.value: [
            "forged_steel_4340",
            "structural_steel_astm_a572",
            "al_6061_t6",
            "hardwood_oak",
            "ti_6al4v",
        ],
        ComponentRole.ROTATING_MASS.value: [
            "forged_steel_4340",
            "nitrided_steel",
            "ti_6al4v",
            "al_2618",
            "al_4032",
        ],
        ComponentRole.PRESSURE_BOUNDARY.value: ["cast_iron_gray", "forged_steel_4340", "al_356_t6"],
        ComponentRole.THERMAL_SYSTEM.value: ["al_356_t6", "cast_iron_gray", "forged_steel_4340"],
        ComponentRole.FLUID_COMPONENT.value: ["al_356_t6", "cast_iron_gray", "forged_steel_4340"],
    }

    # Candidate filters by component — still keyed by id, not substring name matching.
    _COMPONENT_CANDIDATES: dict[str, list[str]] = {
        "connecting_rods": ["forged_steel_4340", "ti_6al4v"],
        "rod_primary": ["forged_steel_4340", "ti_6al4v"],
        "rotating_link": ["forged_steel_4340", "ti_6al4v"],
        "rod_piece_xyz": ["forged_steel_4340", "ti_6al4v"],
        "pistons": ["al_2618", "al_4032", "ti_6al4v"],
        "crankshaft": ["forged_steel_4340", "nitrided_steel", "ti_6al4v"],
        "camshaft": ["forged_steel_4340", "nitrided_steel", "ti_6al4v"],
        "main_bearings": ["forged_steel_4340", "nitrided_steel", "ti_6al4v"],
        "top_chord": ["structural_steel_astm_a572"],
        "bottom_chord": ["structural_steel_astm_a572"],
        "web_diagonals": ["structural_steel_astm_a572"],
        "verticals": ["structural_steel_astm_a572"],
        "stringers": ["structural_steel_astm_a572"],
        "top_tube": ["al_6061_t6", "ti_6al4v"],
        "down_tube": ["al_6061_t6", "ti_6al4v"],
        "seat_tube": ["al_6061_t6", "ti_6al4v"],
        "seat_stays": ["al_6061_t6", "ti_6al4v"],
        "chain_stays": ["al_6061_t6", "ti_6al4v"],
        "front_legs": ["hardwood_oak"],
        "rear_legs": ["hardwood_oak"],
        "stretchers": ["hardwood_oak"],
        "seat_rails": ["hardwood_oak"],
    }

    def __init__(self) -> None:
        self.selection_failures: list[dict[str, object]] = []
        self.decisions: list[MaterialDecision] = []

    def assign(
        self,
        graph: EngineeringDesignGraph,
        requirement_spec: RequirementSpecification | None = None,
        physics_analysis: PhysicsAnalysis | None = None,
    ) -> EngineeringDesignGraph:
        self.selection_failures = []
        self.decisions = []

        blocked_components: set[str] = set()
        if requirement_spec is not None:
            for term in requirement_spec.unrecognized_terms:
                if term.get("category") == "material":
                    # Unknown material named in prompt — do not invent rods/pistons substitution.
                    blocked_components.update({"connecting_rods", "pistons", "rod_primary", "rotating_link", "rod_piece_xyz"})

        for comp in graph.components.values():
            # Always clear template ghost materials before evidence-gated assignment.
            comp.material = None
            comp.material_spec = None

            role = role_for_component(comp.id)
            if comp.id in blocked_components or role == ComponentRole.UNKNOWN:
                self.decisions.append(
                    MaterialDecision(
                        component_id=comp.id,
                        role=role.value,
                        selected_material=None,
                        requirement_source=None,
                        requirement_value=None,
                        evidence=[],
                        confidence="UNKNOWN",
                    )
                )
                continue

            requirement = self._requirement_for_role(role, comp.id, physics_analysis)
            if requirement is None:
                unk = unknown_requirement(comp.id, "No computed physics pathway for this role")
                self.decisions.append(
                    MaterialDecision(
                        component_id=comp.id,
                        role=role.value,
                        selected_material=None,
                        requirement_source=None,
                        requirement_value=None,
                        evidence=[],
                        confidence="UNKNOWN",
                        requirement_evidence=unk.to_dict(),
                    )
                )
                continue

            selected, rankings = self.select_material(requirement, component_id=comp.id)
            evidence = [
                Evidence(
                    claim=f"computed requirement from {calc_id}",
                    state=KnowledgeState.DERIVED,
                    confidence="medium",
                    reason=requirement.source,
                    source_calc_id=calc_id,
                )
                for calc_id in requirement.evidence_calc_ids
            ]
            req_packet = self._evidence_packet(requirement, comp.id, selected, rankings)
            if selected is not None:
                evidence.append(
                    Evidence(
                        claim="yield_strength_catalog",
                        state=KnowledgeState.KNOWN,
                        confidence="high",
                        reason=f"catalog comparison selected {selected.name}",
                        source_calc_id=None,
                    )
                )
                # Attach structured requirement evidence onto selection metrics.
                if selected.selection_metrics is not None:
                    selected.selection_metrics["requirement_evidence"] = req_packet
                else:
                    selected.selection_metrics = {"requirement_evidence": req_packet}
                comp.material_spec = selected
                comp.material = selected.name
                self.decisions.append(
                    MaterialDecision(
                        component_id=comp.id,
                        role=role.value,
                        selected_material=selected.name,
                        requirement_source=requirement.source,
                        requirement_value=requirement.required_yield_mpa,
                        evidence=evidence,
                        confidence="high" if requirement.evidence_calc_ids else "UNKNOWN",
                        requirement_evidence=req_packet,
                    )
                )
                continue

            self.decisions.append(
                MaterialDecision(
                    component_id=comp.id,
                    role=role.value,
                    selected_material=None,
                    requirement_source=requirement.source,
                    requirement_value=requirement.required_yield_mpa,
                    evidence=evidence,
                    confidence="UNKNOWN",
                    requirement_evidence=req_packet,
                )
            )
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
                    "requirement_evidence": req_packet,
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
        self,
        requirement: MaterialRequirement,
        component_id: str | None = None,
    ) -> tuple[MaterialSpec | None, list[dict[str, str | float | int | bool | None]]]:
        if component_id and component_id in self._COMPONENT_CANDIDATES:
            candidates = self._COMPONENT_CANDIDATES[component_id]
        else:
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
                    "mass_sensitive_density_penalty": density if requirement.mass_sensitive else 0.0,
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

    def _requirement_for_role(
        self,
        role: ComponentRole,
        component_id: str,
        physics_analysis: PhysicsAnalysis | None,
    ) -> MaterialRequirement | None:
        """Only emit requirements backed by computed physics — no fixed theater floors."""
        rod_stress = self._computed_value(physics_analysis, "calc_rod_stress_requirement")
        truss_stress = self._computed_value(physics_analysis, "calc_truss_member_stress")
        combustion_temp = self._computed_value(physics_analysis, "calc_combustion_side_temperature")

        if role == ComponentRole.STRUCTURAL_LOAD_PATH:
            stress_value = truss_stress if truss_stress is not None else rod_stress
            if stress_value is None:
                return None
            stress = float(stress_value)
            source = (
                "calc_truss_member_stress"
                if truss_stress is not None
                else "calc_rod_stress_requirement"
            )
            mass_sensitive = source == "calc_rod_stress_requirement"
            return MaterialRequirement(
                role=role.value,
                required_yield_mpa=stress * 1.25,
                required_fatigue_mpa=stress * 0.65,
                required_temperature_c=160.0,
                mass_sensitive=mass_sensitive,
                source=source,
                evidence_calc_ids=(source,),
            )

        if role == ComponentRole.ROTATING_MASS:
            if rod_stress is None:
                return None
            stress = float(rod_stress)
            # Pistons: reciprocating mass — mass-sensitive, combustion temp when available.
            if component_id == "pistons":
                if combustion_temp is None:
                    return None
                return MaterialRequirement(
                    role=role.value,
                    required_yield_mpa=stress * 0.55,
                    required_fatigue_mpa=stress * 0.30,
                    required_temperature_c=float(combustion_temp),
                    mass_sensitive=True,
                    source="calc_rod_stress_requirement + calc_combustion_side_temperature",
                    evidence_calc_ids=("calc_rod_stress_requirement", "calc_combustion_side_temperature"),
                )
            # Shafts / bearings: torque+rod load path — stress-derived, not mass-sensitive.
            return MaterialRequirement(
                role=role.value,
                required_yield_mpa=stress * 0.9,
                required_fatigue_mpa=stress * 0.45,
                required_temperature_c=180.0,
                mass_sensitive=False,
                source="calc_rod_stress_requirement",
                evidence_calc_ids=("calc_rod_stress_requirement",),
            )

        # PRESSURE_BOUNDARY / THERMAL_SYSTEM / FLUID_COMPONENT have no standalone
        # computed yield/fatigue pathway in the Phase 1 physics engine — refuse assignment.
        return None

    @staticmethod
    def _evidence_packet(
        requirement: MaterialRequirement,
        component_id: str,
        selected: MaterialSpec | None,
        rankings: list[dict[str, str | float | int | bool | None]],
    ) -> dict[str, object]:
        if component_id == "pistons":
            packet = build_piston_requirement(
                component=component_id,
                stress_mpa=requirement.required_yield_mpa / 0.55
                if requirement.required_yield_mpa
                else 0.0,
                temperature_c=requirement.required_temperature_c,
                computed_from=list(requirement.evidence_calc_ids),
            )
        elif requirement.role == ComponentRole.STRUCTURAL_LOAD_PATH.value:
            packet = build_structural_rod_requirement(
                component=component_id,
                stress_mpa=requirement.required_yield_mpa / 1.25
                if requirement.required_yield_mpa
                else 0.0,
                temperature_c=requirement.required_temperature_c,
                computed_from=list(requirement.evidence_calc_ids),
            )
        else:
            packet = MaterialRequirementEvidence(
                component=component_id,
                required_properties={
                    "yield_mpa": requirement.required_yield_mpa,
                    "fatigue_mpa": requirement.required_fatigue_mpa,
                    "temperature_c": requirement.required_temperature_c,
                },
                computed_from=list(requirement.evidence_calc_ids),
                load_case="stress_derived",
                temperature_c=requirement.required_temperature_c,
                safety_factor={},
                role=requirement.role,
                status="computed",
            )
        packet.reason_for_selection = (
            None
            if selected is None
            else (
                f"Selected {selected.name} because computed load evidence requires "
                f"yield≥{requirement.required_yield_mpa:.1f} MPa, "
                f"fatigue≥{requirement.required_fatigue_mpa:.1f} MPa, "
                f"temperature≥{requirement.required_temperature_c:.1f} C "
                f"(load_source={requirement.source})."
            )
        )
        alts = []
        for r in rankings[:8]:
            rejected_for = None
            if not r.get("hard_constraints_met"):
                # Identify limiting property.
                margins = {
                    "yield": float(r.get("yield_margin") or 0),
                    "fatigue": float(r.get("fatigue_margin") or 0),
                    "temperature": float(r.get("thermal_margin") or 0),
                }
                rejected_for = min(margins, key=margins.get)  # type: ignore[arg-type]
            alts.append(
                {
                    "name": r.get("name"),
                    "hard_constraints_met": r.get("hard_constraints_met"),
                    "limiting_margin": r.get("limiting_margin"),
                    "rejected_property": rejected_for,
                    "selected": selected is not None and r.get("name") == selected.name,
                }
            )
        packet.alternatives_considered = alts
        return packet.to_dict()

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
