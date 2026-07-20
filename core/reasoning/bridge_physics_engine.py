"""Bridge / civil physics engine — truss reference domain (Phase F)."""

from __future__ import annotations

from core.engineering.truss_bridge_model import TrussBridgeModel
from core.epistemology import KnowledgeState
from core.epistemology.input_requirement import MissingEngineeringInputError
from core.ir.requirement_spec import RequirementSpecification
from core.reasoning.physics_engine import PhysicsAnalysis, make_physics_calculation


def analyze_bridge(requirement_spec: RequirementSpecification) -> PhysicsAnalysis:
    """Quantitative truss member demand from span and assumed live load."""
    params = requirement_spec.resolved_parameters
    span_m = _float_param(params, "span_m")
    if span_m is None:
        raise MissingEngineeringInputError(
            "span_m",
            "Bridge physics requires resolved span_m (e.g. 'spanning 40 meters').",
        )

    analysis = PhysicsAnalysis()
    model = TrussBridgeModel()
    result = model.estimate(
        span_m=span_m,
        live_load_kn_per_m=_float_param(params, "live_load_kn_per_m"),
    )
    if result.estimate is None:
        analysis.warnings.append("Truss bridge model returned no estimate.")
        return analysis

    analysis.engineering_attachments["truss_bridge"] = result.to_dict()
    est = result.estimate

    analysis.calculations.append(
        make_physics_calculation(
            id="calc_bridge_deck_moment",
            name="Equivalent deck moment",
            formula="M_max = w * L^2 / 8",
            inputs={
                "span_m": span_m,
                "live_load_kn_per_m": est.live_load_kn_per_m,
                "w_n_per_m": est.live_load_kn_per_m * 1000.0,
            },
            result=round(est.live_load_kn_per_m * 1000.0 * span_m**2 / 8.0, 0),
            unit="N·m",
            method="Simply-supported equivalent beam moment for deck live load.",
            assumptions=list(est.assumptions),
            knowledge_state=KnowledgeState.DERIVED,
            confidence="medium",
            assessment="Deck moment drives truss chord demand estimate.",
            passes=True,
        )
    )

    stress_range = (
        round(est.max_member_stress_mpa * 0.85, 2),
        round(est.max_member_stress_mpa * 1.15, 2),
    )
    analysis.calculations.append(
        make_physics_calculation(
            id="calc_truss_member_stress",
            name="Truss member axial stress estimate",
            formula="sigma = F_member / A_member; F_member ≈ M_max / truss_depth",
            inputs={
                "span_m": span_m,
                "truss_depth_m": est.truss_depth_m,
                "member_area_m2": est.member_area_m2,
                "max_member_force_n": est.max_member_force_n,
            },
            result=est.max_member_stress_mpa,
            value_range=stress_range,
            unit="MPa",
            method="Warren/Pratt truss analogy via equivalent beam moment and depth.",
            assumptions=list(est.assumptions),
            dependency_ids=["calc_bridge_deck_moment"],
            knowledge_state=KnowledgeState.ASSUMED,
            confidence="medium",
            assessment="Structural steel must provide yield margin above member stress band.",
            passes=True,
        )
    )
    analysis.bind_operating("truss_member_stress_mpa", "calc_truss_member_stress", use_high=True)
    return analysis


def _float_param(params: dict, key: str) -> float | None:
    value = params.get(key)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
