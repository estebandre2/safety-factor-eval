"""Study II Phase 1 analysis (spec 2026-11-10: H3, H3b, H7, sliding control) -> results/tables/phase1_summary.json."""
import json
from pathlib import Path

import pandas as pd

from sfe.analyze import error_ci, error_rate
from sfe.analyze2 import attribute, h3_overturning, h3_paired, h7_effort, mechanism_shares
from sfe.cases import load_cases

CASES = {c.id: c for c in load_cases(Path("data/cases_phase1.jsonl"))}
GRADED = Path("results/graded/phase1.jsonl")
OUT = Path("results/tables/phase1_summary.json")

df = pd.DataFrame([json.loads(l) for l in GRADED.read_text().splitlines() if l.strip()])
df.loc[df["model"].str.startswith("deepseek-") & df["effort"].isna(), "effort"] = "high"
df["mechanism"] = [attribute(CASES[c], v) if f != "sliding" else None
                   for c, v, f in zip(df["case_id"], df["value_pred"], df["family"])]
done = df[df["status"] == "done"]
summary: dict = {"excluded": int((df["status"] != "done").sum()), "error_rates": {}, "H3": {}, "H3b": {}, "H7": {},
                 "verdicts": {}}

for (model, effort, family), g in done.groupby(["model", "effort", "family"]):
    rate, n = error_rate(g)
    summary["error_rates"][f"{model} | {effort} | {family}"] = {"n": n, "rate": rate, "ci": error_ci(g)}
    unsafe, safe = g[g["verdict_truth"] == "UNSAFE"], g[g["verdict_truth"] == "SAFE"]
    summary["verdicts"][f"{model} | {effort} | {family}"] = {
        "unsafe_approvals": int((unsafe["verdict_pred"] == "APPROVE").sum()), "unsafe_n": len(unsafe),
        "false_rejections": int((safe["verdict_pred"] != "APPROVE").sum()), "safe_n": len(safe)}

high = done[done["effort"] == "high"]
for model, g in high.groupby("model"):
    summary["H3"][model] = {"overturning (hard minus easy load)": h3_overturning(g),
                            "gate (hard minus easy)": h3_paired(g, "gate", CASES),
                            "wall (hard minus easy)": h3_paired(g, "wall", CASES)}
    summary["H3b"][model] = mechanism_shares(g[g["family"] == "overturning"], model)
for model in sorted(done[done["model"].str.startswith("claude-")]["model"].unique()):
    summary["H7"][model] = h7_effort(done, model, CASES)

fs = done[done["family"].isin(["overturning", "wall", "sliding"]) & done["value_pred"].notna() & done["value_rule"].notna()]
summary["value_agreement_fs"] = {"n": len(fs), "share": float(((fs["value_rule"] / fs["value_pred"] - 1).abs() <= 0.02).mean())}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(summary, indent=2, default=str))
print(json.dumps({k: summary[k] for k in ("excluded", "H3", "H7", "value_agreement_fs")}, indent=1, default=str))
