"""Independent geometry model verification — must not import production GeometryModel."""

from __future__ import annotations

import math

from verification.formulas import (
    bore_mm_from_displacement_stroke,
    crank_radius_mm,
    piston_area_m2,
    stroke_m_from_volume_ratio,
)


def test_bore_from_known_f20c_geometry():
    # Honda F20C: 87 x 84, 1.997 L, 4 cyl
    bore = bore_mm_from_displacement_stroke(1.997, 4, 84.0)
    assert abs(bore - 87.0) < 0.2


def test_stroke_from_volume_ratio_identity():
    # V = n*(π/4)*bore²*stroke with λ=bore/stroke → consistent identity
    stroke_m = stroke_m_from_volume_ratio(0.0005, 1.1)
    assert stroke_m > 0
    bore_m = 1.1 * stroke_m
    vol = math.pi / 4.0 * bore_m**2 * stroke_m
    assert abs(vol - 0.0005) / 0.0005 < 1e-9


def test_crank_and_area():
    assert crank_radius_mm(80.0) == 40.0
    assert abs(piston_area_m2(100.0) - (math.pi * 0.05**2)) < 1e-12
