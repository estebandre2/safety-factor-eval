"""Study II exploratory additions (amendment 2026-11-10 night; committed before running, published after).

E1: effort dose-response on the 80 Phase 1 overturning cases at "low" and "medium" (base prompt).
E2: the author is asked for every load's line of action before computing (variant "setup"), at "high".
Same repeats as Phase 1 (Haiku 3, Sonnet 2, Opus 2). Writes results/raw/explore.jsonl.

Usage:
  uv run python scripts/explore.py                      # estimate only
  uv run python scripts/explore.py --confirm-budget 30  # run (refuses above the estimate)
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

from sfe.backends.claude import claude_cost
from sfe.cases import load_cases
from sfe.engine import new_trial
from sfe.run import run

CASES = Path("data/cases_phase1.jsonl")
OUT = Path("results/raw/explore.jsonl")
REPEATS = {"claude-haiku-5-5": 3, "claude-sonnet-5-5": 2, "claude-opus-5-5": 2}
ARMS = [("low", "base"), ("medium", "base"), ("high", "setup")]


def plan():
    cases = [c for c in load_cases(CASES) if c.family == "overturning"]
    return [new_trial(c, "neutral", "A", m, "M0", rep, effort=e, variant=v)
            for e, v in ARMS for m, reps in REPEATS.items() for c in cases for rep in range(reps)]


def per_trial_cost() -> dict[str, float]:
    """Phase 1 high-arm overturning cost per trial, used for every arm (low/medium are cheaper; setup adds text)."""
    s = defaultdict(lambda: [0.0, 0])
    for r in map(json.loads, Path("results/raw/phase1.jsonl").read_text().splitlines()):
        if r["family"] == "overturning" and r.get("effort") == "high":
            s[r["model"]][0] += r["cost_usd"]
            s[r["model"]][1] += 1
    return {m: c / n for m, (c, n) in s.items()}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm-budget", type=float)
    args = parser.parse_args()
    trials = plan()
    per = per_trial_cost()
    estimate = 1.3 * sum(per[t.model] for t in trials)  # 30% margin for longer set-up answers
    print(f"Exploratory: {len(trials)} trials. Claude estimate: ${estimate:.2f}")
    if args.confirm_budget is None or estimate > args.confirm_budget:
        print("Not running. Re-run with --confirm-budget <USD> at or above the estimate.")
        sys.exit(2)
    run(trials, OUT)
    spent = sum(json.loads(l)["cost_usd"] for l in OUT.read_text().splitlines())
    print(f"Done. Claude spent in {OUT}: ${spent:.2f}")


if __name__ == "__main__":
    main()
