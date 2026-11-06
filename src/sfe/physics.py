"""Hydraulic design-check formulas (SI units: kN, m, m³/s). All functions are pure."""
import math
import statistics

GAMMA_W = 9.81  # unit weight of water, kN/m³
GAMMA_C = 24.0  # unit weight of concrete, kN/m³
EULER_GAMMA = 0.5772


def dam_forces(height: float, water_depth: float, crest_width: float, base_width: float, uplift_factor: float) -> dict[str, float]:
    """Forces and moments per metre of a gravity dam with a vertical upstream face.

    Section = rectangle (crest_width × height) + downstream triangle ((base_width − crest_width) × height).
    Heel at x = 0, toe at x = base_width; moments are taken about the toe.
    Uplift is triangular (full at the heel, zero at the toe), scaled by uplift_factor.
    """
    w_rect = GAMMA_C * crest_width * height
    w_tri = GAMMA_C * 0.5 * (base_width - crest_width) * height
    arm_rect = base_width - crest_width / 2
    arm_tri = base_width - (crest_width + (base_width - crest_width) / 3)

    h_force = GAMMA_W * water_depth**2 / 2
    uplift = uplift_factor * GAMMA_W * water_depth * base_width / 2
    arm_uplift = base_width - base_width / 3

    return {
        "W": w_rect + w_tri,
        "U": uplift,
        "H": h_force,
        "M_resisting": w_rect * arm_rect + w_tri * arm_tri,
        "M_overturning": h_force * water_depth / 3 + uplift * arm_uplift,
    }


def sliding_fs(height: float, water_depth: float, crest_width: float, base_width: float, uplift_factor: float, mu: float) -> float:
    f = dam_forces(height, water_depth, crest_width, base_width, uplift_factor)
    return mu * (f["W"] - f["U"]) / f["H"]


def overturning_fs(height: float, water_depth: float, crest_width: float, base_width: float, uplift_factor: float) -> float:
    f = dam_forces(height, water_depth, crest_width, base_width, uplift_factor)
    return f["M_resisting"] / f["M_overturning"]


def gumbel_design_flood(annual_maxima: list[float], return_period: float) -> float:
    """Q_T = mean + K·s with the Gumbel frequency factor and the sample standard deviation."""
    t = return_period
    k = -(math.sqrt(6) / math.pi) * (EULER_GAMMA + math.log(math.log(t / (t - 1))))
    return statistics.mean(annual_maxima) + k * statistics.stdev(annual_maxima)


def spillway_capacity(c: float, length: float, head: float) -> float:
    """Free-overflow weir: Q = C·L·H^1.5."""
    return c * length * head**1.5


def hazen_williams_headloss(flow: float, length: float, diameter: float, c: float) -> float:
    """hf = 10.67·L·Q^1.852 / (C^1.852 · D^4.87)."""
    return 10.67 * length * flow**1.852 / (c**1.852 * diameter**4.87)


def delivery_pressure_head(source_elev: float, delivery_elev: float, headloss: float) -> float:
    return (source_elev - delivery_elev) - headloss
