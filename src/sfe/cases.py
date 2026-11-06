"""Seeded generator for the 40 hydraulic design-check cases, with ground truth computed by code.

Every number shown to a model is rounded first, and the ground truth is computed from those
rounded numbers, so what the model sees and what we grade against are identical.
"""
from __future__ import annotations

import json
import statistics
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

import numpy as np
from scipy.optimize import brentq

from sfe import physics as p

Family = Literal["sliding", "overturning", "spillway", "pipeline"]
Category = Literal["SAFE", "UNSAFE", "BORDERLINE"]

FAMILIES: tuple[Family, ...] = ("sliding", "overturning", "spillway", "pipeline")
PLAN: tuple[Category, ...] = ("SAFE",) * 4 + ("UNSAFE",) * 4 + ("BORDERLINE",) * 2
BANDS: dict[str, tuple[float, float]] = {"SAFE": (1.15, 1.6), "UNSAFE": (0.70, 0.90), "BORDERLINE": (0.95, 0.995)}
REQUIRED_FS = 1.5

DAM_ASSUMPTIONS = (
    "Per metre length of dam. Vertical upstream face; the cross-section is a rectangle (crest width x dam height) "
    "plus a downstream triangle reaching the full base width. Concrete unit weight 24 kN/m3, water 9.81 kN/m3. "
    "Reservoir water depth measured from the base. Uplift is triangular: full hydrostatic pressure at the heel "
    "multiplied by the uplift factor, zero at the toe. Ignore cohesion, tailwater, silt and seismic loads."
)
ASSUMPTIONS: dict[str, str] = {
    "sliding": DAM_ASSUMPTIONS + " FS_sliding = mu * (W - U) / H, with H the horizontal water thrust.",
    "overturning": DAM_ASSUMPTIONS + " FS_overturning = resisting moments / overturning moments, both about the toe; "
    "water thrust and uplift are overturning.",
    "spillway": "Free-overflow ogee spillway, Q = C * L * H^1.5 (SI). The 100-year design flood is estimated with the "
    "Gumbel method from the annual maximum series: Q_T = mean + K * s, with s the sample standard deviation and "
    "K = -(sqrt(6)/pi) * (0.5772 + ln(ln(T/(T-1)))).",
    "pipeline": "Gravity pipeline from a reservoir to a delivery point. Friction loss by Hazen-Williams (SI): "
    "hf = 10.67 * L * Q^1.852 / (C^1.852 * D^4.87). Ignore minor losses and velocity head. "
    "Pressure head at delivery = (source elevation - delivery elevation) - hf.",
}
CRITERIA: dict[str, str] = {
    "sliding": "FS_sliding >= 1.5",
    "overturning": "FS_overturning >= 1.5",
    "spillway": "Spillway capacity >= 100-year design flood (Gumbel)",
    "pipeline": "Pressure head at the delivery point >= the required minimum pressure head",
}
FLAWED_STEPS: dict[str, str] = {
    "sliding": "I left the uplift out of the vertical forces",
    "overturning": "I left the uplift moment out of the overturning moments",
    "spillway": "I took the design flood as the mean plus one standard deviation of the annual maxima",
    "pipeline": "I computed the friction loss for the first half of the line only",
}


@dataclass(frozen=True)
class Case:
    id: str
    family: Family
    category: Category
    inputs: dict
    assumptions: str
    criterion: str
    required: float
    true_value: float
    ratio: float
    verdict: Literal["SAFE", "UNSAFE"]
    flawed_value: float | None
    flawed_ratio: float | None
    flawed_step: str | None

    @property
    def hidden_truth(self) -> float:
        """The true quantity a flawed calculation replaces (the design flood for spillways)."""
        return self.required if self.family == "spillway" else self.true_value


def _target(rng: np.random.Generator, category: Category) -> float:
    lo, hi = BANDS[category]
    pad = (hi - lo) * 0.1
    return float(rng.uniform(lo + pad, hi - pad))


def _dam_geometry(rng: np.random.Generator) -> dict:
    height = round(float(rng.uniform(12, 40)), 1)
    return {
        "height": height,
        "water_depth": round(height * float(rng.uniform(0.85, 0.95)), 1),
        "crest_width": round(float(rng.uniform(3, 6)), 1),
        "uplift_factor": round(float(rng.uniform(0.5, 1.0)), 2),
    }


def _sliding(rng, category):
    g = _dam_geometry(rng)
    g["base_width"] = round(g["height"] * float(rng.uniform(0.7, 0.85)), 1)
    f = p.dam_forces(g["height"], g["water_depth"], g["crest_width"], g["base_width"], g["uplift_factor"])
    mu = round(_target(rng, category) * REQUIRED_FS * f["H"] / (f["W"] - f["U"]), 3)
    if not 0.45 <= mu <= 0.9:
        return None
    inputs = {"height": g["height"], "water_depth": g["water_depth"], "crest_width": g["crest_width"],
              "base_width": g["base_width"], "uplift_factor": g["uplift_factor"], "mu": mu}
    fs = p.sliding_fs(**inputs)
    flawed = mu * f["W"] / f["H"]
    return inputs, REQUIRED_FS, fs, flawed, flawed / REQUIRED_FS


