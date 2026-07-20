"""Independent rod model verification — must not import ConnectingRodModel."""

from __future__ import annotations

from verification.formulas import euler_buckling_load_n, i_beam_area_m2, rod_stress_mpa


def test_i_beam_area_positive():
    area = i_beam_area_m2(
        web_thickness=0.008,
        depth=0.05,
        flange_width=0.03,
        flange_thickness=0.008,
    )
    assert area > 0


def test_euler_buckling_increases_with_stiffness():
    soft = euler_buckling_load_n(200e9, 1e-8, 0.15)
    stiff = euler_buckling_load_n(200e9, 2e-8, 0.15)
    assert stiff == soft * 2


def test_rod_stress_identity():
    assert abs(rod_stress_mpa(50_000, 5e-4) - 100.0) < 1e-9
