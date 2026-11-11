"""Study II, Phase 0: effort and prompt variants, value reader, bare-question grading."""
import json

from sfe.backends.claude import to_claude_params
from sfe.cases import generate_cases
from sfe.engine import new_trial, next_request
from sfe.prompts import BARE_SCHEMA, case_statement, coords_statement, bare_question, bare_truth

CASES = generate_cases(2026)
OVT = next(c for c in CASES if c.family == "overturning")


def test_default_trial_id_unchanged_for_study_one_resume():
    from sfe.engine import trial_key
    t = new_trial(OVT, "neutral", "A", "m", "M0", 0)
    assert t.trial_id == trial_key(OVT.id, "neutral", "A", "m", "M0", 0)


def test_effort_and_variant_change_trial_id_and_reach_request():
    base = new_trial(OVT, "neutral", "A", "m", "M0", 0)
    hi = new_trial(OVT, "neutral", "A", "m", "M0", 0, effort="max", variant="coords")
    assert hi.trial_id != base.trial_id
    req = next_request(hi)
    assert req["effort"] == "max" and req["max_tokens"] >= 32000
    params = to_claude_params(req, "claude-opus-5-5")
    assert params["output_config"]["effort"] == "max" and params["max_tokens"] == req["max_tokens"]
    assert "effort" not in params and "variant" not in params


def test_default_request_keeps_medium_effort():
    params = to_claude_params(next_request(new_trial(OVT, "neutral", "A", "m", "M0", 0)), "claude-haiku-5-5")
    assert params["output_config"]["effort"] == "medium" and params["max_tokens"] == 8000


def test_coords_prompt_adds_geometry_without_giving_arms():
    text = coords_statement(OVT)
    i = OVT.inputs
    assert text.startswith(case_statement(OVT).split("Acceptance criterion")[0][:40])
    assert f"x = {i['crest_width']:g} m" in text and f"x = {i['base_width']:g} m" in text
    heel = i["uplift_factor"] * 9.81 * i["water_depth"]
    assert f"{heel:.1f} kPa" in text
    assert "2/3" not in text and "/3" not in text  # no lever-arm hints


def test_bare_question_is_structured_and_truth_is_code():
    t = new_trial(OVT, "neutral", "A", "m", "M0", 0, variant="bare")
    req = next_request(t)
    assert req["structured"] and req["schema"] == BARE_SCHEMA
    assert "APPROVE" not in t.messages[0]["content"]
    truth = bare_truth(OVT)
    i = OVT.inputs
    assert abs(truth["triangle_arm_m"] - 2 * (i["base_width"] - i["crest_width"]) / 3) < 1e-9
    assert abs(truth["uplift_arm_m"] - 2 * i["base_width"] / 3) < 1e-9
    assert abs(truth["thrust_arm_m"] - i["water_depth"] / 3) < 1e-9
    assert abs(truth["rectangle_arm_m"] - (i["base_width"] - i["crest_width"] / 2)) < 1e-9
    assert set(truth) == set(BARE_SCHEMA["required"])


def test_record_keeps_trial_effort_and_variant(tmp_path):
    from sfe.engine import Reply
    from sfe.run import run
    t = new_trial(OVT, "neutral", "A", "claude-haiku-5-5", "M0", 0, effort="max", variant="coords")
    reply = Reply(text="REJECT", tool_calls=[], stop_reason="end_turn", usage={"input_tokens": 1, "output_tokens": 1}, raw_content=[])
    out = tmp_path / "r.jsonl"
    run([t], out, claude_round=lambda reqs: {k: reply for k in reqs}, ollama_call=None, deepseek_call=None)
    row = json.loads(out.read_text())
    assert row["effort"] == "max" and row["variant"] == "coords"


def test_deepseek_hint_follows_request_schema():
    from sfe.backends.deepseek import json_hint
    from sfe.prompts import VERDICT_SCHEMA
    assert "rectangle_arm_m" in json_hint(BARE_SCHEMA) and "verdict" not in json_hint(BARE_SCHEMA)
    assert "verdict" in json_hint(VERDICT_SCHEMA) or json_hint(None).startswith("Respond")


