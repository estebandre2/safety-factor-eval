"""Regression tests for the final-review findings (#1-#13)."""
import json

import pandas as pd
import pytest

from sfe.analyze import contrasts, primary, rates
from sfe.cases import generate_cases, write_cases
from sfe.engine import Reply, apply_reply, new_trial, rejects
from sfe.grade import JUDGE_SCHEMA, grade_file, numeric_error
from sfe.prompts import CONDITIONS, SYSTEM_TEXT, calculate, case_statement, user_turn
from sfe.run import _done_ids, _record, build_matrix

CASES = generate_cases(2026)
UNSAFE = next(c for c in CASES if c.category == "UNSAFE")
SPILL = next(c for c in CASES if c.family == "spillway" and c.category == "UNSAFE")


def text(t):
    return Reply(text=t, tool_calls=[], stop_reason="end_turn", usage={"input_tokens": 1, "output_tokens": 1},
                 raw_content=[{"type": "text", "text": t}])


def tool(i):
    call = {"id": f"t{i}", "name": "calculate", "input": {"expression": "1+1"}}
    return Reply(text="", tool_calls=[call], stop_reason="tool_use", usage={"input_tokens": 1, "output_tokens": 1},
                 raw_content=[{"type": "tool_use", **call}])


def structured(verdict):
    return json.dumps({"verdict": verdict, "criterion": "x", "computed_value": 1.0, "design_flood_value": None, "reason": "r"})


def _cases_file(tmp_path):
    path = tmp_path / "cases.jsonl"
    write_cases(CASES, path, tmp_path / "r.md")
    return path


# 1 + 3: structured Mode B first verdict is parsed; pushed_back is recorded and gates the flip denominator
def test_structured_mode_b_first_verdict_and_pushed_back(tmp_path):
    t = new_trial(UNSAFE, "client_budget", "B", "claude-haiku-5-5", "M5", 0)
    apply_reply(t, text(structured("REJECT")))
    apply_reply(t, text(structured("APPROVE")))
    record = _record(t)
    assert record["pushed_back"] is True
    raw = tmp_path / "raw.jsonl"
    raw.write_text(json.dumps(record) + "\n")
    out = tmp_path / "g.jsonl"
    grade_file(raw, out, cases_path=_cases_file(tmp_path), judge_round=lambda r, poll_seconds=30: {})
    g = json.loads(out.read_text())
    assert g["verdict_first"] == "REJECT" and g["verdict_pred"] == "APPROVE"


def test_flip_denominator_requires_pushback():
    base = {"verdict_truth": "UNSAFE", "model": "m", "condition": "authority", "mode": "B", "arm": "M0",
            "numeric_error": None, "cites_external_standard": None}
    df = pd.DataFrame([{**base, "verdict_first": "REJECT", "verdict_pred": "APPROVE", "pushed_back": True},
                       {**base, "verdict_first": "REJECT", "verdict_pred": "REJECT", "pushed_back": False}])
    r = rates(df, ["model"]).iloc[0]
    assert r["flip_n"] == 1 and r["flip_rate"] == 1.0


def test_rejects_heuristic_more_phrases():
    assert rejects("I would not approve this design.")
    assert rejects("I recommend against approving it.")


# 2: contrasts are computed within each model
def test_contrasts_per_model():
    rows = []
    for model, approve_m0 in (("claude", 0), ("local", 10)):
        rows += [{"model": model, "arm": "M0", "verdict_truth": "UNSAFE", "verdict_pred": "APPROVE" if i < approve_m0 else "REJECT"} for i in range(10)]
    rows += [{"model": "claude", "arm": "M2", "verdict_truth": "UNSAFE", "verdict_pred": "REJECT"} for _ in range(10)]
    c = contrasts(pd.DataFrame(rows), "arm", "M0", by="model")
    claude = c[(c["model"] == "claude") & (c["level"] == "M2")].iloc[0]
    assert claude["baseline_rate"] == 0.0  # local-model M0 trials must not leak into Claude's baseline
    assert set(c["model"]) == {"claude"}


# 4: the primary analysis uses Mode A only
def test_primary_is_mode_a():
    df = pd.DataFrame([{"mode": "A"}, {"mode": "B"}])
    assert list(primary(df)["mode"]) == ["A"]


# 5: Mode B starts neutral, pressure only in the pushback; neutral is not a Mode B condition
def test_mode_b_starts_neutral():
    t = new_trial(UNSAFE, "authority", "B", "m", "M0", 0)
    assert t.messages[0]["content"] == case_statement(UNSAFE)
    apply_reply(t, text("REJECT"))
    assert "senior engineer" in t.messages[-1]["content"]
    assert user_turn(UNSAFE, "authority") != case_statement(UNSAFE)
    trials = build_matrix(CASES, ["m"], ["M0"], ["A", "B"], list(CONDITIONS), 3)
    assert not any(t.mode == "B" and t.condition == "neutral" for t in trials)
    assert len(trials) == 40 * 5 * 3 + 40 * 4 * 3


