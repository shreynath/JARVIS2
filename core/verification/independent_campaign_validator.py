"""Independent campaign validator — raw equations only.

MUST NOT import:
  PhysicsEngine, MaterialAssigner, ConstraintEvaluator, EngineeringEvaluator
"""

from __future__ import annotations

import math
from typing import Any

_HP_TO_W = 745.6998715822702
_HP_TO_KW = 0.745699872


class IndependentCampaignValidator:
    """Recalculate campaign identities from first principles."""

    def torque_nm(self, horsepower: float, rpm: float) -> float:
        if rpm == 0:
            raise ZeroDivisionError("rpm must be nonzero")
        return (horsepower * _HP_TO_W) / (2.0 * math.pi * rpm / 60.0)

    def mean_piston_speed_m_s(self, stroke_m: float, rpm: float) -> float:
        return 2.0 * stroke_m * rpm / 60.0

    def bmep_bar(self, torque_nm: float, displacement_l: float) -> float:
        """Four-stroke BMEP = 4π T / V_d → Pa → bar."""
        v_m3 = displacement_l / 1000.0
        if v_m3 <= 0:
            raise ZeroDivisionError("displacement must be positive")
        return (4.0 * math.pi * torque_nm / v_m3) / 1e5

    def displacement_l(self, horsepower: float, rpm: float, bmep_bar: float) -> float:
        if rpm == 0:
            raise ZeroDivisionError("rpm must be nonzero")
        bmep_pa = bmep_bar * 1e5
        power_w = horsepower * _HP_TO_KW * 1000.0
        return power_w * 120.0 / (bmep_pa * rpm) * 1000.0

    def peak_piston_acceleration_m_s2(self, stroke_m: float, rpm: float) -> float:
        r = stroke_m / 2.0
        omega = 2.0 * math.pi * rpm / 60.0
        return r * omega**2

    def inertia_force_n(self, mass_kg: float, stroke_m: float, rpm: float) -> float:
        return mass_kg * self.peak_piston_acceleration_m_s2(stroke_m, rpm)

    def stress_mpa(self, load_n: float, area_m2: float) -> float:
        if area_m2 == 0:
            raise ZeroDivisionError("area must be nonzero")
        return (load_n / area_m2) / 1e6

    def fatigue_margin(self, fatigue_mpa: float, alternating_mpa: float) -> float | None:
        if alternating_mpa <= 0:
            return None
        return fatigue_mpa / alternating_mpa

    def buckling_margin(
        self,
        youngs_pa: float,
        second_moment_m4: float,
        length_m: float,
        applied_n: float,
        *,
        k: float = 1.0,
    ) -> float | None:
        if length_m <= 0 or applied_n <= 0:
            return None
        pcr = (math.pi**2) * youngs_pa * second_moment_m4 / (k * length_m) ** 2
        return pcr / applied_n

    def rod_stress_packet(self, case: dict[str, Any]) -> dict[str, Any]:
        """Independent rod loading / stress / margins for one case."""
        rpm = case.get("rpm")
        stroke_mm = case.get("stroke_mm")
        piston_g = case.get("piston_mass_g")
        rod_g = case.get("rod_mass_g")
        rod_length_mm = case.get("rod_length_mm")
        out: dict[str, Any] = {
            "engine": case.get("engine_name") or case.get("engine_id"),
            "computable": False,
        }
        if rpm is None or stroke_mm is None or piston_g is None:
            out["blocking"] = "missing_rpm_stroke_or_piston_mass"
            return out
        stroke_m = float(stroke_mm) / 1000.0
        mass_kg = float(piston_g) / 1000.0
        if rod_g is not None:
            mass_kg += 0.35 * (float(rod_g) / 1000.0)
        force = self.inertia_force_n(mass_kg, stroke_m, float(rpm))
        # Placeholder section for formula exercise (not OEM geometry).
        area = 0.01 * 0.02
        stress = self.stress_mpa(force, area)
        out.update(
            {
                "computable": True,
                "rod_loading_n": force,
                "rod_stress_mpa": stress,
                "stress_mpa": stress,
                "peak_accel_m_s2": self.peak_piston_acceleration_m_s2(stroke_m, float(rpm)),
            }
        )
        rcd = case.get("reported_component_data") or {}
        fatigue = rcd.get("fatigue_strength_mpa") or case.get("fatigue_strength_mpa")
        if fatigue is not None:
            out["fatigue_margin"] = self.fatigue_margin(float(fatigue), stress)
        if rod_length_mm is not None:
            length_m = float(rod_length_mm) / 1000.0
            i = (0.01 * 0.02**3) / 12.0
            out["buckling_margin"] = self.buckling_margin(200e9, i, length_m, force)
            out["buckling_note"] = "Placeholder section — identity check only"
        return out

    def validate_packet(
        self,
        *,
        horsepower: float | None = None,
        rpm: float | None = None,
        stroke_m: float | None = None,
        torque_nm: float | None = None,
        displacement_l: float | None = None,
    ) -> dict[str, Any]:
        packet: dict[str, Any] = {"independent_verifier": True}
        if horsepower is not None and rpm is not None:
            packet["torque_nm"] = self.torque_nm(horsepower, rpm)
        if stroke_m is not None and rpm is not None:
            packet["mean_piston_speed_m_s"] = self.mean_piston_speed_m_s(stroke_m, rpm)
            packet["peak_piston_acceleration_m_s2"] = self.peak_piston_acceleration_m_s2(
                stroke_m, rpm
            )
        if torque_nm is not None and displacement_l is not None:
            packet["bmep_bar"] = self.bmep_bar(torque_nm, displacement_l)
        if horsepower is not None and rpm is not None and packet.get("bmep_bar") is not None:
            packet["displacement_l_check"] = self.displacement_l(
                horsepower, rpm, float(packet["bmep_bar"])
            )
        return packet
