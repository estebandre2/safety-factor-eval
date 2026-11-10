"""Study II families (spec 2026-11-10 §3): a hinged gate and a gravity retaining wall, both with an orientation
that decides whether the correct lever arm of a triangular load is 1/3 ("easy") or 2/3 ("hard") of its length."""
from __future__ import annotations

from sfe.physics import GAMMA_C, GAMMA_W

GATE_HINGES = ("bottom", "top")
WALL_BATTERS = ("front", "back")


def gate_latch_reaction(depth: float, width: float, hinge: str) -> float:
    """Vertical gate from the water surface down to `depth`, hinged at one edge, held by a latch at the other.

    Hydrostatic force F = gamma_w * depth^2 / 2 * width acts depth/3 above the bottom edge.
    Bottom hinge: arm depth/3 (easy). Top hinge, at the surface: arm 2*depth/3 (hard).
    Latch reaction = F * arm / depth.
    """
    if hinge not in GATE_HINGES:
        raise ValueError(f"hinge must be one of {GATE_HINGES}")
    force = GAMMA_W * depth**2 / 2 * width
    arm = depth / 3 if hinge == "bottom" else 2 * depth / 3
    return force * arm / depth


def wall_forces(height: float, base_width: float, top_width: float, ka: float, gamma_s: float,
                batter: str) -> dict[str, float]:
    """Gravity wall = rectangle (top_width x height) + triangle ((base_width - top_width) x height), moments about the toe.

    front batter: the triangle is on the toe side with its apex at the toe -> centroid 2/3 of its base from the toe (hard).
    back batter: the rectangle is at the toe; the triangle's vertical side is at x = top_width, apex at the heel
    -> centroid top_width + (base_width - top_width)/3 from the toe (easy).
    Rankine active thrust Pa = Ka * gamma_s * height^2 / 2, acting height/3 above the base (easy).
    """
    if batter not in WALL_BATTERS:
        raise ValueError(f"batter must be one of {WALL_BATTERS}")
    tri_base = base_width - top_width
    w_rect = GAMMA_C * top_width * height
    w_tri = GAMMA_C * 0.5 * tri_base * height
    if batter == "front":
        arm_rect, arm_tri = tri_base + top_width / 2, 2 * tri_base / 3
    else:
        arm_rect, arm_tri = top_width / 2, top_width + tri_base / 3
    thrust = ka * gamma_s * height**2 / 2
    return {"W": w_rect + w_tri, "Pa": thrust, "M_resisting": w_rect * arm_rect + w_tri * arm_tri,
            "M_overturning": thrust * height / 3}


def wall_overturning_fs(height: float, base_width: float, top_width: float, ka: float, gamma_s: float,
                        batter: str) -> float:
    f = wall_forces(height, base_width, top_width, ka, gamma_s, batter)
    return f["M_resisting"] / f["M_overturning"]
