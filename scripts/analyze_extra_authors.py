"""amendment 2026-11-10 (after Phase 2): extra providers as authors on the Phase 1 overturning cases
-> results/tables/phase1_extra_summary.json (error rate with case-bootstrap CI, verdicts, mechanism shares).
Compared descriptively with the pre-registered Phase 1 "high" arm; no new confirmatory test."""
import json
from pathlib import Path

import pandas as pd

from sfe.analyze import error_ci, error_rate
from sfe.analyze2 import attribute, mechanism_shares
from sfe.cases import load_cases

CASES = {c.id: c for c in load_cases(Path("data/cases_phase1.jsonl"))}
GRADED = Path("results/graded/phase1_extra.jsonl")
OUT = Path("results/tables/phase1_extra_summary.json")
PRICES = {"gemini-3-flash-preview": (0.50, 3.00), "gpt-oss-120b": (0.15, 0.60)}  # USD per 1M tokens, list price
RAW = Path("results/raw/phase1_extra.jsonl")

df = pd.DataFrame([json.loads(l) for l in GRADED.read_text().splitlines() if l.strip()])
df["mechanism"] = [attribute(CASES[c], v) for c, v in zip(df["case_id"], df["value_pred"])]
usage = {r["trial_id"]: r["usage"] for r in map(json.loads, RAW.read_text().splitlines())}
done = df[df["status"] == "done"]
summary: dict = {"excluded": int((df["status"] != "done").sum()), "authors": {}}
for model, g in done.groupby("model"):
    rate, n = error_rate(g)
    unsafe, safe = g[g["verdict_truth"] == "UNSAFE"], g[g["verdict_truth"] == "SAFE"]
    u = [usage[t] for t in g["trial_id"]]
    pin, pout = PRICES.get(model, (0.0, 0.0))
    summary["authors"][model] = {
        "n": n, "error_rate": rate, "ci": error_ci(g), "mechanisms": mechanism_shares(g, model),
        "unsafe_approvals": int((unsafe["verdict_pred"] == "APPROVE").sum()), "unsafe_n": len(unsafe),
        "false_rejections": int((safe["verdict_pred"] != "APPROVE").sum()), "safe_n": len(safe),
        "mean_output_tokens": sum(x["output_tokens"] for x in u) / len(u),
        "list_cost_usd": sum(x["input_tokens"] * pin + x["output_tokens"] * pout for x in u) / 1e6}
OUT.write_text(json.dumps(summary, indent=1))
print(json.dumps(summary, indent=1))
