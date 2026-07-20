"""Truss bridge structural model — cited formulas, explicit assumptions (Phase F reference)."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from core.epistemology.assumption_registry import AssumptionRegistry

# AASHTO / structural steel design references for formula identity — load magnitude is ASSUMED.
DEFAULT_LIVE_LOAD_KN_PER_M = 20.0
DEFAULT_TRUSS_DEPTH_RATIO = 0.10  # depth = span * ratio
DEFAULT_PANEL_COUNT = 8
DEFAULT_MEMBER_AREA_M2 = (4.0e-3, 8.0e-3)  # W-shape range — ASSUMED if not specified


@dataclass(frozen=True)
class TrussBridgeEstimate:
    span_m: float
    live_load_kn_per_m: float
    truss_depth_m: float
    max_member_force_n: float
    max_member_stress_mpa: float
    member_area_m2: float
    assumptions: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "span_m": self.span_m,
            "live_load_kn_per_m": self.live_load_kn_per_m,
            "truss_depth_m": self.truss_depth_m,
            "max_member_force_n": self.max_member_force_n,
            "max_member_stress_mpa": self.max_member_stress_mpa,
            "member_area_m2": self.member_area_m2,
            "assumptions": list(self.assumptions),
        }


@dataclass
class TrussBridgeModelResult:
    estimate: TrussBridgeEstimate | None = None
    assumption_records: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "estimate": None if self.estimate is None else self.estimate.to_dict(),
            "assumption_records": list(self.assumption_records),
        }


class TrussBridgeModel:
    """Simplified Warren/Pratt truss member demand from equivalent beam + depth.

    References:
    - Hibbeler, *Structural Analysis*, truss / internal force fundamentals
    - AASHTO LRFD Bridge Design Specifications (load magnitude bands — parameters ASSUMED here)
    """

    def estimate(
        self,
        *,
        span_m: float,
        live_load_kn_per_m: float | None = None,
        truss_depth_m: float | None = None,
        member_area_m2: float | None = None,
        registry: AssumptionRegistry | None = None,
    ) -> TrussBridgeModelResult:
        reg = registry if registry is not None else AssumptionRegistry()
        if span_m <= 0:
            return TrussBridgeModelResult()

        w = live_load_kn_per_m if live_load_kn_per_m is not None else DEFAULT_LIVE_LOAD_KN_PER_M
        depth = truss_depth_m if truss_depth_m is not None else span_m * DEFAULT_TRUSS_DEPTH_RATIO
        area = member_area_m2 if member_area_m2 is not None else sum(DEFAULT_MEMBER_AREA_M2) / 2.0

        if live_load_kn_per_m is None:
            reg.record(
                id="bridge_live_load",
                field="live_load_kn_per_m",
                assumed_value=w,
                rationale="Highway live load not specified — representative 20 kN/m band (ASSUMED)",
                source_model="TrussBridgeModel",
                confidence="low",
                category="engineering",
            )
        if truss_depth_m is None:
            reg.record(
                id="bridge_truss_depth",
                field="truss_depth_m",
                assumed_value=depth,
                rationale=f"Truss depth not specified — depth = span × {DEFAULT_TRUSS_DEPTH_RATIO}",
                source_model="TrussBridgeModel",
                confidence="medium",
                category="engineering",
            )
        if member_area_m2 is None:
            reg.record(
                id="bridge_member_area",
                field="member_area_m2",
                assumed_value=area,
                rationale="Member section not sized — representative steel area band (ASSUMED)",
                source_model="TrussBridgeModel",
                confidence="low",
                category="engineering",
            )

        # Equivalent simply-supported deck: M_max = w L² / 8  (w in N/m)
        w_n_per_m = w * 1000.0
        m_max = w_n_per_m * span_m**2 / 8.0
        # Upper chord axial demand ~ M / depth (order-of-magnitude truss analogy)
        force_n = m_max / max(depth, 0.1)
        stress_pa = force_n / max(area, 1e-6)
        stress_mpa = stress_pa / 1e6

        est = TrussBridgeEstimate(
            span_m=span_m,
            live_load_kn_per_m=w,
            truss_depth_m=depth,
            max_member_force_n=round(force_n, 0),
            max_member_stress_mpa=round(stress_mpa, 2),
            member_area_m2=area,
            assumptions=tuple(reg.as_strings()),
        )
        return TrussBridgeModelResult(estimate=est, assumption_records=reg.as_dicts())
