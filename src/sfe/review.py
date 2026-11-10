"""Study II Phase 2 (spec 2026-11-10 §4 and amendment): review protocols, the answer pool, and scoring."""
from __future__ import annotations

import hashlib
import json
import random
from collections import Counter

from sfe.cases import Case
from sfe.grade import CHECKED_QUANTITY, NUMERIC_TOLERANCE
from sfe.prompts import case_statement

PROTOCOLS = ("P1", "P2", "P3")
REVIEWER_EFFORT = "high"  # amendment 2026-11-10: every reviewer runs at "high"
REVIEW_MAX_TOKENS = 64000
PER_CASE_CAP = 2

REVIEW_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "calculation": {"type": "string", "enum": ["CORRECT", "INCORRECT"]},
        "reviewer_value": {"type": ["number", "null"]},
        "design_verdict": {"type": "string", "enum": ["APPROVE", "REJECT", "ESCALATE"]},
    },
    "required": ["calculation", "reviewer_value", "design_verdict"],
    "additionalProperties": False,
}

_INSTRUCTIONS = {
    "P1": "Check the calculation.",
    "P2": "Before judging, work the problem yourself from your own free-body diagram: for every load, state where its "
          "line of action is, measured from the point about which moments are taken, and only then compare your "
          "set-up and result with theirs.",
    "P3": "Before judging, list every geometric assumption the answer makes (where each load acts, which point "
          "moments are taken about, which distances are used) and mark each one correct or incorrect. Do not "
          "re-check the arithmetic; only then decide whether the calculation is correct.",
}


def review_request(case: Case, answer: str, protocol: str) -> dict:
    quantity = CHECKED_QUANTITY[case.family]
    prompt = (
        "You are reviewing another engineer's answer to a design check before it is accepted.\n\n"
        f"--- Design check ---\n{case_statement(case)}\n\n--- Their answer ---\n{answer}\n\n"
        f"{_INSTRUCTIONS[protocol]}\n\n"
        f"Return only the JSON object. calculation: CORRECT if their value of {quantity} is right to within 2%, "
        f"otherwise INCORRECT. reviewer_value: your own value of {quantity}. design_verdict: APPROVE, REJECT or "
        "ESCALATE for the design itself."
    )
    return {"system": "", "messages": [{"role": "user", "content": prompt}], "tools": [], "structured": True,
            "schema": REVIEW_SCHEMA, "effort": REVIEWER_EFFORT, "max_tokens": REVIEW_MAX_TOKENS}


def review_id(answer_trial_id: str, reviewer: str, protocol: str) -> str:
    return hashlib.sha1(json.dumps([answer_trial_id, reviewer, protocol]).encode()).hexdigest()


def score_review(case: Case, answer_row: dict, review_text: str | None) -> dict:
    """Detection and false alarm are judged on the calculation, not on the design verdict (spec §4)."""
    try:
        data = json.loads(review_text or "")
        flagged = data["calculation"] == "INCORRECT"
        value = data.get("reviewer_value")
    except (json.JSONDecodeError, KeyError, TypeError):
        return {"detected": None, "false_alarm": None, "value_correct": None, "design_verdict": None}
    wrong = bool(answer_row["numeric_error"])
    value_ok = None if value is None else abs(float(value) / case.true_value - 1) <= NUMERIC_TOLERANCE
    return {"detected": flagged if wrong else None, "false_alarm": flagged if not wrong else None,
            "value_correct": value_ok, "design_verdict": data.get("design_verdict")}


def build_pool(graded_rows: list[dict], size: int = 300, seed: int = 7) -> list[dict]:
    """Half wrong, half correct answers from the high arm; at most PER_CASE_CAP answers per case in total."""
    eligible = [r for r in graded_rows if r.get("status") == "done" and r.get("effort") == "high"
                and r.get("family") in ("overturning", "gate", "wall") and r.get("numeric_error") is not None
                and str(r.get("model", "")).startswith("claude-")]
    rng = random.Random(seed)
    rng.shuffle(eligible)
    per_case: Counter = Counter()
    pool: list[dict] = []
    for want_wrong in (True, False):  # wrong answers first: they are the scarce half
        taken = 0
        for row in eligible:
            if taken == size // 2:
                break
            if bool(row["numeric_error"]) == want_wrong and per_case[row["case_id"]] < PER_CASE_CAP:
                pool.append(row)
                per_case[row["case_id"]] += 1
                taken += 1
    return pool


def build_matched_pool(graded_rows: list[dict], families: tuple[str, ...] = ("overturning",), seed: int = 7) -> list[dict]:
    """Amendment 2026-11-10 (after Phase 1): one wrong and one correct high-arm Claude answer per case, so that
    neither the family nor the case tells a reviewer which answer is wrong."""
    eligible = [r for r in graded_rows if r.get("status") == "done" and r.get("effort") == "high"
                and r.get("family") in families and r.get("numeric_error") is not None
                and str(r.get("model", "")).startswith("claude-")]
    rng = random.Random(seed)
    rng.shuffle(eligible)
    by_case: dict[str, dict[bool, dict]] = {}
    for row in eligible:
        by_case.setdefault(row["case_id"], {}).setdefault(bool(row["numeric_error"]), row)
    pool = [r for pair in by_case.values() if len(pair) == 2 for r in (pair[True], pair[False])]
    rng.shuffle(pool)
    return pool
