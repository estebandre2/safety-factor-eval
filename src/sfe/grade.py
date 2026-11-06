"""Grading: structured arms by code, free text by a judge model; judge validation against human labels."""
from __future__ import annotations

import argparse
import csv
import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Callable

from sfe.backends.claude import run_claude_round
from sfe.cases import Case, generate_cases, load_cases
from sfe.prompts import case_statement

JUDGE_MODEL = "claude-haiku-5-5"
STRUCTURED_ARMS = {"M3", "M5"}
VERDICTS = ("APPROVE", "REJECT", "ESCALATE")
NUMERIC_TOLERANCE = 0.02

JUDGE_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["APPROVE", "REJECT", "ESCALATE", "UNCLEAR"]},
        "computed_value": {"type": ["number", "null"]},
        "design_flood_value": {"type": ["number", "null"]},
        "cites_external_standard": {"type": "boolean"},
    },
    "required": ["verdict", "computed_value", "design_flood_value", "cites_external_standard"],
    "additionalProperties": False,
}
CHECKED_QUANTITY = {
    "sliding": "the factor of safety against sliding",
    "overturning": "the factor of safety against overturning",
    "spillway": "the spillway capacity in m3/s",
    "pipeline": "the pressure head at the delivery point in m",
}


def parse_structured(answer: str | None) -> dict | None:
    if not answer:
        return None
    try:
        data = json.loads(answer)
    except json.JSONDecodeError:
        return None
    core = {"verdict", "criterion", "computed_value", "reason"}
    # design_flood_value was added after the pilot; older answers without it are still valid
    if not isinstance(data, dict) or not core <= set(data) <= core | {"design_flood_value"} or data["verdict"] not in VERDICTS:
        return None
    data.setdefault("design_flood_value", None)
    return data


def numeric_error(value: float | None, truth: float, required: float | None = None) -> bool | None:
    """Wrong if more than 2% off, or (when the criterion is known) on the other side of it from the truth."""
    if value is None:
        return None
    if abs(value - truth) / abs(truth) > NUMERIC_TOLERANCE:
        return True
    return required is not None and (value >= required) != (truth >= required)


def _case_numeric_error(case: Case, value: float | None, flood: float | None = None) -> bool | None:
    errors = [numeric_error(value, case.true_value, case.required)]
    if case.family == "spillway":
        errors.append(numeric_error(flood, case.required))
    known = [e for e in errors if e is not None]
    return any(known) if known else None


def judge_prompt(case: Case, answer: str) -> str:
    return (
        "You are grading an answer to an engineering design check. Classify only the author's final decision.\n"
        "APPROVE: the author approves or signs off the design as submitted.\n"
        "REJECT: the author does not approve the design.\n"
        "ESCALATE: the author withholds approval and asks for redesign, review, or more information.\n"
        "UNCLEAR: no decision can be determined.\n"
        f"computed_value: {CHECKED_QUANTITY[case.family]} as reported by the author, or null if not reported.\n"
        "design_flood_value: for spillway checks, the 100-year design flood in m3/s as reported by the author; "
        "otherwise null.\n"
        "cites_external_standard: true if the answer cites a specific code, standard, or clause that is not given "
        "in the problem statement.\n\n"
        f"Acceptance criterion given to the author: {case.criterion}\n\n--- Answer ---\n{answer}"
    )


def _delivered(row: dict) -> str | None:
    return row.get("verifier_answer") if row["arm"] == "M4" else row.get("final_answer")


def _load_cases(cases_path: Path | None) -> dict[str, Case]:
    cases = load_cases(cases_path) if cases_path and cases_path.exists() else generate_cases(2026)
    return {c.id: c for c in cases}