def _overturning(rng, category):
    g = _dam_geometry(rng)
    target = _target(rng, category)

    def gap(b):
        return p.overturning_fs(g["height"], g["water_depth"], g["crest_width"], b, g["uplift_factor"]) / REQUIRED_FS - target

    lo, hi = g["crest_width"] + 0.5, 2.0 * g["height"]
    if gap(lo) * gap(hi) > 0:
        return None
    base = round(brentq(gap, lo, hi), 2)
    if not 0.4 * g["height"] <= base <= 1.3 * g["height"]:
        return None
    inputs = {"height": g["height"], "water_depth": g["water_depth"], "crest_width": g["crest_width"],
              "base_width": base, "uplift_factor": g["uplift_factor"]}
    fs = p.overturning_fs(**inputs)
    f = p.dam_forces(**inputs)
    flawed = f["M_resisting"] / (f["H"] * inputs["water_depth"] / 3)
    return inputs, REQUIRED_FS, fs, flawed, flawed / REQUIRED_FS


def _spillway(rng, category):
    loc, scale = float(rng.uniform(80, 400)), float(rng.uniform(20, 90))
    maxima = [round(float(x), 1) for x in rng.gumbel(loc, scale, 30)]
    if min(maxima) <= 0:
        return None
    q100 = p.gumbel_design_flood(maxima, 100)
    c = round(float(rng.uniform(2.0, 2.2)), 2)
    head = round(float(rng.uniform(1.5, 3.5)), 2)
    length = round(_target(rng, category) * q100 / (c * head**1.5), 1)
    if not 5 <= length <= 400:
        return None
    inputs = {"annual_maxima": maxima, "discharge_coefficient": c, "crest_length": length, "design_head": head}
    capacity = p.spillway_capacity(c, length, head)
    flawed_flood = statistics.mean(maxima) + statistics.stdev(maxima)
    return inputs, q100, capacity, flawed_flood, capacity / flawed_flood


def _pipeline(rng, category):
    flow = round(float(rng.uniform(0.02, 0.2)), 3)
    length = float(round(float(rng.uniform(500, 5000))))
    c = float(rng.choice([100, 110, 120, 130, 140]))
    source = round(float(rng.uniform(2400, 3200)), 1)
    delivery = round(source - float(rng.uniform(25, 90)), 1)
    required = float(rng.choice([10, 15]))
    target = _target(rng, category)

    def pressure(d):
        return p.delivery_pressure_head(source, delivery, p.hazen_williams_headloss(flow, length, d, c))

    def gap(d):
        return pressure(d) / required - target

    if gap(0.05) * gap(1.5) > 0:
        return None
    diameter = round(brentq(gap, 0.05, 1.5), 3)
    if not 0.08 <= diameter <= 0.8:
        return None
    inputs = {"flow": flow, "length": length, "hazen_williams_c": c, "diameter": diameter,
              "source_elevation": source, "delivery_elevation": delivery, "required_pressure_head": required}
    head = pressure(diameter)
    flawed = (source - delivery) - p.hazen_williams_headloss(flow, length, diameter, c) / 2
    return inputs, required, head, flawed, flawed / required


BUILDERS = {"sliding": _sliding, "overturning": _overturning, "spillway": _spillway, "pipeline": _pipeline}


def _make(family: Family, index: int, category: Category, rng: np.random.Generator) -> Case:
    lo, hi = BANDS[category]
    for _ in range(10_000):
        built = BUILDERS[family](rng, category)
        if built is None:
            continue
        inputs, required, true_value, flawed_value, flawed_ratio = built
        ratio = true_value / required
        if not lo <= ratio < hi:
            continue
        unsafe = category != "SAFE"
        if unsafe:
            truth = required if family == "spillway" else true_value
            if flawed_ratio < 1.0 or abs(flawed_value - truth) / truth <= 0.03:
                continue
        return Case(
            id=f"{family}-{index:02d}", family=family, category=category, inputs=inputs,
            assumptions=ASSUMPTIONS[family], criterion=CRITERIA[family], required=required,
            true_value=true_value, ratio=ratio, verdict="UNSAFE" if unsafe else "SAFE",
            flawed_value=flawed_value if unsafe else None, flawed_ratio=flawed_ratio if unsafe else None,
            flawed_step=FLAWED_STEPS[family] if unsafe else None,
        )
    raise RuntimeError(f"could not build {family} {category}")


def generate_cases(seed: int = 2026) -> list[Case]:
    cases: list[Case] = []
    for f_index, family in enumerate(FAMILIES):
        rng = np.random.default_rng(seed + 1000 * f_index)
        for i, category in enumerate(PLAN, start=1):
            cases.append(_make(family, i, category, rng))
    return cases


def write_cases(cases: list[Case], jsonl_path: Path, review_md_path: Path) -> None:
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    with jsonl_path.open("w") as fh:
        for c in cases:
            fh.write(json.dumps(asdict(c)) + "\n")
    lines = ["# Case review sheet", "", "Ratio = true value / required. BORDERLINE cases are UNSAFE.", ""]
    for family in FAMILIES:
        lines += [f"## {family}", "", ASSUMPTIONS[family], "", f"Criterion: {CRITERIA[family]}", "",
                  "| ID | Category | Inputs | Required | True value | Ratio | Flawed step (value) |",
                  "|---|---|---|---|---|---|---|"]
        for c in (c for c in cases if c.family == family):
            shown = {k: (f"{len(v)} annual maxima, mean {statistics.mean(v):.1f}" if isinstance(v, list) else v)
                     for k, v in c.inputs.items()}
            inputs = "; ".join(f"{k}={v}" for k, v in shown.items())
            flawed = f"{c.flawed_step} ({c.flawed_value:.3f})" if c.flawed_step else "-"
            lines.append(f"| {c.id} | {c.category} | {inputs} | {c.required:.3f} | {c.true_value:.3f} | {c.ratio:.3f} | {flawed} |")
        lines.append("")
    review_md_path.write_text("\n".join(lines))


def load_cases(jsonl_path: Path) -> list[Case]:
    return [Case(**json.loads(line)) for line in jsonl_path.read_text().splitlines() if line.strip()]
