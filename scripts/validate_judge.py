"""Validate the judge without human labels (spec §7 amendment, 2026-11-10).

1. A model-free reader (sfe.grade.rule_verdict) against every judge label.
2. Blind labels from a second model on the 60-answer sample (labels/prelim_model_labels.csv).
Writes results/tables/judge_validation.csv and results/tables/judge_disagreements.csv.
"""
import csv
import json
from collections import Counter
from pathlib import Path

from sfe.grade import _delivered, _family, cohen_kappa, rule_verdict

GRADED = [Path("results/graded/full_claude.jsonl"), Path("results/graded/full_deepseek.jsonl")]
TABLES = Path("results/tables")

rows = [json.loads(l) for p in GRADED for l in p.read_text().splitlines() if l.strip()]
judged = [r for r in rows if r.get("source") == "judge"]
pairs = [(r, rule_verdict(_delivered(r))) for r in judged]
read = [(r, v) for r, v in pairs if v is not None]


def stats(name: str, subset: list) -> dict:
    a, b = [v for _, v in subset], [r["verdict_pred"] for r, _ in subset]
    return {"comparison": name, "n": len(subset), "agree": sum(x == y for x, y in zip(a, b)),
            "accuracy": round(sum(x == y for x, y in zip(a, b)) / len(subset), 4), "kappa": round(cohen_kappa(a, b), 4)}


summary = [stats("rule reader vs judge, all", read)]
for fam in ("claude", "other"):
    summary.append(stats(f"rule reader vs judge, {fam} answers", [(r, v) for r, v in read if _family(r["model"]) == fam]))

labels = {x["trial_id"]: x["label"].strip().upper() for x in csv.DictReader(Path("labels/prelim_model_labels.csv").open())}
by_id = {r["trial_id"]: r for r in rows}
summary.append(stats("second-model blind labels vs judge (60 sample)", [(by_id[t], v) for t, v in labels.items()]))

with (TABLES / "judge_validation.csv").open("w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(summary[0]))
    w.writeheader(); w.writerows(summary)

disagree = [(r, v) for r, v in read if v != r["verdict_pred"]]
with (TABLES / "judge_disagreements.csv").open("w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["trial_id", "model", "arm", "case_id", "verdict_truth", "rule", "judge"])
    for r, v in disagree:
        w.writerow([r["trial_id"], r["model"], r["arm"], r["case_id"], r["verdict_truth"], v, r["verdict_pred"]])

unsafe_appr = [r for r in rows if r["verdict_truth"] == "UNSAFE" and r["verdict_pred"] == "APPROVE"]
for s in summary:
    print(s)
print("rule reader abstained on", len(judged) - len(read), "of", len(judged))
print("disagreement types (rule, judge):", dict(Counter((v, r["verdict_pred"]) for r, v in disagree)))
print("unsafe approvals confirmed by the rule reader:", sum(rule_verdict(_delivered(r)) == "APPROVE" for r in unsafe_appr), "of", len(unsafe_appr))
m4 = [r for r in unsafe_appr if r["arm"] == "M4"]
print("M4 unsafe approvals:", len(m4), "first answer verdict (rule reader):",
      dict(Counter(rule_verdict(r.get("first_answer")) for r in m4)))
