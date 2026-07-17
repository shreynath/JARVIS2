"""Assumption manager — records unknowns with defaults."""

from __future__ import annotations

from core.ir.constraint import Assumption
from core.ir.design_graph import EngineeringDesignGraph, EngineeringIntent

DEFAULT_ASSUMPTIONS: dict[str, dict[str, str | float]] = {
    "displacement": {"value": "6.0L", "rationale": "Typical high-performance V12 displacement", "confidence": 0.4},
    "compression_ratio": {"value": "12.5:1", "rationale": "High-performance NA engine typical CR", "confidence": 0.5},
    "fuel_system": {"value": "port fuel injection", "rationale": "Standard for performance NA engines", "confidence": 0.6},
    "cooling_capacity": {"value": "adequate for track use", "rationale": "Performance engine cooling requirement", "confidence": 0.4},
    "bore_stroke_ratio": {"value": "oversquare", "rationale": "High-revving performance orientation", "confidence": 0.5},
    "max_rpm": {"value": "8500", "rationale": "Performance NA engine redline", "confidence": 0.4},
}


class AssumptionManager:
    """Fill unknowns from intent with documented assumptions."""

    def fill_unknowns(self, graph: EngineeringDesignGraph, intent: EngineeringIntent) -> EngineeringDesignGraph:
        assumptions: list[Assumption] = []
        for i, unknown in enumerate(intent.unknowns):
            defaults = DEFAULT_ASSUMPTIONS.get(unknown, {
                "value": "to be determined",
                "rationale": f"No default available for {unknown}",
                "confidence": 0.2,
            })
            assumptions.append(
                Assumption(
                    id=f"assumption_{i + 1}",
                    field=unknown,
                    assumed_value=str(defaults["value"]),
                    rationale=str(defaults.get("rationale", "")),
                    confidence=float(defaults.get("confidence", 0.3)),
                )
            )
        graph.assumptions = assumptions
        return graph
