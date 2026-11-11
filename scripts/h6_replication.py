"""Exploratory replication of H6 and H4-Opus (amendment 2026-11-10 night) on held-out answers: Opus's round 3
answers on the 80 held-out dams (base prompt, effort "high") reviewed by Opus P1, Opus P2 and Haiku P2, with the
same requests and scoring as Phase 2. Writes results/raw/h6_reviews.jsonl. Analysis: --analyze."""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from sfe.analyze2 import _paired, _per_case_mean
from sfe.backends.claude import claude_cost, run_claude_round
from sfe.cases import load_cases
from sfe.grade import _delivered
from sfe.review import review_id, review_request, score_review

CASES = {c.id: c for c in load_cases(Path("data/cases_explore_holdout.jsonl"))}
SRC, OUT = Path("results/graded/explore3.jsonl"), Path("results/raw/h6_reviews.jsonl")
JOBS = [("claude-opus-5-5", "P1"), ("claude-opus-5-5", "P2"), ("claude-haiku-5-5", "P2")]


def answers() -> list[dict]:
    rows = [json.loads(l) for l in SRC.read_text().splitlines()]
    return [r for r in rows if r["model"] == "claude-opus-5-5" and r["effort"] == "high" and r["variant"] == "base"
            and r["status"] == "done" and r.get("numeric_error") is not None]


def run(budget: float) -> None:
    pool = answers()
    done = {json.loads(l)["review_id"] for l in OUT.read_text().splitlines()} if OUT.exists() else set()
    todo = {review_id(a["trial_id"], m, p): (a, m, p) for a in pool for m, p in JOBS
            if review_id(a["trial_id"], m, p) not in done}
    estimate = len(todo) * 0.01
    print(f"Pool: {len(pool)} answers ({sum(bool(a['numeric_error']) for a in pool)} wrong); reviews: {len(todo)}; "
          f"rough estimate ${estimate:.2f}")
    if estimate > budget:
        sys.exit("over budget")
    replies = run_claude_round({rid: (review_request(CASES[a["case_id"]], _delivered(a) or "", p), m)
                                for rid, (a, m, p) in todo.items()})
    with OUT.open("a") as fh:
        for rid, (a, m, p) in todo.items():
            reply = replies[rid]
            fh.write(json.dumps({
                "review_id": rid, "answer_trial_id": a["trial_id"], "case_id": a["case_id"], "author": a["model"],
                "answer_wrong": bool(a["numeric_error"]), "reviewer": m, "protocol": p,
                "status": "done" if reply.stop_reason == "end_turn" else reply.stop_reason, "review": reply.text,
                "usage": reply.usage, "cost_usd": claude_cost(reply.usage, m),
                **score_review(CASES[a["case_id"]], a, reply.text),
                "finished_at": datetime.now(timezone.utc).isoformat()}) + "\n")
    print(f"Done. Spent ${sum(json.loads(l)['cost_usd'] for l in OUT.read_text().splitlines()):.2f}")


def analyze() -> None:
    df = pd.DataFrame([json.loads(l) for l in OUT.read_text().splitlines()])
    df = df[df["status"] == "done"]
    pick = lambda m, p: df[(df["reviewer"] == m) & (df["protocol"] == p)]
    out = {"n_reviews": len(df), "rates": {}}
    for m, p in JOBS:
        g = pick(m, p)
        out["rates"][f"{m} | {p}"] = {"detection": float(g["detected"].dropna().mean()),
                                      "false_alarm": float(g["false_alarm"].dropna().mean()), "n": len(g)}
    h6 = _paired(_per_case_mean(pick("claude-haiku-5-5", "P2"), "detected"), _per_case_mean(pick("claude-opus-5-5", "P1"), "detected"))
    h4d = _paired(_per_case_mean(pick("claude-opus-5-5", "P2"), "detected"), _per_case_mean(pick("claude-opus-5-5", "P1"), "detected"))
    h4f = _paired(_per_case_mean(pick("claude-opus-5-5", "P2"), "false_alarm"), _per_case_mean(pick("claude-opus-5-5", "P1"), "false_alarm"))
    out |= {"H6_haikuP2_minus_opusP1": h6, "H6_replicated": bool(h6[1] > -0.05),
            "H4_opus_P2_minus_P1_detection": h4d, "H4_opus_P2_minus_P1_false_alarm": h4f,
            "H4_replicated": bool(h4d[0] >= 0.10 and h4d[1] > 0 and h4f[0] <= 0.05)}
    Path("results/tables/h6_replication_summary.json").write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--confirm-budget", type=float)
    ap.add_argument("--analyze", action="store_true")
    a = ap.parse_args()
    analyze() if a.analyze else run(a.confirm_budget or 0)
