"""Independent mass model verification — must not import ReciprocatingMassModel."""

from __future__ import annotations

from verification.formulas import piston_shell_mass_kg


def test_piston_shell_mass_scales_with_bore():
    small = piston_shell_mass_kg(80.0, 80.0)
    large = piston_shell_mass_kg(100.0, 80.0)
    assert large > small > 0.05


def test_piston_shell_mass_known_point():
    # Sanity: ~87×84 Al piston body should be order ~0.3–0.6 kg for these heuristics
    m = piston_shell_mass_kg(87.0, 84.0)
    assert 0.15 < m < 1.2
