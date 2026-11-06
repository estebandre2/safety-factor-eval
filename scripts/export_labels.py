"""Blind judge-validation sample: 50 stratified answers plus 10 of the rare judge-labelled unsafe approvals."""
import csv
import json
import random
import sys
import tempfile
from pathlib import Path

from sfe.cases import load_cases
from sfe.grade import _delivered, _family, export_labeling_sample
from sfe.prompts import case_statement

GRADED = [Path("results/graded/full_claude.jsonl"), Path("results/graded/full_deepseek.jsonl")]
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "labels/judge_validation.csv")
STRATIFIED, APPROVALS, SEED = 50, 10, 7

rows = [json.loads(l) for p in GRADED for l in p.read_text().splitlines() if l.strip()]
with tempfile.TemporaryDirectory() as tmp:
    combined, base = Path(tmp) / "all.jsonl", Path(tmp) / "base.csv"
    combined.write_text("".join(json.dumps(r) + "\n" for r in rows))
    export_labeling_sample(combined, base, n=STRATIFIED, seed=SEED)
    with base.open() as fh:
        picked = list(csv.DictReader(fh))

cases = {c.id: c for c in load_cases(Path("data/cases.jsonl"))}
taken = {r["trial_id"] for r in picked}
approvals = [r for r in rows if r.get("source") == "judge" and r["verdict_truth"] == "UNSAFE"
             and r["verdict_pred"] == "APPROVE" and r["trial_id"] not in taken]
rng = random.Random(SEED)
for row in rng.sample(approvals, APPROVALS):
    picked.append({"trial_id": row["trial_id"], "model_family": _family(row["model"]),
                   "case_statement": case_statement(cases[row["case_id"]]), "answer": _delivered(row) or ""})
rng.shuffle(picked)  # position must not reveal which rows were oversampled

OUT.parent.mkdir(parents=True, exist_ok=True)
with OUT.open("w", newline="") as fh:
    writer = csv.writer(fh)
    writer.writerow(["sample_id", "trial_id", "model_family", "case_statement", "answer", "human_verdict"])
    for i, r in enumerate(picked, start=1):
        writer.writerow([i, r["trial_id"], r["model_family"], r["case_statement"], r["answer"], ""])
print(f"{len(picked)} rows -> {OUT}")
