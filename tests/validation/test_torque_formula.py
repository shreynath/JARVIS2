"""Independent torque formula verification — does not import PhysicsEngine."""

from __future__ import annotations

from verification.formulas import percent_error, torque_nm_from_english, torque_nm_from_hp_rpm


def test_torque_formula_si_matches_english_within_0_1_percent():
    hp, rpm = 800.0, 9000.0
    si = torque_nm_from_hp_rpm(hp, rpm)
    en = torque_nm_from_english(hp, rpm)
    assert percent_error(en, si) < 0.1


def test_torque_known_point():
    # 800 hp @ 9000 rpm ≈ 633 N·m
    t = torque_nm_from_hp_rpm(800.0, 9000.0)
    assert abs(t - 633.0) / 633.0 < 0.01