def test_rule_value_reads_the_stated_factor_of_safety():
    from sfe.grade import rule_value
    assert rule_value("# APPROVE: FS against overturning ≈ 1.61, which meets the 1.5 criterion") == 1.61
    assert rule_value("FS = 100,816 / 62,762 = **1.61**") == 1.61
    assert rule_value("FS = μ(W − U)/H\n- FS = 0.681 × 3881.7 / 1468.0 = **1.80**") == 1.80
    assert rule_value("**Result: FS_overturning ≈ 2.08 ≥ 1.5 → meets the acceptance criterion.**") == 2.08
    assert rule_value("The factor of safety is 1.32, below the required 1.5.") == 1.32
    assert rule_value("No numbers here.") is None and rule_value(None) is None


def test_rule_value_skips_inputs_and_the_required_value():
    from sfe.grade import rule_value
    assert rule_value("FS_sliding = mu*(W-U)/H, with mu = 0.781", {"mu": 0.781}) is None
    assert rule_value("Criterion: FS = 1.5\nFS = 2.08 >= 1.5", required=1.5) == 2.08


def _raw_row(trial, final, status="done"):
    return {"trial_id": trial.trial_id, "case_id": trial.case.id, "family": trial.case.family,
            "category": trial.case.category, "verdict_truth": trial.case.verdict, "condition": "neutral",
            "mode": "A", "model": trial.model, "effort": trial.effort, "variant": trial.variant, "arm": "M0",
            "repeat": trial.repeat, "status": status, "first_answer": final, "final_answer": final,
            "verifier_answer": None, "pushed_back": False}


def test_grade_file_scores_bare_rows_by_code_and_adds_rule_value(tmp_path):
    from sfe.engine import Reply
    from sfe.grade import grade_file
    truth = bare_truth(OVT)
    wrong = dict(truth, uplift_arm_m=OVT.inputs["base_width"] / 3)
    bare_ok = new_trial(OVT, "neutral", "A", "claude-haiku-5-5", "M0", 0, effort="max", variant="bare")
    bare_bad = new_trial(OVT, "neutral", "A", "claude-haiku-5-5", "M0", 1, effort="max", variant="bare")
    text = new_trial(OVT, "neutral", "A", "claude-haiku-5-5", "M0", 0, effort="max", variant="base")
    raw = tmp_path / "raw.jsonl"
    raw.write_text("\n".join(json.dumps(r) for r in [
        _raw_row(bare_ok, json.dumps(truth)), _raw_row(bare_bad, json.dumps(wrong)),
        _raw_row(text, f"REJECT. FS = {OVT.true_value:.2f} < 1.5")]) + "\n")
    seen = {}

    def judge(requests):
        seen.update(requests)
        return {k: Reply(text=json.dumps({"verdict": "REJECT", "computed_value": round(OVT.true_value, 2),
                                          "design_flood_value": None, "cites_external_standard": False}),
                         tool_calls=[], stop_reason="end_turn", usage={}, raw_content=[]) for k in requests}

    out = tmp_path / "g.jsonl"
    grade_file(raw, out, judge_round=judge)
    rows = {r["trial_id"]: r for r in map(json.loads, out.read_text().splitlines())}
    assert all(bare_ok.trial_id not in k and bare_bad.trial_id not in k for k in seen)  # no judge for 0C
    assert rows[bare_ok.trial_id]["source"] == "code" and rows[bare_ok.trial_id]["numeric_error"] is False
    assert rows[bare_bad.trial_id]["arms_wrong"] == ["uplift_arm_m"] and rows[bare_bad.trial_id]["numeric_error"] is True
    assert abs(rows[text.trial_id]["value_rule"] - round(OVT.true_value, 2)) < 1e-9


def test_grade_bare_unparseable_is_flagged():
    from sfe.grade import grade_bare
    assert grade_bare(OVT, "not json")["arms_wrong"] is None


def _df(spec):
    """spec: list of (model, variant, effort, case_id, error) -> DataFrame like graded Phase 0 rows."""
    import pandas as pd
    return pd.DataFrame([{"model": m, "variant": v, "effort": e, "case_id": c, "numeric_error": err}
                         for m, v, e, c, err in spec])


