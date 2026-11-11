"""Study II Phase 1 case set (spec 2026-11-10 §3): new overturning geometries, a hinged gate and a gravity
retaining wall generated in both orientations, and a sliding control. Truth computed by code."""
from __future__ import annotations

import json
from dataclasses import asdict, replace
from pathlib import Path

import numpy as np
from scipy.optimize import brentq

from sfe import cases as c1
from sfe.cases import BANDS, Case
from sfe.physics import GAMMA_C, GAMMA_W
from sfe.physics2 import gate_latch_reaction, wall_overturning_fs

SEED = 2027
WALL_REQUIRED_FS = 2.0
PAIR_PLAN = ("SAFE",) * 8 + ("UNSAFE",) * 8 + ("BORDERLINE",) * 4  # per orientation, 20 geometries

GATE_TEXT = (
    "A vertical rectangular gate closes an opening whose top edge is at the water surface and whose bottom edge is at "
    "the stated depth. The gate is hinged at its {hinge} edge and held closed by a latch at its {latch} edge. "
    "Hydrostatic pressure only (water 9.81 kN/m3), atmospheric pressure on both sides; ignore the gate's weight and "
    "hinge friction. Take moments about the hinge to find the latch reaction."
)
WALL_TEXT = (
    "Gravity retaining wall, per metre length. The cross-section is a rectangle (top width x wall height) plus a "
    "triangle that makes up the rest of the base width. {faces} Concrete unit weight 24 kN/m3. Rankine active earth "
    "pressure acts horizontally on a vertical plane through the back of the base: Pa = Ka * gamma_s * H^2 / 2. "
    "Ignore the weight of soil over the battered face, passive pressure, water and surcharge. "
    "FS_overturning = resisting moments / overturning moments, both about the toe."
)
WALL_FACES = {
    "easy": "The front face (toe side) is vertical and the back face is battered, so the triangle is on the back "
            "(heel) side with its apex at the heel.",
    "hard": "The back face is vertical and the front face is battered, so the triangle is on the front (toe) side "
            "with its apex at the toe.",
}


def orientation(case: Case) -> str | None:
    return case.id.rsplit("-", 1)[-1] if case.family in ("gate", "wall") else None


def pair_id(case: Case) -> str | None:
    return case.id.rsplit("-", 1)[0] if case.family in ("gate", "wall") else None


def _target(rng: np.random.Generator, category: str) -> float:
    lo, hi = BANDS[category]
    pad = (hi - lo) * 0.1
    return float(rng.uniform(lo + pad, hi - pad))


def _gate_case(idx: int, o: str, cat: str, depth: float, width: float, rng: np.random.Generator) -> Case:
    hinge, latch = ("bottom", "top") if o == "easy" else ("top", "bottom")
    reaction = gate_latch_reaction(depth, width, hinge)
    for _ in range(100):
        capacity = round(reaction * _target(rng, cat), 1)
        ratio = capacity / reaction
        if BANDS[cat][0] <= ratio < BANDS[cat][1]:
            break
    else:
        raise RuntimeError("gate category not reachable")
    return Case(id=f"s2-gate-{idx:02d}-{o}", family="gate", category=cat,
                inputs={"gate_height": depth, "gate_width": width, "latch_capacity": capacity},
                assumptions=GATE_TEXT.format(hinge=hinge, latch=latch),
                criterion="Latch capacity >= latch reaction", required=capacity, true_value=reaction,
                ratio=ratio, verdict="SAFE" if cat == "SAFE" else "UNSAFE",
                flawed_value=None, flawed_ratio=None, flawed_step=None)


