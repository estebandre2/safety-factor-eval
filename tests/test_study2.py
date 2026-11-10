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
