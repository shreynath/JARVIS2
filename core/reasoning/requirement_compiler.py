"""Engineering Requirement Compiler — intent → traceable requirement specification."""

from __future__ import annotations

import re

from core.ir.constraint import ConstraintPriority, ConstraintSpec
from core.ir.design_graph import EngineeringIntent
from core.ir.requirement_spec import (
    CompiledRequirement,
    DecisionCategory,
    DecisionStatus,
    RequiredDecision,
    RequirementSpecification,
    SpecificationStatus,
)
from knowledge.requirements.templates import (
    ICE_REQUIRED_DECISIONS,
    REFERENCE_PROFILES,
    build_ice_required_decisions,
    compile_reference_requirements,
    match_reference_profile,
)


class RequirementCompiler:
    """Compile engineering intent into a formal, traceable requirement specification.

    Does not invent constraints for vague prompts — surfaces required decisions instead.
    Reference profiles (e.g. Ferrari V12) compile fully specified requirements.
    """

    _OBJECT_DECISION_SETS: dict[str, list[dict]] = {
        "internal_combustion_engine": ICE_REQUIRED_DECISIONS,
    }

    # Category A: known-unknown nouns that must not silently map to real catalog entries.
    _UNKNOWN_MATERIAL_TERMS = ("unobtainium", "adamantium", "vibranium", "mithril")
    _UNKNOWN_COOLANT_TERMS = ("lava-cooled", "lava cooled", "magma-cooled", "magma cooled")

    # Category C: mutually incompatible field combinations.
    _INCOMPATIBLE_COMBINATIONS: list[dict[str, str]] = [
        {
            "fields": "fuel_type+ignition",
            "description": "Diesel fuel with spark ignition is incompatible — diesel uses compression ignition.",
            "detect": "diesel_spark",
        },
    ]

    def compile(self, intent: EngineeringIntent) -> RequirementSpecification:
        text = intent.raw_input.lower()
        profile_id = match_reference_profile(text)

        if profile_id:
            return self._compile_from_profile(intent, profile_id)

        extracted = self._extract_explicit_parameters(text)
        conflicts = self._detect_conflicts(text, extracted)
        unrecognized = self._detect_unrecognized_terms(text)
        implausible = self._detect_implausible_parameters(extracted)

        decisions = self._build_decisions(intent, extracted, conflicts, unrecognized)
        requirements = self._compile_from_intent_constraints(intent, extracted)

        unresolved = [d for d in decisions if d.status == DecisionStatus.UNRESOLVED]
        critical_unresolved = [
            d for d in unresolved
            if d.category in {
                DecisionCategory.ARCHITECTURE,
                DecisionCategory.TARGET_OUTPUT,
                DecisionCategory.DUTY_CYCLE,
            }
        ]

        requirements = self._add_decision_requirements(intent, requirements, decisions)

        rationale_parts: list[str] = []
        if conflicts:
            rationale_parts.append(
                f"{len(conflicts)} conflicting requirement(s) detected and left unresolved."
            )
        if unrecognized:
            rationale_parts.append(
                f"{len(unrecognized)} unrecognized term(s) could not be mapped to the knowledge base."
            )
        if implausible:
            rationale_parts.append(
                f"{len(implausible)} parameter(s) flagged as physically implausible."
            )

        if critical_unresolved and len(requirements) == 1:
            return RequirementSpecification(
                status=SpecificationStatus.INCOMPLETE,
                object_type=intent.object_type,
                design_goal=intent.design_goal,
                requirements=requirements,
                required_decisions=decisions,
                resolved_parameters=extracted,
                unrecognized_terms=unrecognized,
                conflicts=conflicts,
                implausible_parameters=implausible,
                completeness_rationale=(
                    "Design intent incomplete — critical engineering decisions unresolved. "
                    "Resolve required decisions before generating quantitative constraints. "
                    + " ".join(rationale_parts)
                ).strip(),
            )

        if unresolved or conflicts or unrecognized or implausible:
            status = SpecificationStatus.INCOMPLETE
            rationale = (
                f"Partial specification — {len(unresolved)} decision(s) remain unresolved. "
                "Quantitative constraints derived only from explicit inputs. "
                + " ".join(rationale_parts)
            ).strip()
        else:
            status = SpecificationStatus.COMPLETE
            rationale = "All required engineering decisions resolved from prompt."

        return RequirementSpecification(
            status=status,
            object_type=intent.object_type,
            design_goal=intent.design_goal,
            requirements=requirements,
            required_decisions=decisions,
            resolved_parameters=extracted,
            unrecognized_terms=unrecognized,
            conflicts=conflicts,
            implausible_parameters=implausible,
            completeness_rationale=rationale,
        )

    def _compile_from_profile(
        self,
        intent: EngineeringIntent,
        profile_id: str,
    ) -> RequirementSpecification:
        profile = REFERENCE_PROFILES[profile_id]
        params = dict(profile["resolved_parameters"])
        requirements = compile_reference_requirements(profile_id)

        decisions = build_ice_required_decisions()
        for decision in decisions:
            param_key = decision.id
            if param_key == "target_horsepower" and "target_horsepower" in params:
                decision.status = DecisionStatus.RESOLVED
                decision.resolved_value = str(params["target_horsepower"])
            elif param_key == "target_torque" and "target_torque_nm" in params:
                decision.status = DecisionStatus.RESOLVED
                decision.resolved_value = str(params["target_torque_nm"])
            elif param_key in params or param_key.replace("_", "") in params:
                key = param_key if param_key in params else param_key
                for k, v in params.items():
                    if k.startswith(param_key.split("_")[0]) or k == param_key:
                        decision.status = DecisionStatus.RESOLVED
                        decision.resolved_value = str(v)
                        break
            elif decision.id == "engine_architecture" and "engine_architecture" in params:
                decision.status = DecisionStatus.RESOLVED
                decision.resolved_value = str(params["engine_architecture"])
            elif decision.id == "aspiration" and "aspiration" in params:
                decision.status = DecisionStatus.RESOLVED
                decision.resolved_value = str(params["aspiration"])
            elif decision.id == "duty_cycle" and "duty_cycle" in params:
                decision.status = DecisionStatus.RESOLVED
                decision.resolved_value = str(params["duty_cycle"])
            elif decision.id == "fuel_type" and "fuel_type" in params:
                decision.status = DecisionStatus.RESOLVED
                decision.resolved_value = str(params["fuel_type"])

        return RequirementSpecification(
            status=SpecificationStatus.COMPLETE,
            object_type=intent.object_type,
            design_goal=intent.design_goal,
            requirements=requirements,
            required_decisions=decisions,
            resolved_parameters=params,
            reference_profile=profile_id,
            completeness_rationale=f"Compiled from reference profile: {profile_id}",
        )

    @staticmethod
    def _parse_int_token(raw: str) -> int:
        """Parse integers that may include thousand separators (e.g. 500,000)."""
        return int(raw.replace(",", "").replace("_", ""))

    def _extract_explicit_parameters(self, text: str) -> dict[str, str | float | int]:
        params: dict[str, str | float | int] = {}

        displacement_match = re.search(r"(\d+(?:\.\d+)?)\s*l(?:itre|iter)?\b", text)
        if displacement_match:
            params["displacement_l"] = float(displacement_match.group(1))

        hp_match = re.search(
            r"([\d,]+)\s*(?:hp|bhp|horsepower)\b\.?", text, flags=re.IGNORECASE
        )
        if hp_match:
            params["target_horsepower"] = self._parse_int_token(hp_match.group(1))

        rpm_match = re.search(r"([\d,]+)\s*rpm\b", text)
        if rpm_match:
            params["max_rpm"] = self._parse_int_token(rpm_match.group(1))

        mass_match = re.search(r"under\s*([\d,]+)\s*kg", text)
        if mass_match:
            params["mass_kg"] = self._parse_int_token(mass_match.group(1))

        arch_patterns = [
            (r"\bv12\b", "V12", 12),
            (r"\bv10\b", "V10", 10),
            (r"\bv8\b", "V8", 8),
            (r"\bv6\b", "V6", 6),
            (r"\binline\s*6\b|\bi6\b", "Inline 6", 6),
            (r"\binline\s*4\b|\bi4\b", "Inline 4", 4),
            (r"\bflat\s*6\b", "Flat 6", 6),
        ]
        for pattern, arch, count in arch_patterns:
            if re.search(pattern, text):
                params["engine_architecture"] = arch
                params["cylinder_count"] = count
                break

        if re.search(r"\bnaturally\s*aspirated\b|\bna\b", text):
            params["aspiration"] = "Naturally aspirated"
        elif re.search(r"\bturbocharged\b|\bturbo\b", text):
            params["aspiration"] = "Turbocharged"
        elif re.search(r"\bsupercharged\b", text):
            params["aspiration"] = "Supercharged"

        # Detect fuel / ignition language for conflict checks (not silent resolution).
        if re.search(r"\bdiesel\b", text):
            params["fuel_type"] = "Diesel"
        elif re.search(r"\bgasoline\b|\bpetrol\b", text):
            params["fuel_type"] = "Gasoline"

        if re.search(r"\bspark\s*ignition\b|\bspark\s*ignited\b", text):
            params["ignition_type"] = "spark_ignition"
        elif re.search(r"\bcompression\s*ignition\b", text):
            params["ignition_type"] = "compression_ignition"

        return params

    def _detect_unrecognized_terms(self, text: str) -> list[dict[str, str]]:
        unrecognized: list[dict[str, str]] = []
        for term in self._UNKNOWN_MATERIAL_TERMS:
            if term in text:
                unrecognized.append(
                    {
                        "term": term,
                        "category": "material",
                        "reason": (
                            f"'{term}' does not match any entry in the materials knowledge base "
                            "and was not silently substituted."
                        ),
                    }
                )
        for term in self._UNKNOWN_COOLANT_TERMS:
            if term in text:
                unrecognized.append(
                    {
                        "term": term,
                        "category": "cooling",
                        "reason": (
                            f"'{term}' does not match any known cooling medium in the knowledge base "
                            "and was not silently substituted."
                        ),
                    }
                )
        return unrecognized

    def _detect_implausible_parameters(
        self,
        extracted: dict[str, str | float | int],
    ) -> list[dict[str, str | float | int]]:
        """Flag only structurally uncomputable values — never magnitude ceilings.

        Extreme-but-computable RPM/power/etc. must pass through physics + materials.
        """
        implausible: list[dict[str, str | float | int]] = []

        def _non_positive(parameter: str, label: str) -> None:
            value = extracted.get(parameter)
            if isinstance(value, (int, float)) and value <= 0:
                implausible.append(
                    {
                        "parameter": parameter,
                        "value": value,
                        "limit": 0,
                        "reason": (
                            f"{label} must be strictly positive to form well-defined "
                            f"engineering equations; got {value:g}."
                        ),
                    }
                )

        _non_positive("max_rpm", "max_rpm")
        _non_positive("target_horsepower", "target_horsepower")
        _non_positive("displacement_l", "displacement_l")

        cylinders = extracted.get("cylinder_count")
        if isinstance(cylinders, (int, float)):
            if cylinders <= 0 or float(cylinders) != int(cylinders):
                implausible.append(
                    {
                        "parameter": "cylinder_count",
                        "value": cylinders,
                        "limit": 1,
                        "reason": (
                            f"cylinder_count must be a positive integer for displacement "
                            f"partitioning; got {cylinders}."
                        ),
                    }
                )
        return implausible

    def _detect_conflicts(
        self,
        text: str,
        extracted: dict[str, str | float | int],
    ) -> list[dict[str, str]]:
        conflicts: list[dict[str, str]] = []

        # Category C1: mutually exclusive values for the single aspiration field.
        has_na = bool(re.search(r"\bnaturally\s*aspirated\b|\bna\b", text))
        has_turbo = bool(re.search(r"\bturbocharged\b|\bturbo\b", text))
        has_super = bool(re.search(r"\bsupercharged\b", text))
        aspiration_hits = sum([has_na, has_turbo, has_super])
        if aspiration_hits >= 2:
            claimed = []
            if has_na:
                claimed.append("Naturally aspirated")
            if has_turbo:
                claimed.append("Turbocharged")
            if has_super:
                claimed.append("Supercharged")
            # Do not silently pick one — clear aspiration and record the conflict.
            extracted.pop("aspiration", None)
            conflicts.append(
                {
                    "type": "mutually_exclusive_field",
                    "field": "aspiration",
                    "inputs": " + ".join(claimed),
                    "description": (
                        f"Conflicting aspiration values requested for a single field: "
                        f"{' and '.join(claimed)}. Aspiration left unresolved."
                    ),
                }
            )

        # Category C2: cross-field incompatibility (diesel + spark ignition).
        fuel = str(extracted.get("fuel_type", "")).lower()
        ignition = str(extracted.get("ignition_type", "")).lower()
        if "diesel" in fuel and ignition == "spark_ignition":
            conflicts.append(
                {
                    "type": "cross_field_incompatibility",
                    "field": "fuel_type+ignition_type",
                    "inputs": f"{extracted.get('fuel_type')} + spark ignition",
                    "description": (
                        "Conflicting requirements: diesel fuel with spark ignition. "
                        "Diesel requires compression ignition; spark ignition requires "
                        "a spark-ignitable fuel. Conflict left unresolved."
                    ),
                }
            )
            # Keep both visible but mark fuel decision conflicting via unresolved later.
            extracted.pop("fuel_type", None)

        return conflicts

    def _build_decisions(
        self,
        intent: EngineeringIntent,
        extracted: dict[str, str | float | int],
        conflicts: list[dict[str, str]] | None = None,
        unrecognized: list[dict[str, str]] | None = None,
    ) -> list[RequiredDecision]:
        decision_defs = self._OBJECT_DECISION_SETS.get(intent.object_type, ICE_REQUIRED_DECISIONS)
        decisions = [RequiredDecision(**d) for d in decision_defs]

        param_to_decision = {
            "engine_architecture": "engine_architecture",
            "aspiration": "aspiration",
            "target_horsepower": "target_horsepower",
            "duty_cycle": "duty_cycle",
            "fuel_type": "fuel_type",
        }

        conflicted_fields = {
            c.get("field", "").split("+")[0]
            for c in (conflicts or [])
            if c.get("type") == "mutually_exclusive_field"
        }
        for c in conflicts or []:
            if c.get("type") == "cross_field_incompatibility":
                for part in c.get("field", "").split("+"):
                    conflicted_fields.add(part)

        for decision in decisions:
            if decision.id in conflicted_fields:
                decision.status = DecisionStatus.UNRESOLVED
                decision.resolved_value = None
                matching = [c for c in (conflicts or []) if decision.id in c.get("field", "")]
                decision.rationale = matching[0]["description"] if matching else "Conflicting inputs"
                continue

            for param_key, decision_id in param_to_decision.items():
                if decision.id == decision_id and param_key in extracted:
                    decision.status = DecisionStatus.RESOLVED
                    decision.resolved_value = str(extracted[param_key])
                    decision.rationale = "Extracted from user prompt"
                    break

            if decision.id == "target_torque" and "target_torque_nm" in extracted:
                decision.status = DecisionStatus.RESOLVED
                decision.resolved_value = str(extracted["target_torque_nm"])

        for unknown in intent.unknowns:
            for decision in decisions:
                if unknown.replace("_", " ") in decision.id.replace("_", " "):
                    if decision.status == DecisionStatus.UNRESOLVED:
                        decision.rationale = f"Flagged as unknown in intent: {unknown}"

        # Category A: surface unrecognized terms as explicit unresolved decisions
        # (same mechanism as missing decisions — not a parallel channel).
        for term_info in unrecognized or []:
            decisions.append(
                RequiredDecision(
                    id=f"unrecognized_{term_info['category']}_{term_info['term'].replace(' ', '_')}",
                    category=DecisionCategory.CONSTRAINTS,
                    question=(
                        f"Unrecognized {term_info['category']} term '{term_info['term']}' "
                        "— map to a known knowledge-base entry or remove."
                    ),
                    options=[],
                    status=DecisionStatus.UNRESOLVED,
                    rationale=term_info["reason"],
                )
            )

        return decisions

    def _compile_from_intent_constraints(
        self,
        intent: EngineeringIntent,
        extracted: dict[str, str | float | int],
    ) -> list[CompiledRequirement]:
        requirements: list[CompiledRequirement] = []
        req_id = 0

        for spec in intent.constraints:
            if spec.value is not None:
                req_id += 1
                requirements.append(self._spec_to_requirement(spec, req_id))

        metric_map = {
            "max_rpm": ("max_rpm", "rpm"),
            "mass_kg": ("mass", "kg"),
            "target_horsepower": ("horsepower", "hp"),
            "displacement_l": ("displacement", "L"),
        }
        for param_key, (metric, unit) in metric_map.items():
            if param_key in extracted:
                req_id += 1
                requirements.append(
                    CompiledRequirement(
                        id=f"req_{req_id}",
                        description=f"{metric.replace('_', ' ').title()} from explicit prompt",
                        metric=metric,
                        target_value=extracted[param_key],
                        unit=unit,
                        priority=ConstraintPriority.HIGH,
                        source="explicit_prompt",
                        originating_text=intent.raw_input,
                        affected_assemblies=["root"],
                        downstream_design_consequences=[
                            f"Constrains {metric.replace('_', ' ')} calculations and validation"
                        ],
                        satisfies_decisions=[param_key],
                    )
                )

        for spec in intent.constraints:
            if spec.value is None and spec.type in {"performance", "reliability", "efficiency"}:
                continue

        return requirements

    def _add_decision_requirements(
        self,
        intent: EngineeringIntent,
        requirements: list[CompiledRequirement],
        decisions: list[RequiredDecision],
    ) -> list[CompiledRequirement]:
        result = list(requirements)
        next_id = len(result) + 1

        result.insert(
            0,
            CompiledRequirement(
                id="req_object_type",
                description=f"Design object type resolved as {intent.object_type}",
                metric="object_type",
                target_value=intent.object_type,
                priority=ConstraintPriority.CRITICAL,
                source="intent_parser",
                originating_text=intent.raw_input,
                affected_assemblies=["root"],
                downstream_design_consequences=[
                    "Selects functional decomposition template",
                    "Defines required engineering decision set",
                    "Initializes constraint graph even when numeric targets are absent",
                ],
                satisfies_decisions=["object_type"],
            )
        )

        for decision in decisions:
            if decision.status == DecisionStatus.UNRESOLVED:
                result.append(
                    CompiledRequirement(
                        id=f"req_unresolved_{next_id}",
                        description=f"Unresolved engineering decision: {decision.question}",
                        metric=decision.id,
                        target_value=None,
                        priority=ConstraintPriority.HIGH,
                        source="requirement_compiler",
                        originating_text=intent.raw_input,
                        affected_assemblies=["root"],
                        downstream_design_consequences=[
                            "Requires user or assumption-manager resolution before full validation",
                            "Reduces confidence for downstream engineering decisions",
                        ],
                        satisfies_decisions=[decision.id],
                    )
                )
                next_id += 1

        return result

    @staticmethod
    def _spec_to_requirement(spec: ConstraintSpec, req_id: int) -> CompiledRequirement:
        return CompiledRequirement(
            id=f"req_{req_id}",
            description=spec.description or spec.type,
            metric=spec.type,
            target_value=spec.value,
            priority=spec.priority,
            source="intent",
            originating_text=spec.description,
            affected_assemblies=["root"],
            downstream_design_consequences=["Constrains generated architecture"],
        )