def _wall_case(idx: int, o: str, cat: str, geo: dict, rng: np.random.Generator) -> Case | None:
    batter = "back" if o == "easy" else "front"
    h, b, ka, gs = geo["wall_height"], geo["top_width"], geo["ka"], geo["gamma_s"]
    target = _target(rng, cat)

    def gap(base: float) -> float:
        return wall_overturning_fs(h, base, b, ka, gs, batter) / WALL_REQUIRED_FS - target

    lo, hi = b + 0.3, 1.5 * h
    if gap(lo) * gap(hi) > 0:
        return None
    base = round(brentq(gap, lo, hi), 2)
    fs = wall_overturning_fs(h, base, b, ka, gs, batter)
    ratio = fs / WALL_REQUIRED_FS
    if not BANDS[cat][0] <= ratio < BANDS[cat][1] or base - b < 0.5:
        return None
    return Case(id=f"s2-wall-{idx:02d}-{o}", family="wall", category=cat,
                inputs={"wall_height": h, "base_width": base, "top_width": b, "ka": ka, "gamma_s": gs},
                assumptions=WALL_TEXT.format(faces=WALL_FACES[o]), criterion="FS_overturning >= 2.0",
                required=WALL_REQUIRED_FS, true_value=fs, ratio=ratio,
                verdict="SAFE" if cat == "SAFE" else "UNSAFE", flawed_value=None, flawed_ratio=None, flawed_step=None)


def _paired(rng: np.random.Generator, make_geo, build) -> list[Case]:
    """20 geometries; each is built in both orientations, with categories drawn independently per orientation."""
    plans = {o: list(PAIR_PLAN) for o in ("easy", "hard")}
    for o in plans:
        rng.shuffle(plans[o])
    out: list[Case] = []
    for idx in range(1, 21):
        for _ in range(10_000):
            geo = make_geo(rng)
            pair = [build(idx, o, plans[o][idx - 1], geo, rng) for o in ("easy", "hard")]
            if all(pair) and all(_distinguishable(c) for c in pair):
                out += pair
                break
        else:
            raise RuntimeError("could not build a geometry pair")
    return out


DISTINCT = 0.03  # every mistake must move the value by more than 3%, or a wrong answer would look correct


def _distinguishable(case: Case) -> bool:
    return all(abs(v / case.true_value - 1) > DISTINCT for v in mechanism_values(case).values())


def _from_study_one(family: str, plan: tuple[str, ...], rng: np.random.Generator) -> list[Case]:
    out = []
    for i, cat in enumerate(plan, start=1):
        for _ in range(1000):
            case = replace(c1._make(family, i, cat, rng), id=f"s2-{family}-{i:02d}",
                           flawed_value=None, flawed_ratio=None, flawed_step=None)
            if _distinguishable(case):
                break
        else:
            raise RuntimeError(f"no distinguishable {family} {cat} case")
        out.append(case)
    return out


def generate_phase1_cases(seed: int = SEED) -> list[Case]:
    rng = np.random.default_rng(seed)
    overturning = _from_study_one("overturning", ("SAFE",) * 32 + ("UNSAFE",) * 32 + ("BORDERLINE",) * 16, rng)
    sliding = _from_study_one("sliding", ("SAFE",) * 8 + ("UNSAFE",) * 8 + ("BORDERLINE",) * 4, rng)
    gates = _paired(
        rng,
        lambda r: {"depth": round(float(r.uniform(1.5, 5.0)), 2), "width": round(float(r.uniform(1.0, 4.0)), 2)},
        lambda idx, o, cat, g, r: _gate_case(idx, o, cat, g["depth"], g["width"], r))
    walls = _paired(
        rng,
        lambda r: {"wall_height": round(float(r.uniform(3.0, 8.0)), 1), "top_width": round(float(r.uniform(0.5, 1.5)), 2),
                   "ka": round(float(r.uniform(0.25, 0.40)), 2), "gamma_s": round(float(r.uniform(17.0, 20.0)), 1)},
        _wall_case)
    return overturning + gates + walls + sliding


def _overturning_fs(i: dict, tri: bool = False, up: bool = False, thrust: bool = False) -> float:
    h, d, bc, B, uf = i["height"], i["water_depth"], i["crest_width"], i["base_width"], i.get("uplift_factor", 0.0)
    wr, wt = GAMMA_C * bc * h, GAMMA_C * 0.5 * (B - bc) * h
    at = (B - bc) / 3 if tri else 2 * (B - bc) / 3
    hf, u = GAMMA_W * d * d / 2, uf * GAMMA_W * d * B / 2
    return (wr * (B - bc / 2) + wt * at) / (hf * (2 * d / 3 if thrust else d / 3) + u * (B / 3 if up else 2 * B / 3))


