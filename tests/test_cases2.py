"""Study II Phase 1 case set (spec 2026-11-10 §3)."""
from collections import Counter

import pytest

from sfe.cases import BANDS
from sfe.cases2 import generate_phase1_cases, mechanism_values, orientation, pair_id
from sfe.physics2 import gate_latch_reaction, wall_overturning_fs
from sfe.prompts import case_statement

CASES = generate_phase1_cases()


def test_counts_per_family():
    assert Counter(c.family for c in CASES) == {"overturning": 80, "gate": 40, "wall": 40, "sliding": 20}


def test_categories_follow_the_plan_per_orientation():
    for fam in ("gate", "wall"):
        for o in ("easy", "hard"):
            cats = Counter(c.category for c in CASES if c.family == fam and orientation(c) == o)
            assert cats == {"SAFE": 8, "UNSAFE": 8, "BORDERLINE": 4}
    assert Counter(c.category for c in CASES if c.family == "overturning") == {"SAFE": 32, "UNSAFE": 32, "BORDERLINE": 16}


def test_pairs_share_geometry():
    gates = [c for c in CASES if c.family == "gate"]
    by_pair = {}
    for c in gates:
        by_pair.setdefault(pair_id(c), []).append(c)
    assert len(by_pair) == 20 and all(len(v) == 2 for v in by_pair.values())
    for a, b in by_pair.values():
        assert (a.inputs["gate_height"], a.inputs["gate_width"]) == (b.inputs["gate_height"], b.inputs["gate_width"])
        assert {orientation(a), orientation(b)} == {"easy", "hard"}
    walls = [c for c in CASES if c.family == "wall"]
    pairs = {}
    for c in walls:
        pairs.setdefault(pair_id(c), []).append(c)
    for a, b in pairs.values():
        for k in ("wall_height", "top_width", "ka", "gamma_s"):
            assert a.inputs[k] == b.inputs[k]


def test_truth_recomputes_and_ratio_in_band():
    for c in CASES:
        lo, hi = BANDS[c.category]
        assert lo <= c.ratio < hi, c.id
        if c.family == "gate":
            hinge = "bottom" if orientation(c) == "easy" else "top"
            r = gate_latch_reaction(c.inputs["gate_height"], c.inputs["gate_width"], hinge)
            assert c.true_value == pytest.approx(r) and c.ratio == pytest.approx(c.required / r)
        if c.family == "wall":
            batter = "back" if orientation(c) == "easy" else "front"
            i = c.inputs
            fs = wall_overturning_fs(i["wall_height"], i["base_width"], i["top_width"], i["ka"], i["gamma_s"], batter)
            assert c.true_value == pytest.approx(fs) and c.ratio == pytest.approx(fs / 2.0)


def test_mechanism_variants_are_distinguishable():
    for c in CASES:
        if c.family == "sliding":
            assert mechanism_values(c) == {}
            continue
        for label, v in mechanism_values(c).items():
            assert abs(v / c.true_value - 1) > 0.02, (c.id, label)


def test_prompts_render_and_state_orientation():
    for c in CASES:
        text = case_statement(c)
        assert c.criterion in text
    gate_hard = next(c for c in CASES if c.family == "gate" and orientation(c) == "hard")
    assert "hinged at its top edge" in gate_hard.assumptions
    wall_hard = next(c for c in CASES if c.family == "wall" and orientation(c) == "hard")
    assert "front face" in wall_hard.assumptions


def test_ids_do_not_collide_with_study_one():
    ids = [c.id for c in CASES]
    assert len(set(ids)) == len(ids) and all(i.startswith("s2-") for i in ids)


def test_judge_prompt_and_value_reader_cover_new_families():
    from sfe.grade import FS_FAMILIES, judge_prompt
    gate = next(c for c in CASES if c.family == "gate")
    wall = next(c for c in CASES if c.family == "wall")
    assert "latch reaction in kN" in judge_prompt(gate, "x")
    assert "overturning" in judge_prompt(wall, "x") and "wall" in FS_FAMILIES


def test_phase1_cases_file_round_trips(tmp_path):
    from sfe.cases import load_cases
    from sfe.cases2 import write_phase1_cases
    path = tmp_path / "c.jsonl"
    write_phase1_cases(CASES, path)
    assert [c.id for c in load_cases(path)] == [c.id for c in CASES]


def test_nouplift_cases_match_independent_physics_and_drop_uplift_mechanisms():
    from sfe import physics as p
    from sfe.cases2 import generate_nouplift_cases, generate_phase1_cases, mechanism_values
    base = [c for c in generate_phase1_cases() if c.family == "overturning"]
    cases = generate_nouplift_cases(base)
    assert 60 <= len(cases) <= 80
    for c in cases:
        i = c.inputs
        assert "uplift_factor" not in i and "no uplift" in c.assumptions.lower()
        assert c.id.startswith("s2-nouplift-") and c.family == "overturning"
        truth = p.overturning_fs(i["height"], i["water_depth"], i["crest_width"], i["base_width"], 0.0)
        assert abs(c.true_value - truth) < 1e-9
        assert c.verdict == ("SAFE" if truth >= 1.5 else "UNSAFE")
        mech = mechanism_values(c)
        assert set(mech) == {"triangle_centroid (hard)", "thrust_arm (easy)"}
        assert all(abs(v / truth - 1) > 0.03 for v in mech.values())
