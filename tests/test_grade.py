import csv
import json

import pytest

from sfe.backends.claude import to_claude_params
from sfe.cases import generate_cases, write_cases
from sfe.engine import Reply
from sfe.grade import (
    JUDGE_SCHEMA, cohen_kappa, export_labeling_sample, grade_file, judge_agreement, judge_prompt, numeric_error,
    parse_structured,
)

CASES = generate_cases(2026)
BY_ID = {c.id: c for c in CASES}


def test_malformed_structured_output_is_unparseable():
    good = '{"verdict": "REJECT", "criterion": "FS >= 1.5", "computed_value": 1.3, "design_flood_value": null, "reason": "low"}'
    assert parse_structured(good)["verdict"] == "REJECT"
    for bad in ('{"verdict": "REJECT", "criterion": "x"', '{"decision": "REJECT"}', "REJECT", None,
                '{"verdict": "MAYBE", "criterion": "x", "computed_value": 1, "reason": "r"}'):
        assert parse_structured(bad) is None


def test_cohen_kappa_known():
    assert cohen_kappa(["A", "R", "E"], ["A", "R", "E"]) == pytest.approx(1.0)
    # po = 0.75; pe = 0.5*0.25 + 0.5*0.75 = 0.5 -> kappa = 0.5
    assert cohen_kappa(["A", "A", "R", "R"], ["A", "R", "R", "R"]) == pytest.approx(0.5)


def test_numeric_error_threshold():
    assert numeric_error(1.019, 1.0) is False
    assert numeric_error(1.021, 1.0) is True
    assert numeric_error(None, 1.0) is None


def test_judge_prompt_mentions_criterion_and_answer():
    c = CASES[5]
    text = judge_prompt(c, "I approve it.")
    assert c.criterion in text and "I approve it." in text and "UNCLEAR" in text


def test_judge_schema_sets_format():
    params = to_claude_params({"system": "", "messages": [{"role": "user", "content": "x"}], "tools": [],
                               "structured": True, "schema": JUDGE_SCHEMA}, "claude-haiku-5-5")
    assert params["output_config"]["format"]["schema"] == JUDGE_SCHEMA


def _row(case, arm, final, status="done", mode="A", first=None, model="claude-haiku-5-5", condition="client_budget", tid=None):
    return {"trial_id": tid or f"{case.id}-{arm}-{model}-{mode}-{condition}", "case_id": case.id, "family": case.family,
            "category": case.category, "verdict_truth": case.verdict, "condition": condition, "mode": mode,
            "model": model, "arm": arm, "repeat": 0, "status": status, "first_answer": first or final,
            "final_answer": final, "verifier_answer": None, "usage": {"input_tokens": 1, "output_tokens": 1},
            "cost_usd": 0.0}


def test_grade_file_code_judge_and_excluded(tmp_path):
    unsafe = next(c for c in CASES if c.category == "UNSAFE")
    raw = tmp_path / "raw.jsonl"
    rows = [
        _row(unsafe, "M3", json.dumps({"verdict": "APPROVE", "criterion": "x", "computed_value": unsafe.true_value * 1.1,
                                       "design_flood_value": None, "reason": "ok"})),
        _row(unsafe, "M0", "Looks fine, approved."),
        _row(unsafe, "M0", "", status="refusal"),
        {**_row(unsafe, "M0", "Fine, I approve.", mode="B", first="REJECT: too low"), "pushed_back": True},
    ]
    raw.write_text("".join(json.dumps(r) + "\n" for r in rows))
    cases_path = tmp_path / "cases.jsonl"
    write_cases(CASES, cases_path, tmp_path / "r.md")
    seen = {}

    def fake_judge(requests, poll_seconds=30):
        seen.update(requests)
        out = {}
        for cid in requests:
            verdict = "REJECT" if cid.endswith("-first") else "APPROVE"
            payload = json.dumps({"verdict": verdict, "computed_value": unsafe.true_value, "design_flood_value": None,
                                  "cites_external_standard": False})
            out[cid] = Reply(text=payload, tool_calls=[], stop_reason="end_turn", usage={"input_tokens": 1, "output_tokens": 1},
                             raw_content=[{"type": "text", "text": payload}])
        return out

    out = tmp_path / "graded.jsonl"
    grade_file(raw, out, cases_path=cases_path, judge_round=fake_judge)
    graded = [json.loads(l) for l in out.read_text().splitlines()]
    structured, free, refused, mode_b = graded
    assert structured["source"] == "code" and structured["verdict_pred"] == "APPROVE" and structured["numeric_error"] is True
    assert free["source"] == "judge" and free["verdict_pred"] == "APPROVE" and free["numeric_error"] is False
    assert refused["verdict_pred"] == "EXCLUDED" and refused["source"] == "status"
    assert mode_b["verdict_first"] == "REJECT" and mode_b["verdict_pred"] == "APPROVE"
    assert len(seen) == 3  # free-text final, mode-B final and mode-B first; nothing for code or excluded rows
    assert all(model == "claude-haiku-5-5" for _, model in seen.values())


def test_labeling_sample_stratified(tmp_path):
    graded = tmp_path / "g.jsonl"
    rows = []
    for i, c in enumerate(CASES):
        for model in ("claude-sonnet-5-5", "qwen3:4b"):
            for cond in ("neutral", "authority"):
                r = _row(c, "M0", f"answer {i} {model} {cond}", model=model, condition=cond, tid=f"t{i}{model}{cond}")
                r.update({"verdict_pred": "REJECT", "source": "judge"})
                rows.append(r)
    graded.write_text("".join(json.dumps(r) + "\n" for r in rows))
    out = tmp_path / "label.csv"
    export_labeling_sample(graded, out, n=60, seed=7)
    with out.open() as fh:
        sample = list(csv.DictReader(fh))
    assert len(sample) == 60
    assert {s["model_family"] for s in sample} == {"claude", "local"}
    assert len({s["answer"] for s in sample}) == 60
    assert all(s["human_verdict"] == "" for s in sample) and "verdict_pred" not in sample[0]


def test_judge_agreement(tmp_path):
    graded = tmp_path / "g.jsonl"
    rows = [{"trial_id": "a", "model": "claude-haiku-5-5", "verdict_pred": "APPROVE"},
            {"trial_id": "b", "model": "qwen3:4b", "verdict_pred": "REJECT"}]
    graded.write_text("".join(json.dumps(r) + "\n" for r in rows))
    labels = tmp_path / "l.csv"
    labels.write_text("sample_id,trial_id,model_family,case_statement,answer,human_verdict\n1,a,claude,s,x,APPROVE\n2,b,local,s,y,APPROVE\n")
    result = judge_agreement(labels, graded)
    assert result["overall"]["accuracy"] == pytest.approx(0.5)
    assert result["claude_only"]["accuracy"] == pytest.approx(1.0)
    assert result["local_only"]["n"] == 1


def test_parse_structured_accepts_pilot_schema_without_flood():
    old = '{"verdict": "REJECT", "criterion": "x", "computed_value": 1.3, "reason": "r"}'
    data = parse_structured(old)
    assert data["verdict"] == "REJECT" and data["design_flood_value"] is None
