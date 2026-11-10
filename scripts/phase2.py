"""Study II, Phase 2 (spec 2026-11-10 §4 + amendment): reviewers x protocols on a balanced pool of Phase 1 answers.

Usage:
  uv run python scripts/phase2.py                       # builds the pool, prints the estimate, runs nothing
  uv run python scripts/phase2.py --confirm-budget 40   # runs Claude + DeepSeek reviewers (resumable)
  uv run python scripts/phase2.py --gemini 60           # optional third provider on a 60-answer subsample (free tier)
Writes results/raw/phase2_pool.jsonl and results/raw/phase2.jsonl.
"""
import argparse
import json
import random
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import httpx

from sfe.backends.claude import claude_cost, run_claude_round
from sfe.backends.deepseek import run_deepseek
from sfe.backends.gemini import GEMINI_MODEL, run_gemini
from sfe.cases import load_cases
from sfe.grade import _delivered
from sfe.review import PROTOCOLS, build_matched_pool, review_id, review_request, score_review

CASES = {c.id: c for c in load_cases(Path("data/cases_phase1.jsonl"))}
GRADED = Path("results/graded/phase1.jsonl")
POOL = Path("results/raw/phase2_pool.jsonl")
OUT = Path("results/raw/phase2.jsonl")
CLAUDE_REVIEWERS = ["claude-haiku-5-5", "claude-sonnet-5-5", "claude-opus-5-5"]
DEEPSEEK_REVIEWER = "deepseek-flash"
REVIEW_COST_FACTOR = 1.5  # reviews read the answer too; estimate = 1.5 x the model's Phase 1 high-arm cost


def load_pool() -> list[dict]:
    if POOL.exists():
        return [json.loads(l) for l in POOL.read_text().splitlines()]
    rows = [json.loads(l) for l in GRADED.read_text().splitlines()]
    pool = build_matched_pool(rows)  # amendment 2026-11-10: case-matched, overturning only
    POOL.parent.mkdir(parents=True, exist_ok=True)
    POOL.write_text("".join(json.dumps(r) + "\n" for r in pool))
    return pool


def done_ids() -> set[str]:
    if not OUT.exists():
        return set()
    return {r["review_id"] for r in map(json.loads, OUT.read_text().splitlines()) if r["status"] == "done"}


def record(answer: dict, reviewer: str, protocol: str, reply, cost: float) -> dict:
    case = CASES[answer["case_id"]]
    status = "done" if reply.stop_reason == "end_turn" else reply.stop_reason
    return {"review_id": review_id(answer["trial_id"], reviewer, protocol), "answer_trial_id": answer["trial_id"],
            "case_id": answer["case_id"], "family": answer["family"], "author": answer["model"],
            "answer_wrong": bool(answer["numeric_error"]), "reviewer": reviewer, "protocol": protocol,
            "status": status, "review": reply.text, "usage": reply.usage, "cost_usd": cost,
            **score_review(case, answer, reply.text), "finished_at": datetime.now(timezone.utc).isoformat()}


def high_arm_cost() -> dict[str, float]:
    sums: dict[str, list[float]] = {}
    for r in map(json.loads, Path("results/raw/phase1.jsonl").read_text().splitlines()):
        if r["status"] == "done" and r.get("effort") == "high":
            s = sums.setdefault(r["model"], [0.0, 0])
            s[0] += r["cost_usd"]
            s[1] += 1
    return {m: c / n for m, (c, n) in sums.items()}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm-budget", type=float)
    parser.add_argument("--gemini", type=int, default=0, help="answers in the Gemini subsample (0 = skip)")
    args = parser.parse_args()
    pool = load_pool()
    wrong = sum(r["numeric_error"] for r in pool)
    print(f"Pool: {len(pool)} answers ({wrong} wrong, {len(pool) - wrong} correct)")
    finished = done_ids()
    todo = [(a, m, p) for a in pool for m in CLAUDE_REVIEWERS + [DEEPSEEK_REVIEWER] for p in PROTOCOLS
            if review_id(a["trial_id"], m, p) not in finished]

    if args.gemini:
        sample = random.Random(11).sample(pool, min(args.gemini, len(pool)))
        jobs = [(a, p) for a in sample for p in ("P1", "P2") if review_id(a["trial_id"], GEMINI_MODEL, p) not in finished]
        with OUT.open("a") as fh:
            for a, p in jobs:
                try:
                    reply = run_gemini(review_request(CASES[a["case_id"]], _delivered(a) or "", p), GEMINI_MODEL)
                except (httpx.HTTPError, RuntimeError) as exc:
                    print(f"Gemini stopped after a failure ({type(exc).__name__}); re-run later to resume.")
                    break
                fh.write(json.dumps(record(a, GEMINI_MODEL, p, reply, 0.0)) + "\n")
                fh.flush()
        return

    per = high_arm_cost()
    estimate = sum(per[m] * REVIEW_COST_FACTOR for _, m, _ in todo if m.startswith("claude-"))
    print(f"Reviews to run: {len(todo)}. Claude estimate: ${estimate:.2f}")
    if args.confirm_budget is None or estimate > args.confirm_budget:
        print("Not running. Re-run with --confirm-budget <USD> at or above the estimate.")
        sys.exit(2)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("a") as fh:
        ds = [(a, m, p) for a, m, p in todo if m == DEEPSEEK_REVIEWER]

        def ds_job(job):
            a, m, p = job
            try:
                reply = run_deepseek(review_request(CASES[a["case_id"]], _delivered(a) or "", p), m)
            except (httpx.HTTPError, RuntimeError):
                return None
            return record(a, m, p, reply, 0.0)

        with ThreadPoolExecutor(max_workers=8) as ex:
            for row in ex.map(ds_job, ds):
                if row:
                    fh.write(json.dumps(row) + "\n")
                    fh.flush()

        claude = {review_id(a["trial_id"], m, p): (a, m, p) for a, m, p in todo if m.startswith("claude-")}
        if claude:
            replies = run_claude_round({rid: (review_request(CASES[a["case_id"]], _delivered(a) or "", p), m)
                                        for rid, (a, m, p) in claude.items()})
            for rid, (a, m, p) in claude.items():
                reply = replies[rid]
                fh.write(json.dumps(record(a, m, p, reply, claude_cost(reply.usage, m))) + "\n")
    spent = sum(r["cost_usd"] for r in map(json.loads, OUT.read_text().splitlines()))
    print(f"Done. Claude spent in {OUT}: ${spent:.2f}")


if __name__ == "__main__":
    main()