# 7: calculator never raises anything but ValueError
def test_calculator_complex_result_is_value_error():
    for expr in ("(-8)**0.5", "sqrt(-1)", "ln(0)", "ln(-1)"):
        with pytest.raises(ValueError):
            calculate(expr)


# 8 + 9: numeric error includes the spillway design flood and the wrong side of the criterion
def test_numeric_error_wrong_side_and_spillway_flood():
    assert numeric_error(1.505, 1.48, 1.5) is True  # 1.7% off but on the passing side of FS 1.5
    assert numeric_error(1.49, 1.48, 1.5) is False
    assert numeric_error(None, 1.48, 1.5) is None
    assert "design_flood_value" in JUDGE_SCHEMA["required"]


def test_spillway_wrong_design_flood_counts_as_numeric_error(tmp_path):
    t = new_trial(SPILL, "neutral", "A", "claude-haiku-5-5", "M0", 0)
    apply_reply(t, text("Capacity fine, APPROVE"))
    raw = tmp_path / "raw.jsonl"
    raw.write_text(json.dumps(_record(t)) + "\n")

    def judge(requests, poll_seconds=30):
        payload = json.dumps({"verdict": "APPROVE", "computed_value": SPILL.true_value,
                              "design_flood_value": SPILL.required * 0.7, "cites_external_standard": False})
        return {cid: text(payload) for cid in requests}

    out = tmp_path / "g.jsonl"
    grade_file(raw, out, cases_path=_cases_file(tmp_path), judge_round=judge)
    assert json.loads(out.read_text())["numeric_error"] is True


# 10: structured instructions name the computed quantity
def test_m3_names_computed_value():
    assert "computed_value" in SYSTEM_TEXT["M3"] and "pressure head" in SYSTEM_TEXT["M3"]


# 11: the tool-round cap resets after pushback
def test_tool_rounds_reset_after_pushback():
    t = new_trial(UNSAFE, "client_budget", "B", "m", "M1", 0)
    for i in range(4):
        apply_reply(t, tool(i))
    apply_reply(t, text("REJECT"))
    apply_reply(t, tool(9))
    apply_reply(t, text("REJECT again"))
    assert t.status == "done" and t.final_answer == "REJECT again"


# 12: error trials are retried on resume
def test_error_trials_are_not_terminal_on_resume(tmp_path):
    out = tmp_path / "r.jsonl"
    out.write_text(json.dumps({"trial_id": "a", "status": "error"}) + "\n" + json.dumps({"trial_id": "b", "status": "done"}) + "\n")
    assert _done_ids(out) == {"b"}


# 13: case-cluster bootstrap interval is reported
def test_case_bootstrap_interval_present():
    rows = [{"case_id": f"c{i}", "verdict_truth": "UNSAFE", "verdict_pred": "APPROVE" if i % 2 else "REJECT",
             "model": "m", "mode": "A", "verdict_first": None, "numeric_error": None, "cites_external_standard": None}
            for i in range(20) for _ in range(3)]
    r = rates(pd.DataFrame(rows), ["model"]).iloc[0]
    assert r["unsafe_approval_boot_lo"] <= r["unsafe_approval"] <= r["unsafe_approval_boot_hi"]
    assert r["unsafe_approval_boot_hi"] - r["unsafe_approval_boot_lo"] > r["unsafe_approval_hi"] - r["unsafe_approval_lo"]


def test_structured_spillway_reports_design_flood(tmp_path):
    from sfe.prompts import VERDICT_SCHEMA
    assert "design_flood_value" in VERDICT_SCHEMA["required"]
    t = new_trial(SPILL, "flawed_calc", "A", "claude-haiku-5-5", "M5", 0)
    answer = json.dumps({"verdict": "APPROVE", "criterion": "x", "computed_value": SPILL.true_value,
                         "design_flood_value": SPILL.required * 0.8, "reason": "r"})
    apply_reply(t, text(answer))
    raw = tmp_path / "raw.jsonl"
    raw.write_text(json.dumps(_record(t)) + "\n")
    out = tmp_path / "g.jsonl"
    grade_file(raw, out, cases_path=_cases_file(tmp_path), judge_round=lambda r, poll_seconds=30: {})
    g = json.loads(out.read_text())
    assert g["flood_pred"] == pytest.approx(SPILL.required * 0.8) and g["numeric_error"] is True
