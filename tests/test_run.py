import json

import pytest

from sfe.cases import generate_cases, write_cases
from sfe.engine import Reply
from sfe.prompts import ARMS, CONDITIONS
from sfe.run import build_matrix, estimate_cost, main, measured_tokens, pilot_cases, run

CASES = generate_cases(2026)


def reply(text="REJECT"):
    return Reply(text=text, tool_calls=[], stop_reason="end_turn", usage={"input_tokens": 100, "output_tokens": 50},
                 raw_content=[{"type": "text", "text": text}])


def test_matrix_size_main():
    trials = build_matrix(CASES, ["claude-haiku-5-5"], ["M0"], ["A", "B"], list(CONDITIONS), 3)
    assert len(trials) == 1200
    assert len({t.trial_id for t in trials}) == 1200


def test_matrix_mitigations_scope():
    trials = build_matrix(CASES, ["m"], ["M2"], ["A"], list(CONDITIONS), 1)
    for t in trials:
        if t.case.category == "SAFE":
            assert t.condition == "neutral"
        else:
            assert t.condition != "neutral"
    # 24 unsafe/borderline x 4 pressures + 16 safe x neutral
    assert len(trials) == 24 * 4 + 16


def test_pilot_cases():
    pilot = pilot_cases(CASES)
    assert len(pilot) == 8
    assert {(c.family, c.category) for c in pilot} == {(f, k) for f in ("sliding", "overturning", "spillway", "pipeline") for k in ("SAFE", "UNSAFE")}


def test_run_writes_lines_and_mixes_backends(tmp_path):
    trials = build_matrix(CASES[:2], ["claude-haiku-5-5", "qwen3:4b"], ["M0"], ["A"], ["neutral"], 1)
    rounds = []

    def fake_round(requests, poll_seconds=30):
        rounds.append(len(requests))
        return {cid: reply() for cid in requests}

    out = tmp_path / "r.jsonl"
    run(trials, out, claude_round=fake_round, ollama_call=lambda req, model: reply())
    lines = [json.loads(x) for x in out.read_text().splitlines()]
    assert len(lines) == 4 and rounds == [2]
    claude = next(l for l in lines if l["model"] == "claude-haiku-5-5")
    assert claude["status"] == "done" and claude["effort"] == "medium" and claude["cost_usd"] > 0
    local = next(l for l in lines if l["model"] == "qwen3:4b")
    assert local["cost_usd"] == 0 and local["effort"] is None and local["final_answer"] == "REJECT"
    assert {"trial_id", "case_id", "family", "category", "verdict_truth", "condition", "mode", "arm", "repeat",
            "first_answer", "verifier_answer", "tool_rounds", "usage", "transcript", "finished_at"} <= set(claude)


def test_resume_skips_completed_trials(tmp_path):
    trials = build_matrix(CASES[:5], ["claude-haiku-5-5"], ["M0"], ["A"], ["neutral"], 1)
    out = tmp_path / "r.jsonl"
    out.write_text("".join(json.dumps({"trial_id": t.trial_id, "status": "done"}) + "\n" for t in trials))
    sent = []
    run(trials, out, claude_round=lambda reqs, poll_seconds=30: sent.append(reqs) or {}, ollama_call=None)
    assert sent == []


def test_ollama_unsupported_marks_trial(tmp_path):
    from sfe.backends.ollama import ToolsUnsupported
    trials = build_matrix(CASES[4:5], ["gemma4:e4b"], ["M1"], ["A"], ["client_budget"], 1)

    def boom(req, model):
        raise ToolsUnsupported("no tools")

    out = tmp_path / "r.jsonl"
    run(trials, out, claude_round=None, ollama_call=boom)
    assert json.loads(out.read_text())["status"] == "unsupported"


def test_budget_gate_exits_without_confirm(tmp_path, capsys):
    cases_path = tmp_path / "cases.jsonl"
    write_cases(CASES, cases_path, tmp_path / "r.md")
    pilot = tmp_path / "pilot.jsonl"
    pilot.write_text(json.dumps({"model": "claude-sonnet-5-5", "arm": "M0", "status": "done",
                                 "usage": {"input_tokens": 2000, "output_tokens": 1500}}) + "\n")
    args = ["--phase", "full", "--models", "claude-sonnet-5-5", "--arms", "M0", "--cases", str(cases_path),
            "--pilot-file", str(pilot), "--out", str(tmp_path / "full.jsonl")]
    with pytest.raises(SystemExit) as exc:
        main(args)
    assert exc.value.code == 2
    assert "Estimated cost" in capsys.readouterr().out


def test_estimate_cost_uses_measured_tokens(tmp_path):
    pilot = tmp_path / "pilot.jsonl"
    pilot.write_text(json.dumps({"model": "claude-sonnet-5-5", "arm": "M0", "status": "done",
                                 "usage": {"input_tokens": 1_000_000, "output_tokens": 0}}) + "\n")
    measured = measured_tokens(pilot)
    trials = build_matrix(CASES[:1], ["claude-sonnet-5-5", "qwen3:4b"], ["M0"], ["A"], ["neutral"], 1)
    assert estimate_cost(trials, measured) == pytest.approx(1.0)  # $2/M input at 50% batch discount


def test_results_never_contain_api_key(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-123")
    trials = build_matrix(CASES[:1], ["claude-haiku-5-5"], ["M0"], ["A"], ["neutral"], 1)
    out = tmp_path / "r.jsonl"
    run(trials, out, claude_round=lambda reqs, poll_seconds=30: {c: reply() for c in reqs}, ollama_call=None)
    assert "sk-ant-test-123" not in out.read_text()
