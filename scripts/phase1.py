"""Study II, Phase 1 (spec 2026-11-10 §4): breadth at the effort chosen by Phase 0.

Usage:
  uv run python scripts/phase1.py                       # prints the estimate, runs nothing
  uv run python scripts/phase1.py --confirm-budget 40   # runs, refuses above the Claude estimate
Effort comes from results/tables/phase0_summary.json ("phase1_effort"). Writes results/raw/phase1.jsonl.
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

from sfe.cases import load_cases
from sfe.engine import new_trial
from sfe.run import is_claude, run

CASES = Path("data/cases_phase1.jsonl")
PHASE0 = Path("results/raw/phase0.jsonl")
SUMMARY = Path("results/tables/phase0_summary.json")
OUT = Path("results/raw/phase1.jsonl")
REPEATS = {"claude-haiku-5-5": 3, "claude-sonnet-5-5": 2, "claude-opus-5-5": 2, "deepseek-flash": 2, "deepseek-v4-pro": 1}
V4_PRO_FAMILIES = {"overturning", "wall"}  # spec §4: budget


def trials(cases, effort: str, drop: set[str] = frozenset()):
    out = []
    for model, reps in REPEATS.items():
        if model in drop:
            continue
        model_effort = effort if is_claude(model) else "high"
        for case in cases:
            if model == "deepseek-v4-pro" and case.family not in V4_PRO_FAMILIES:
                continue
            if case.family in drop:
                continue
            for rep in range(reps):
                out.append(new_trial(case, "neutral", "A", model, "M0", rep, effort=model_effort, variant="base"))
    return out


def cost_per_trial(effort: str) -> dict[str, float]:
    """Measured mean cost of finished Phase 0 base-prompt trials at this effort, by model."""
    sums = defaultdict(lambda: [0.0, 0])
    for row in map(json.loads, PHASE0.read_text().splitlines()):
        if row["status"] == "done" and row.get("variant") == "base" and row.get("effort") == effort:
            sums[row["model"]][0] += row["cost_usd"]
            sums[row["model"]][1] += 1
    return {m: c / n for m, (c, n) in sums.items() if n}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm-budget", type=float)
    args = parser.parse_args()
    effort = json.loads(SUMMARY.read_text())["phase1_effort"]
    cases = load_cases(CASES)
    per = cost_per_trial(effort)
    # Spec §8 cut order, applied only if the estimate exceeds the budget.
    for drop in (set(), {"wall"}, {"wall", "deepseek-v4-pro"}):
        plan = trials(cases, effort, drop)
        estimate = sum(per[t.model] for t in plan if is_claude(t.model))
        if args.confirm_budget is not None and estimate <= args.confirm_budget:
            break
    print(f"Phase 1 at effort {effort}: {len(plan)} trials (dropped: {sorted(drop) or 'nothing'}). "
          f"Claude estimate: ${estimate:.2f}")
    if args.confirm_budget is None or estimate > args.confirm_budget:
        print("Not running. Re-run with --confirm-budget <USD> at or above the estimate.")
        sys.exit(2)
    run(plan, OUT)
    spent = sum(json.loads(l)["cost_usd"] for l in OUT.read_text().splitlines())
    print(f"Done. Claude spent in {OUT}: ${spent:.2f}")


if __name__ == "__main__":
    main()
