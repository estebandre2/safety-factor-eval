"""Study II Phase 2: review protocols, answer pool, scoring (spec 2026-11-10 §4 Phase 2 and amendment)."""
import json
from collections import Counter

from sfe.cases2 import generate_phase1_cases
from sfe.review import (PROTOCOLS, REVIEW_SCHEMA, build_pool, review_id, review_request, score_review)

CASES = {c.id: c for c in generate_phase1_cases()}
GATE = next(c for c in CASES.values() if c.family == "gate")


def test_review_request_is_structured_high_effort_and_hides_truth():
    for p in PROTOCOLS:
        req = review_request(GATE, "The latch reaction is 12.3 kN, so APPROVE.", p)
        text = req["messages"][0]["content"]
        assert req["structured"] and req["schema"] == REVIEW_SCHEMA and req["effort"] == "high"
        assert "12.3 kN" in text and GATE.criterion in text
        assert f"{GATE.true_value:.3g}" not in text
    assert "line of action" in review_request(GATE, "x", "P2")["messages"][0]["content"]
    assert "assumption" in review_request(GATE, "x", "P3")["messages"][0]["content"].lower()
    assert set(REVIEW_SCHEMA["required"]) == {"calculation", "reviewer_value", "design_verdict"}


def test_score_detection_and_false_alarm():
    wrong = {"numeric_error": True}
    right = {"numeric_error": False}
    out = json.dumps({"calculation": "INCORRECT", "reviewer_value": GATE.true_value, "design_verdict": "REJECT"})
    s = score_review(GATE, wrong, out)
    assert s["detected"] is True and s["false_alarm"] is None and s["value_correct"] is True
    s = score_review(GATE, right, out)
    assert s["false_alarm"] is True and s["detected"] is None
    assert score_review(GATE, wrong, "not json")["detected"] is None


def _graded_rows():
    rows = []
    for cid, c in CASES.items():
        if c.family not in ("overturning", "gate", "wall"):
            continue
        for m in ("claude-haiku-5-5", "claude-sonnet-5-5", "claude-opus-5-5"):
            for rep, err in enumerate((True, False, True)):
                rows.append({"trial_id": f"{cid}-{m}-{rep}", "case_id": cid, "family": c.family, "model": m,
                             "effort": "high", "status": "done", "numeric_error": err, "final_answer": "a"})
    return rows


def test_pool_is_balanced_capped_per_case_and_deterministic():
    pool = build_pool(_graded_rows(), size=300, seed=7)
    assert len(pool) == 300
    assert Counter(r["numeric_error"] for r in pool) == {True: 150, False: 150}
    assert max(Counter(r["case_id"] for r in pool).values()) <= 2
    assert [r["trial_id"] for r in pool] == [r["trial_id"] for r in build_pool(_graded_rows(), size=300, seed=7)]
    assert all(r["effort"] == "high" for r in pool)


def test_review_id_unique_per_reviewer_and_protocol():
    ids = {review_id("t1", m, p) for m in ("a", "b") for p in PROTOCOLS}
    assert len(ids) == 2 * len(PROTOCOLS)


def test_case_matched_pool_takes_one_wrong_and_one_correct_per_case():
    from sfe.review import build_matched_pool
    rows = _graded_rows()
    pool = build_matched_pool(rows, families=("overturning",), seed=7)
    by_case = {}
    for r in pool:
        by_case.setdefault(r["case_id"], []).append(r["numeric_error"])
    assert all(sorted(v) == [False, True] for v in by_case.values())
    assert {r["family"] for r in pool} == {"overturning"}
    assert len(pool) == 2 * len(by_case)
