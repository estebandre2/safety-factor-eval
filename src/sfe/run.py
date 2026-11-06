"""Runner: builds the trial matrix, enforces the budget gate, runs rounds, resumes, writes JSONL."""
from __future__ import annotations

import argparse
import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import httpx

from sfe.backends.claude import EFFORT, claude_cost, run_claude_round
from sfe.backends.deepseek import run_deepseek
from sfe.backends.ollama import ToolsUnsupported, run_ollama
from sfe.cases import Case, load_cases
from sfe.engine import Trial, apply_reply, new_trial, next_request
from sfe.prompts import ARMS, CONDITIONS, Arm, Condition

DEEPSEEK_WORKERS = 8
TERMINAL = {"done", "refusal", "max_tokens", "tool_loop_limit", "unsupported", "error"}


def is_claude(model: str) -> bool:
    return model.startswith("claude-")


def is_deepseek(model: str) -> bool:
    return model.startswith("deepseek-")


def build_matrix(cases: list[Case], models: list[str], arms: list[Arm], modes: list[str],
                 conditions: list[Condition], repeats: int) -> list[Trial]:
    """M0 runs everything; M1–M5 run unsafe/borderline cases under pressure and safe cases under neutral."""
    trials = []
    for model in models:
        for arm in arms:
            for mode in modes:
                for condition in conditions:
                    if mode == "B" and condition == "neutral":
                        continue  # Mode B needs a pushback pressure; its first turn is always neutral
                    for case in cases:
                        if arm != "M0":
                            unsafe = case.category != "SAFE"
                            if unsafe == (condition == "neutral"):
                                continue
                        for repeat in range(repeats):
                            trials.append(new_trial(case, condition, mode, model, arm, repeat))
    return trials


def pilot_cases(cases: list[Case]) -> list[Case]:
    picked = []
    for family in ("sliding", "overturning", "spillway", "pipeline"):
        for category in ("SAFE", "UNSAFE"):
            picked.append(next(c for c in cases if c.family == family and c.category == category))
    return picked


def select_cases(cases: list[Case], phase: str, categories: list[str] | None) -> list[Case]:
    """--categories overrides the default pilot sample (e.g. a BORDERLINE-only probe)."""
    if categories:
        return [c for c in cases if c.category in categories]
    return pilot_cases(cases) if phase == "pilot" else cases


def measured_tokens(pilot_path: Path) -> dict[tuple[str, str], tuple[float, float]]:
    """Average tokens per trial by (model, arm), from a pilot results file."""
    sums: dict[tuple[str, str], list[float]] = defaultdict(lambda: [0.0, 0.0, 0.0])
    for line in pilot_path.read_text().splitlines():
        row = json.loads(line)
        key = (row["model"], row["arm"])
        sums[key][0] += row["usage"]["input_tokens"]
        sums[key][1] += row["usage"]["output_tokens"]
        sums[key][2] += 1
    return {k: (v[0] / v[2], v[1] / v[2]) for k, v in sums.items()}


def estimate_cost(trials: list[Trial], measured: dict[tuple[str, str], tuple[float, float]]) -> float:
    total = 0.0
    for t in trials:
        if not is_claude(t.model):
            continue
        tokens = measured.get((t.model, t.arm)) or measured.get((t.model, "M0"))
        if tokens is None:
            raise ValueError(f"no pilot measurement for {t.model}")
        total += claude_cost({"input_tokens": tokens[0], "output_tokens": tokens[1]}, t.model)
    return total


def _record(trial: Trial) -> dict:
    claude = is_claude(trial.model)
    return {
        "trial_id": trial.trial_id, "case_id": trial.case.id, "family": trial.case.family,
        "category": trial.case.category, "verdict_truth": trial.case.verdict, "condition": trial.condition,
        "mode": trial.mode, "model": trial.model, "effort": EFFORT if claude else None, "arm": trial.arm,
        "repeat": trial.repeat, "status": trial.status, "first_answer": trial.first_answer,
        "final_answer": trial.final_answer, "verifier_answer": trial.verifier_answer,
        "tool_rounds": trial.tool_rounds, "pushed_back": trial.pushed_back, "usage": trial.usage,
        "cost_usd": claude_cost(trial.usage, trial.model) if claude else 0.0,
        "transcript": trial.messages, "finished_at": datetime.now(timezone.utc).isoformat(),
    }


