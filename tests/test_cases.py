from collections import Counter

import pytest

from sfe import physics as p
from sfe.cases import BANDS, generate_cases, load_cases, write_cases

CASES = generate_cases(2026)


def recompute(case):
    i = case.inputs
    if case.family == "sliding":
        return p.sliding_fs(i["height"], i["water_depth"], i["crest_width"], i["base_width"], i["uplift_factor"], i["mu"])
    if case.family == "overturning":
        return p.overturning_fs(i["height"], i["water_depth"], i["crest_width"], i["base_width"], i["uplift_factor"])
    if case.family == "spillway":
        return p.spillway_capacity(i["discharge_coefficient"], i["crest_length"], i["design_head"])
    hf = p.hazen_williams_headloss(i["flow"], i["length"], i["diameter"], i["hazen_williams_c"])
    return p.delivery_pressure_head(i["source_elevation"], i["delivery_elevation"], hf)


def test_counts():
    assert len(CASES) == 40
    assert len({c.id for c in CASES}) == 40
    per = Counter((c.family, c.category) for c in CASES)
    for fam in ("sliding", "overturning", "spillway", "pipeline"):
        assert per[(fam, "SAFE")] == 4
        assert per[(fam, "UNSAFE")] == 4
        assert per[(fam, "BORDERLINE")] == 2


def test_ratio_bands():
    for c in CASES:
        lo, hi = BANDS[c.category]
        assert lo <= c.ratio < hi, (c.id, c.ratio)
        assert c.verdict == ("SAFE" if c.category == "SAFE" else "UNSAFE")


def test_ground_truth_recomputes():
    for c in CASES:
        assert recompute(c) == pytest.approx(c.true_value, rel=1e-9), c.id
        if c.family == "spillway":
            q100 = p.gumbel_design_flood(c.inputs["annual_maxima"], 100)
            assert c.required == pytest.approx(q100, rel=1e-9)
        assert c.ratio == pytest.approx(c.true_value / c.required, rel=1e-9)


def test_flawed_value_passes_and_differs():
    for c in CASES:
        if c.category == "SAFE":
            assert c.flawed_value is None and c.flawed_ratio is None
            continue
        assert c.flawed_ratio >= 1.0, c.id
        truth = c.hidden_truth
        assert abs(c.flawed_value - truth) / truth > 0.03, c.id
        assert c.flawed_step


def test_deterministic():
    assert generate_cases(2026) == CASES


def test_roundtrip(tmp_path):
    write_cases(CASES, tmp_path / "c.jsonl", tmp_path / "r.md")
    assert load_cases(tmp_path / "c.jsonl") == CASES
    assert "sliding-01" in (tmp_path / "r.md").read_text()
