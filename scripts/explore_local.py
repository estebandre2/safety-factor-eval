"""Exploratory E4 (amendment 2026-11-10 night): a local open-weight reasoning model (qwen3:14b via Ollama, on this
machine) as author on the 80 Phase 1 overturning cases (1 repeat, base prompt) and as reviewer (P1, then P2) on the
Phase 2 pool. Time-boxed: no new request starts after STOP_AT; whatever finished is reported, with counts.

Usage: uv run python scripts/explore_local.py [--authors] [--reviews]
Writes results/raw/explore_local.jsonl (authors) and results/raw/explore_local_reviews.jsonl (reviews)."""
import argparse
import json
from datetime import datetime
from pathlib import Path

import httpx

from sfe.backends.ollama import run_ollama
from sfe.cases import load_cases
from sfe.engine import new_trial
from sfe.grade import _delivered
from sfe.review import review_id, review_request, score_review
from sfe.run import _record, _run_sync

MODEL = "qwen3:14b"
STOP_AT = "05:00"
CASES = {c.id: c for c in load_cases(Path("data/cases_phase1.jsonl"))}
AUTH_OUT, REV_OUT = Path("results/raw/explore_local.jsonl"), Path("results/raw/explore_local_reviews.jsonl")
POOL = Path("results/raw/phase2_pool.jsonl")


def time_left() -> bool:
    return datetime.now().strftime("%H:%M") < STOP_AT or datetime.now().hour >= 12


def done(path: Path, key: str) -> set[str]:
    if not path.exists():
        return set()
    return {r[key] for r in map(json.loads, path.read_text().splitlines()) if r.get("status") == "done"}


def authors() -> None:
    finished = done(AUTH_OUT, "trial_id")
    trials = [new_trial(c, "neutral", "A", MODEL, "M0", 0, effort="high", variant="base")
              for c in CASES.values() if c.family == "overturning"]
    with AUTH_OUT.open("a") as fh:
        for t in trials:
            if t.trial_id in finished:
                continue
            if not time_left():
                print("Authors: stopped at the time box.")
                return
            fh.write(json.dumps(_record(_run_sync(t, run_ollama))) + "\n")
            fh.flush()
    print("Authors: complete.")


def reviews() -> None:
    finished = done(REV_OUT, "review_id")
    pool = [json.loads(l) for l in POOL.read_text().splitlines()]
    with REV_OUT.open("a") as fh:
        for protocol in ("P1", "P2"):
            for a in pool:
                rid = review_id(a["trial_id"], MODEL, protocol)
                if rid in finished:
                    continue
                if not time_left():
                    print("Reviews: stopped at the time box.")
                    return
                case = CASES[a["case_id"]]
                try:
                    reply = run_ollama(review_request(case, _delivered(a) or "", protocol), MODEL)
                except httpx.HTTPError as exc:
                    print(f"review failed: {type(exc).__name__}")
                    continue
                status = "done" if reply.stop_reason == "end_turn" else reply.stop_reason
                fh.write(json.dumps({
                    "review_id": rid, "answer_trial_id": a["trial_id"], "case_id": a["case_id"], "family": a["family"],
                    "author": a["model"], "answer_wrong": bool(a["numeric_error"]), "reviewer": MODEL,
                    "protocol": protocol, "status": status, "review": reply.text, "usage": reply.usage, "cost_usd": 0.0,
                    **score_review(case, a, reply.text), "finished_at": datetime.now().isoformat()}) + "\n")
                fh.flush()
    print("Reviews: complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--authors", action="store_true")
    parser.add_argument("--reviews", action="store_true")
    args = parser.parse_args()
    if args.authors:
        authors()
    if args.reviews:
        reviews()