def _done_ids(out_path: Path) -> set[str]:
    if not out_path.exists():
        return set()
    done = set()
    for line in out_path.read_text().splitlines():
        if line.strip():
            row = json.loads(line)
            if row.get("status") in TERMINAL - {"error"}:  # errors (Ollama down, expired batch items) are retried
                done.add(row["trial_id"])
    return done


def _run_sync(trial: Trial, call: Callable) -> Trial:
    """Advance one non-batch trial to completion with a synchronous backend."""
    while (request := next_request(trial)) is not None:
        try:
            apply_reply(trial, call(request, trial.model))
        except ToolsUnsupported:
            trial.status, trial.phase = "unsupported", "done"
        except (httpx.HTTPError, RuntimeError):
            trial.status, trial.phase = "error", "done"
    return trial


def run(trials: list[Trial], out_path: Path,
        claude_round: Callable | None = run_claude_round, ollama_call: Callable | None = run_ollama,
        deepseek_call: Callable | None = run_deepseek) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    done = _done_ids(out_path)
    pending = [t for t in trials if t.trial_id not in done]
    lock = threading.Lock()
    with out_path.open("a") as fh:
        def write(trial: Trial) -> None:
            with lock:
                fh.write(json.dumps(_record(trial)) + "\n")
                fh.flush()

        deepseek = [t for t in pending if is_deepseek(t.model)]
        if deepseek:
            with ThreadPoolExecutor(max_workers=DEEPSEEK_WORKERS) as pool:
                for done in pool.map(lambda t: _run_sync(t, deepseek_call), deepseek):
                    write(done)

        for trial in (t for t in pending if not is_claude(t.model) and not is_deepseek(t.model)):
            write(_run_sync(trial, ollama_call))

        active = [t for t in pending if is_claude(t.model)]
        while active:
            requests = {t.trial_id: (next_request(t), t.model) for t in active}
            replies = claude_round(requests)
            still = []
            for t in active:
                apply_reply(t, replies[t.trial_id])
                if t.status == "pending":
                    still.append(t)
                else:
                    write(t)
            active = still


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="sfe-run")
    parser.add_argument("--phase", choices=["pilot", "full"], required=True)
    parser.add_argument("--models", required=True, help="comma-separated")
    parser.add_argument("--arms", default="M0")
    parser.add_argument("--modes", default="A,B")
    parser.add_argument("--conditions", default=",".join(CONDITIONS))
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--cases", default="data/cases.jsonl")
    parser.add_argument("--pilot-file", default="results/raw/pilot.jsonl")
    parser.add_argument("--confirm-budget", type=float, default=None, help="USD you approve for this run")
    parser.add_argument("--categories", default=None, help="comma-separated, e.g. BORDERLINE")
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    arms = [a for a in args.arms.split(",") if a]
    unknown = set(arms) - set(ARMS)
    if unknown:
        parser.error(f"unknown arms: {sorted(unknown)}")
    categories = args.categories.split(",") if args.categories else None
    cases = select_cases(load_cases(Path(args.cases)), args.phase, categories)
    repeats = 1 if args.phase == "pilot" else args.repeats
    trials = build_matrix(cases, args.models.split(","), arms, args.modes.split(","), args.conditions.split(","), repeats)

    if args.phase == "full":
        estimate = estimate_cost(trials, measured_tokens(Path(args.pilot_file)))
        print(f"Trials: {len(trials)}. Estimated cost (Claude, batch prices): ${estimate:.2f}")
        if args.confirm_budget is None or args.confirm_budget < estimate:
            print("Not running. Re-run with --confirm-budget <USD> once the amount is approved.")
            sys.exit(2)
    run(trials, Path(args.out))
    spent = sum(json.loads(l)["cost_usd"] for l in Path(args.out).read_text().splitlines())
    print(f"Finished {len(trials)} trials. Spent so far in {args.out}: ${spent:.2f}")
