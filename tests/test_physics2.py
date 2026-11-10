"""Study II families: hand calculations for the gate and the retaining wall."""
import pytest

from sfe.physics2 import gate_latch_reaction, wall_forces, wall_overturning_fs

GW = 9.81


def test_gate_bottom_hinge_latch_takes_one_third():
    # d = 3 m, w = 2 m: F = 9.81 * 9 / 2 * 2 = 88.29 kN, resultant 1 m above the bottom hinge
    # latch at the top edge: R * 3 = 88.29 * 1 -> R = 29.43 kN
    assert gate_latch_reaction(depth=3.0, width=2.0, hinge="bottom") == pytest.approx(29.43)


def test_gate_top_hinge_latch_takes_two_thirds():
    # hinge at the surface: resultant 2 m below the hinge; latch at the bottom: R * 3 = 88.29 * 2 -> 58.86 kN
    assert gate_latch_reaction(depth=3.0, width=2.0, hinge="top") == pytest.approx(58.86)


def test_wall_front_batter_hand_calc():
    # H = 6, B = 4, b = 1, gamma_c = 24, Ka = 0.3, gamma_s = 18
    # rectangle 1x6 -> 144 kN at 4 - 0.5 = 3.5 m from toe -> 504
    # triangle 3x6/2 = 9 m2 -> 216 kN, apex at the toe -> centroid 2/3*3 = 2.0 m -> 432
    # Pa = 0.5*0.3*18*36 = 97.2 kN at 2 m -> 194.4 ; FS = 936 / 194.4 = 4.8148
    f = wall_forces(height=6.0, base_width=4.0, top_width=1.0, ka=0.3, gamma_s=18.0, batter="front")
    assert f["M_resisting"] == pytest.approx(936.0)
    assert f["M_overturning"] == pytest.approx(194.4)
    assert wall_overturning_fs(6.0, 4.0, 1.0, 0.3, 18.0, "front") == pytest.approx(936.0 / 194.4)


def test_wall_back_batter_hand_calc():
    # rectangle at the toe side: 144 kN at 0.5 m -> 72
    # triangle vertical side at x = 1, apex at the heel (x = 4): centroid 1 + 3/3 = 2.0 m -> 432
    # FS = 504 / 194.4
    f = wall_forces(6.0, 4.0, 1.0, 0.3, 18.0, "back")
    assert f["M_resisting"] == pytest.approx(504.0)
    assert wall_overturning_fs(6.0, 4.0, 1.0, 0.3, 18.0, "back") == pytest.approx(504.0 / 194.4)


def test_bad_orientation_rejected():
    with pytest.raises(ValueError):
        gate_latch_reaction(3.0, 2.0, "side")
    with pytest.raises(ValueError):
        wall_forces(6.0, 4.0, 1.0, 0.3, 18.0, "up")
