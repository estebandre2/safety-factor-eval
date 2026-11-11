"""Study II exploratory additions (amendment 2026-11-10 night; committed before running, published after).

E1: effort dose-response on the 80 Phase 1 overturning cases at "low" and "medium" (base prompt).
E2: the author is asked for every load's line of action before computing (variant "setup"), at "high".
E5-E6 (--round2): "apex" sentence at "high"; set-up-first at "low" and "medium". Writes explore2.jsonl.
E3 (--nouplift): the same 80 dams with no uplift (data/cases_explore_nouplift.jsonl), base prompt, at "high".
Same repeats as Phase 1 (Haiku 3, Sonnet 2, Opus 2). Writes results/raw/explore.jsonl (E3: explore_nouplift.jsonl).

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
NOUPLIFT_CASES, NOUPLIFT_OUT = Path("data/cases_explore_nouplift.jsonl"), Path("results/raw/explore_nouplift.jsonl")
REPEATS = {"claude-haiku-5-5": 3, "claude-sonnet-5-5": 2, "claude-opus-5-5": 2}
ARMS = [("low", "base"), ("medium", "base"), ("high", "setup")]
ARMS2 = [("high", "apex"), ("low", "setup"), ("medium", "setup")]  # E5, E6
OUT2 = Path("results/raw/explore2.jsonl")
# Round 3: held-out dams (new seed) with a placebo control; plus set-up-first on the other Phase 1 families.
HOLDOUT_CASES, OUT3, OUT3_SIDE = (Path("data/cases_explore_holdout.jsonl"), Path("results/raw/explore3.jsonl"),
                                  Path("results/raw/explore3_side.jsonl"))
ARMS3 = [("high", "base"), ("high", "setup"), ("high", "apex"), ("high", "placebo"), ("low", "base"), ("low", "setup")]


def plan3(side: bool = False):
    if side:
        cases = [c for c in load_cases(CASES) if c.family in ("gate", "wall", "sliding")]
        arms = [("high", "setup")]
    else:
        cases, arms = load_cases(HOLDOUT_CASES), ARMS3
    return [new_trial(c, "neutral", "A", m, "M0", rep, effort=e, variant=v)
            for e, v in arms for m, reps in REPEATS.items() for c in cases for rep in range(reps)]


def plan(nouplift: bool = False, round2: bool = False):
    cases = load_cases(NOUPLIFT_CASES) if nouplift else [c for c in load_cases(CASES) if c.family == "overturning"]
    arms = [("high", "base")] if nouplift else (ARMS2 if round2 else ARMS)
    return [new_trial(c, "neutral", "A", m, "M0", rep, effort=e, variant=v)
            for e, v in arms for m, reps in REPEATS.items() for c in cases for rep in range(reps)]


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
    parser.add_argument("--nouplift", action="store_true", help="run E3 instead of E1-E2")
    parser.add_argument("--round2", action="store_true", help="run E5-E6 instead of E1-E2")
    parser.add_argument("--round3", action="store_true", help="held-out dams with placebo control")
    parser.add_argument("--side", action="store_true", help="round 3: set-up-first on gate, wall, sliding")
    parser.add_argument("--oss-setup", action="store_true", help="E7: set-up-first on gpt-oss-120b (OpenRouter)")
    args = parser.parse_args()
    if args.oss_setup:  # within the prepaid OpenRouter balance; no Claude cost except the judge
        cases = [c for c in load_cases(CASES) if c.family == "overturning"]
        trials = [new_trial(c, "neutral", "A", "gpt-oss-120b", "M0", 0, effort="high", variant="setup") for c in cases]
        out = Path("results/raw/explore_oss.jsonl")
        print(f"E7: {len(trials)} gpt-oss-120b trials -> {out}")
        run(trials, out)
        return
    if args.round3 or args.side:
        trials, out = plan3(args.side), (OUT3_SIDE if args.side else OUT3)
    else:
        trials = plan(args.nouplift, args.round2)
        out = NOUPLIFT_OUT if args.nouplift else (OUT2 if args.round2 else OUT)
    per = per_trial_cost()
    estimate = 1.3 * sum(per[t.model] for t in trials)  # 30% margin for longer set-up answers
    print(f"Exploratory: {len(trials)} trials. Claude estimate: ${estimate:.2f}")
    if args.confirm_budget is None or estimate > args.confirm_budget:
        print("Not running. Re-run with --confirm-budget <USD> at or above the estimate.")
        sys.exit(2)
    run(trials, out)
    spent = sum(json.loads(l)["cost_usd"] for l in out.read_text().splitlines())
    print(f"Done. Claude spent in {out}: ${spent:.2f}")


if __name__ == "__main__":
    main()