def mechanism_values(case: Case) -> dict[str, float]:
    """The value each known lever-arm mistake would produce. Keys name the mistake; 'hard'/'easy' per spec §2 H3."""
    i = case.inputs
    if case.family == "overturning" and "uplift_factor" not in i:  # exploratory E3: no uplift on the base
        return {"triangle_centroid (hard)": _overturning_fs(i, tri=True), "thrust_arm (easy)": _overturning_fs(i, thrust=True)}
    if case.family == "overturning":
        return {"uplift_arm (hard)": _overturning_fs(i, up=True), "triangle_centroid (hard)": _overturning_fs(i, tri=True),
                "uplift+triangle (hard)": _overturning_fs(i, tri=True, up=True),
                "thrust_arm (easy)": _overturning_fs(i, thrust=True)}
    if case.family == "gate":
        hinge = "bottom" if orientation(case) == "easy" else "top"
        wrong = "top" if hinge == "bottom" else "bottom"
        return {f"pressure_arm ({orientation(case)})": gate_latch_reaction(i["gate_height"], i["gate_width"], wrong)}
    if case.family == "wall":
        h, base, b, ka, gs = i["wall_height"], i["base_width"], i["top_width"], i["ka"], i["gamma_s"]
        tri = base - b
        w_rect, w_tri = GAMMA_C * b * h, GAMMA_C * 0.5 * tri * h
        thrust_m = ka * gs * h**2 / 2 * h / 3
        if orientation(case) == "hard":  # front batter: rectangle at the heel side
            m_rect, wrong_tri = w_rect * (tri + b / 2), w_tri * tri / 3
            right_tri = w_tri * 2 * tri / 3
        else:
            m_rect, wrong_tri = w_rect * b / 2, w_tri * (b + 2 * tri / 3)
            right_tri = w_tri * (b + tri / 3)
        return {f"triangle_centroid ({orientation(case)})": (m_rect + wrong_tri) / thrust_m,
                "thrust_arm (easy)": (m_rect + right_tri) / (2 * thrust_m)}
    return {}


def write_phase1_cases(cases: list[Case], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(asdict(c)) + "\n" for c in cases))


# --- Exploratory E3 (amendment 2026-11-10 night): the Phase 1 dams with no uplift --------------------------------
NOUPLIFT_TEXT = (c1.DAM_ASSUMPTIONS.split(" Uplift is triangular")[0] + " There is no uplift on the base (fully drained "
                 "foundation). Ignore cohesion, tailwater, silt and seismic loads. FS_overturning = resisting moments / "
                 "overturning moments, both about the toe; the water thrust is overturning.")


def generate_nouplift_cases(overturning: list[Case]) -> list[Case]:
    """Same geometry as each Phase 1 dam, uplift removed: what remains is the concrete triangle (hard) and the water
    thrust (easy), as in the front-batter retaining wall. Cases whose mistakes are not distinguishable are dropped."""
    from sfe.physics import overturning_fs
    out = []
    for case in overturning:
        i = {k: v for k, v in case.inputs.items() if k != "uplift_factor"}
        fs = overturning_fs(i["height"], i["water_depth"], i["crest_width"], i["base_width"], 0.0)
        ratio = fs / c1.REQUIRED_FS
        cat = "SAFE" if ratio >= 1 else ("BORDERLINE" if ratio >= 0.95 else "UNSAFE")
        new = replace(case, id=case.id.replace("s2-overturning-", "s2-nouplift-"), inputs=i, assumptions=NOUPLIFT_TEXT,
                      category=cat, true_value=fs, ratio=ratio, verdict="SAFE" if ratio >= 1 else "UNSAFE")
        if _distinguishable(new):
            out.append(new)
    return out
