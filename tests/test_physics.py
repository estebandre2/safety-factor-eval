import math
import statistics

import pytest

from sfe import physics as p


def test_gumbel_known_value():
    data = [100, 120, 90, 150, 110, 130, 95, 140, 105, 125]
    t = 100
    k = -(math.sqrt(6) / math.pi) * (0.5772 + math.log(math.log(t / (t - 1))))
    assert k == pytest.approx(3.137, abs=1e-3)
    expected = statistics.mean(data) + k * statistics.stdev(data)
    assert p.gumbel_design_flood(data, t) == pytest.approx(expected, rel=1e-9)


def test_spillway_capacity():
    assert p.spillway_capacity(2.1, 20.0, 2.0) == pytest.approx(2.1 * 20 * 2**1.5)


def test_hazen_williams():
    expected = 10.67 * 1000 * 0.05**1.852 / (130**1.852 * 0.25**4.87)
    assert p.hazen_williams_headloss(0.05, 1000, 0.25, 130) == pytest.approx(expected)


def test_delivery_pressure_head():
    assert p.delivery_pressure_head(100.0, 40.0, 12.5) == pytest.approx(47.5)


def test_sliding_and_overturning_reference_dam():
    # Height 20 m, water 18 m, crest 4 m, base 16 m, full uplift, mu 0.7. Heel at x=0, toe at x=16.
    # Rectangle: W1 = 24*4*20 = 1920 kN/m, centroid x=2 -> arm to toe 14 -> 26880 kN·m/m
    # Triangle: W2 = 24*0.5*12*20 = 2880 kN/m, centroid x=4+12/3=8 -> arm 8 -> 23040 kN·m/m
    # W = 4800; M_resisting = 49920
    # H = 9.81*18^2/2 = 1589.22 kN/m at 18/3 = 6 m -> 9535.32
    # U = 1.0*9.81*18*16/2 = 1412.64 kN/m at 16/3 from heel -> arm 16-16/3 = 10.6667 -> 15068.16
    # Sliding FS = 0.7*(4800-1412.64)/1589.22 = 1.49202
    # Overturning FS = 49920/(9535.32+15068.16) = 2.02897
    f = p.dam_forces(20, 18, 4, 16, 1.0)
    assert f["W"] == pytest.approx(4800)
    assert f["U"] == pytest.approx(1412.64)
    assert f["H"] == pytest.approx(1589.22)
    assert f["M_resisting"] == pytest.approx(49920)
    assert f["M_overturning"] == pytest.approx(24603.48)
    assert p.sliding_fs(20, 18, 4, 16, 1.0, 0.7) == pytest.approx(1.49202, rel=1e-4)
    assert p.overturning_fs(20, 18, 4, 16, 1.0) == pytest.approx(2.02897, rel=1e-4)


def test_fs_monotonic():
    base = dict(height=20, water_depth=18, crest_width=4, base_width=16, uplift_factor=1.0)
    assert p.sliding_fs(**base, mu=0.75) > p.sliding_fs(**base, mu=0.7)
    assert p.sliding_fs(**{**base, "base_width": 18}, mu=0.7) > p.sliding_fs(**base, mu=0.7)
    assert p.overturning_fs(**{**base, "water_depth": 19}) < p.overturning_fs(**base)