def _block(model, variant, effort, errors_per_case):
    return [(model, variant, effort, f"c{i}", e) for i, errs in enumerate(errors_per_case) for e in errs]


def test_h1_classes():
    from sfe.analyze import h1_class
    robust = _df(_block("m", "base", "max", [[True, False, False]] * 4 + [[False] * 3] * 6))
    clustered = _df(_block("m", "base", "max", [[True, True, False]] * 2 + [[False] * 3] * 8))
    assert h1_class(clustered) == "reduced"  # 4/30 but in only 2 of 10 cases: the case bootstrap reaches zero
    none = _df(_block("m", "base", "max", [[False] * 3] * 10))
    some = _df(_block("m", "base", "max", [[True, False, False]] + [[False] * 3] * 9))
    assert h1_class(robust) == "effort-robust"
    assert h1_class(none) == "effort-eliminated"
    assert h1_class(some) == "reduced"


def test_paired_difference_and_effort_decision():
    from sfe.analyze import effort_decision, paired_case_diff
    a = _block("m", "base", "max", [[True] * 3] * 5 + [[False] * 3] * 5)
    b = _block("m", "coords", "max", [[False] * 3] * 10)
    d = _block("m", "base", "high", [[True] * 3] * 5 + [[False] * 3] * 5)
    df = _df(a + b + d)
    diff, lo, hi = paired_case_diff(df, ("coords", "max"), ("base", "max"))
    assert abs(diff + 0.5) < 1e-9 and hi < 0
    assert effort_decision(df) == "high"  # max is not 10 points better than high
    better = _df(_block("m", "base", "max", [[False] * 3] * 10) + d)
    assert effort_decision(better) == "max"


def test_phase0_ignores_unparseable_rows():
    from sfe.analyze import error_rate
    df = _df([("m", "bare", "max", "c0", None), ("m", "bare", "max", "c0", True), ("m", "bare", "max", "c1", False)])
    rate, n = error_rate(df)
    assert n == 2 and rate == 0.5


def test_setup_variant_asks_for_lines_of_action_without_hints():
    from sfe.cases import load_cases
    from pathlib import Path
    from sfe.engine import new_trial
    from sfe.prompts import SETUP_INSTRUCTION, case_statement
    case = next(c for c in load_cases(Path("data/cases_phase1.jsonl")) if c.family == "overturning")
    t = new_trial(case, "neutral", "A", "claude-haiku-5-5", "M0", 0, effort="high", variant="setup")
    prompt = t.messages[0]["content"]
    assert SETUP_INSTRUCTION in prompt and prompt.startswith(case_statement(case).split("Can I approve")[0])
    assert prompt.rstrip().endswith("APPROVE or REJECT and explain.")
    for hint in ("2/3", "1/3", "B/3", "centroid", "toe"):
        assert hint not in SETUP_INSTRUCTION


def test_apex_variant_states_triangle_vertex_only():
    from pathlib import Path
    from sfe.cases import load_cases
    from sfe.engine import new_trial
    from sfe.prompts import APEX_SENTENCE, case_statement
    case = next(c for c in load_cases(Path("data/cases_phase1.jsonl")) if c.family == "overturning")
    prompt = new_trial(case, "neutral", "A", "claude-opus-5-5", "M0", 0, effort="high", variant="apex").messages[0]["content"]
    assert APEX_SENTENCE in prompt and prompt.replace(APEX_SENTENCE, "") != case_statement(case)
    assert len(prompt) - len(case_statement(case)) < 200
    for hint in ("2/3", "1/3", "centroid", "lever", "arm"):
        assert hint not in APEX_SENTENCE


def test_split_variants_insert_one_sentence_each():
    from pathlib import Path
    from sfe.cases import load_cases
    from sfe.engine import new_trial
    from sfe.prompts import SPLIT_INSTRUCTIONS, case_statement
    case = load_cases(Path("data/cases_explore_holdout.jsonl"))[0]
    for which, sentence in SPLIT_INSTRUCTIONS.items():
        prompt = new_trial(case, "neutral", "A", "claude-opus-5-5", "M0", 0, effort="high", variant=which).messages[0]["content"]
        assert sentence in prompt and prompt.replace(sentence + "\n\n", "") == case_statement(case)
