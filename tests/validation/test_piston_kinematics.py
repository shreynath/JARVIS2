"""Independent piston kinematics verification — does not import PhysicsEngine."""

from __future__ import annotations

from verification.formulas import mean_piston_speed_m_s, peak_piston_acceleration_m_s2, percent_error


def test_mps_honda_f20c_redline():
    # 84 mm stroke @ 9000 rpm → 25.2 m/s
    mps = mean_piston_speed_m_s(0.084, 9000.0)
    assert percent_error(25.2, mps) < 0.1


def test_acceleration_scales_with_rpm_squared_fixed_stroke():
    stroke = 0.08
    a1 = peak_piston_acceleration_m_s2(stroke, 6000.0)
    a2 = peak_piston_acceleration_m_s2(stroke, 12000.0)
    assert percent_error(4.0, a2 / a1) < 0.1