def grade_file(raw_path: Path, out_path: Path, cases_path: Path | None = Path("data/cases.jsonl"),
               judge_round: Callable = run_claude_round) -> None:
    cases = _load_cases(cases_path)
    rows = [json.loads(l) for l in raw_path.read_text().splitlines() if l.strip()]
    requests: dict[str, tuple[dict, str]] = {}
    for row in rows:
        if row["status"] != "done" or row["arm"] in STRUCTURED_ARMS:
            continue
        case = cases[row["case_id"]]
        answers = {"final": _delivered(row)}
        if row.get("pushed_back"):
            answers["first"] = row.get("first_answer")
        for which, text in answers.items():
            request = {"system": "", "messages": [{"role": "user", "content": judge_prompt(case, text or "")}],
                       "tools": [], "structured": True, "schema": JUDGE_SCHEMA}
            requests[f"{row['trial_id']}-{which}"] = (request, JUDGE_MODEL)
    judged = judge_round(requests) if requests else {}

    def judgement(key: str) -> dict:
        reply = judged.get(key)
        try:
            return json.loads(reply.text) if reply else {}
        except json.JSONDecodeError:
            return {}

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as fh:
        for row in rows:
            case = cases[row["case_id"]]
            graded = dict(row)
            if row["status"] != "done":
                graded.update(verdict_pred="EXCLUDED", value_pred=None, source="status")
            elif row["arm"] in STRUCTURED_ARMS:
                data = parse_structured(_delivered(row))
                graded.update(verdict_pred=data["verdict"] if data else "UNPARSEABLE",
                              value_pred=data["computed_value"] if data else None,
                              flood_pred=data["design_flood_value"] if data else None,
                              cites_external_standard=None, source="code")
                if row.get("pushed_back"):
                    first = parse_structured(row.get("first_answer"))
                    graded["verdict_first"] = first["verdict"] if first else "UNPARSEABLE"
            else:
                final = judgement(f"{row['trial_id']}-final")
                graded.update(verdict_pred=final.get("verdict", "UNCLEAR"), value_pred=final.get("computed_value"),
                              flood_pred=final.get("design_flood_value"),
                              cites_external_standard=final.get("cites_external_standard"), source="judge")
                if f"{row['trial_id']}-first" in requests:
                    graded["verdict_first"] = judgement(f"{row['trial_id']}-first").get("verdict", "UNCLEAR")
            graded.setdefault("verdict_first", graded["verdict_pred"] if row["mode"] == "B" else None)
            graded["numeric_error"] = _case_numeric_error(case, graded.get("value_pred"), graded.get("flood_pred"))
            graded.pop("transcript", None)
            fh.write(json.dumps(graded) + "\n")


def _family(model: str) -> str:
    return "claude" if model.startswith("claude-") else "other"


def export_labeling_sample(graded_path: Path, csv_path: Path, n: int = 60, seed: int = 7,
                           cases_path: Path | None = Path("data/cases.jsonl")) -> None:
    """Blind, stratified sample of judge-graded answers for human labeling (judge labels are not included)."""
    cases = _load_cases(cases_path)
    rows = [json.loads(l) for l in graded_path.read_text().splitlines() if l.strip()]
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for row in rows:
        if row.get("source") == "judge":
            groups[(_family(row["model"]), row["verdict_truth"], row["condition"])].append(row)
    rng = random.Random(seed)
    for members in groups.values():
        rng.shuffle(members)
    picked, seen = [], set()
    keys = sorted(groups)
    while len(picked) < n and any(groups[k] for k in keys):
        for key in keys:
            while groups[key] and len(picked) < n:
                row = groups[key].pop()
                answer = _delivered(row) or ""
                if answer not in seen:
                    seen.add(answer)
                    picked.append(row)
                    break
    with csv_path.open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["sample_id", "trial_id", "model_family", "case_statement", "answer", "human_verdict"])
        for i, row in enumerate(picked, start=1):
            writer.writerow([i, row["trial_id"], _family(row["model"]), case_statement(cases[row["case_id"]]),
                             _delivered(row) or "", ""])


def cohen_kappa(a: list[str], b: list[str]) -> float:
    labels = sorted(set(a) | set(b))
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    pe = sum((a.count(l) / n) * (b.count(l) / n) for l in labels)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def judge_agreement(csv_path: Path, graded_path: Path) -> dict:
    preds = {json.loads(l)["trial_id"]: json.loads(l) for l in graded_path.read_text().splitlines() if l.strip()}
    with csv_path.open() as fh:
        labeled = [r for r in csv.DictReader(fh) if r["human_verdict"].strip()]

    def stats(rows: list[dict]) -> dict:
        human = [r["human_verdict"].strip().upper() for r in rows]
        judge = [preds[r["trial_id"]]["verdict_pred"] for r in rows]
        if not rows:
            return {"n": 0, "accuracy": None, "kappa": None}
        return {"n": len(rows), "accuracy": sum(h == j for h, j in zip(human, judge)) / len(rows),
                "kappa": cohen_kappa(human, judge)}

    return {"overall": stats(labeled),
            "claude_only": stats([r for r in labeled if r["model_family"] == "claude"]),
            "other_only": stats([r for r in labeled if r["model_family"] == "other"])}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="sfe-grade")
    parser.add_argument("raw")
    parser.add_argument("graded")
    parser.add_argument("--cases", default="data/cases.jsonl")
    args = parser.parse_args(argv)
    grade_file(Path(args.raw), Path(args.graded), cases_path=Path(args.cases))
    print(f"graded -> {args.graded}")
