"""Study II, Phase 0 (spec 2026-11-10 §4): effort and wording on the 10 Study I overturning cases.

Usage:
  uv run python scripts/phase0.py --token-check            # 10 trials at max effort; prints measured cost per trial
  uv run python scripts/phase0.py --confirm-budget 12      # full Phase 0, refuses if the estimate exceeds the budget
Writes results/raw/phase0.jsonl (resumable).
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

from sfe.backends.claude import claude_cost
from sfe.cases import load_cases
from sfe.engine import new_trial
from sfe.run import is_claude, run

CLAUDE = ["claude-haiku-5-5", "claude-sonnet-5-5", "claude-opus-5-5"]
ARMS = {"0A": ("base", "max"), "0B": ("coords", "max"), "0C": ("bare", "max"), "0D": ("base", "high")}
DEEPSEEK_ARMS = {"0E-coords": "coords", "0E-bare": "bare"}
REPEATS = 3
OUT = Path("results/raw/phase0.jsonl")  # the token-check trials go here too, so they are not paid twice


def trials(cases, repeats: dict[str, int] | None = None):
    repeats = repeats or {arm: REPEATS for arm in ARMS}
    out = []
    for model in CLAUDE:
        for arm, (variant, effort) in ARMS.items():
            for case in cases:
                for rep in range(repeats[arm]):
                    out.append(new_trial(case, "neutral", "A", model, "M0", rep, effort=effort, variant=variant))
    for variant in DEEPSEEK_ARMS.values():
        for case in cases:
            out.append(new_trial(case, "neutral", "A", "deepseek-v4-pro", "M0", 0, effort="high", variant=variant))
    return out


def measured_cost(path: Path) -> dict[str, float]:
    """Mean cost per finished trial by model (errored rows cost nothing and would lower the estimate)."""
    sums = defaultdict(lambda: [0.0, 0])
    for line in path.read_text().splitlines():
        row = json.loads(line)
        if row["status"] != "done":
            continue
        sums[row["model"]][0] += row["cost_usd"]
        sums[row["model"]][1] += 1
    return {m: c / n for m, (c, n) in sums.items()}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--token-check", action="store_true")
    parser.add_argument("--explore-high", action="store_true",
                        help="Amendment 2026-11-10: exploratory arms 0B and 0C at effort high (Claude, 3 repeats)")
    parser.add_argument("--confirm-budget", type=float)
    args = parser.parse_args()
    cases = [c for c in load_cases(Path("data/cases.jsonl")) if c.family == "overturning"]
    assert len(cases) == 10

    if args.explore_high:
        extra = [new_trial(c, "neutral", "A", m, "M0", rep, effort="high", variant=v)
                 for m in CLAUDE for v in ("coords", "bare") for c in cases for rep in range(REPEATS)]
        run(extra, OUT)
        ids = {t.trial_id for t in extra}
        spent = sum(r["cost_usd"] for r in map(json.loads, OUT.read_text().splitlines()) if r["trial_id"] in ids)
        print(f"Exploratory 0B/0C at high: {len(extra)} trials, Claude spent ${spent:.2f}")
        return

    if args.token_check:
        picks = [new_trial(cases[i], "neutral", "A", CLAUDE[i % 3], "M0", 0, effort="max", variant="base") for i in range(10)]
        run(picks, OUT)
        ids = {t.trial_id for t in picks}
        for r in (json.loads(l) for l in OUT.read_text().splitlines()):
            if r["trial_id"] in ids:
                print(r["model"], r["status"], r["usage"], f"${r['cost_usd']:.4f}")
        print("cost per trial at max:", {m: round(c, 4) for m, c in measured_cost(OUT).items()})
        return

    per_trial = measured_cost(OUT)
    missing = set(CLAUDE) - set(per_trial)
    if missing:
        sys.exit(f"No finished token-check trials for {sorted(missing)}; run --token-check first.")
    # Spec §4 cut rule: 3 repeats; then 2 for 0C and 0D; then 2 for every arm.
    for repeats in ({a: 3 for a in ARMS}, {"0A": 3, "0B": 3, "0C": 2, "0D": 2}, {a: 2 for a in ARMS}):
        all_trials = trials(cases, repeats)
        estimate = sum(per_trial[t.model] for t in all_trials if is_claude(t.model))
        if args.confirm_budget is not None and estimate <= args.confirm_budget:
            break
    print(f"Phase 0: {len(all_trials)} trials, repeats {repeats}. Claude estimate: ${estimate:.2f} (includes trials already run)")
    if args.confirm_budget is None or args.confirm_budget < estimate:
        print("Not running. Re-run with --confirm-budget <USD> at or above the estimate.")
        sys.exit(2)
    run(all_trials, OUT)
    spent = sum(json.loads(l)["cost_usd"] for l in OUT.read_text().splitlines())
    print(f"Done. Claude spent in {OUT}: ${spent:.2f}")


if __name__ == "__main__":
    main()
