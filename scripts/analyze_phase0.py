"""Study II Phase 0 analysis (spec 2026-11-10): H1 class, H2 paired difference, effort decision, 0C lever arms."""
import json
from pathlib import Path

import pandas as pd

from sfe.analyze import _arm, effort_decision, error_ci, error_rate, h1_class, paired_case_diff

GRADED = Path("results/graded/phase0.jsonl")
OUT = Path("results/tables/phase0_summary.json")

df = pd.DataFrame([json.loads(l) for l in GRADED.read_text().splitlines() if l.strip()])
df.loc[df["model"].str.startswith("deepseek-") & df["effort"].isna(), "effort"] = "high"  # DeepSeek runs at "high"
done = df[df["status"] == "done"]
summary: dict = {"excluded": int((df["status"] != "done").sum()), "by_model": {}}
arms = {"0A": ("base", "max"), "0B": ("coords", "max"), "0C": ("bare", "max"), "0D": ("base", "high"),
        "0E-coords": ("coords", "high"), "0E-bare": ("bare", "high"),
        "0B-high (exploratory)": ("coords", "high"), "0C-high (exploratory)": ("bare", "high")}
for model, g in done.groupby("model"):
    m: dict = {}
    for label, (variant, effort) in arms.items():
        part = _arm(g, variant, effort)
        is_claude = model.startswith("claude-")
        if part.empty or ("exploratory" in label and not is_claude) or (label.startswith("0E") and is_claude):
            continue
        rate, n = error_rate(part)
        lo, hi = error_ci(part)
        m[label] = {"n": n, "error_rate": rate, "ci": [lo, hi], "unparseable": int(part["numeric_error"].isna().sum())}
        if variant == "bare":
            wrong = part["arms_wrong"].dropna()
            m[label]["arm_error_rate"] = {k: float(wrong.apply(lambda w: k in w).mean())
                                          for k in ("rectangle_arm_m", "triangle_arm_m", "uplift_arm_m", "thrust_arm_m")}
    if model.startswith("claude-"):
        m["H1"] = h1_class(_arm(g, "base", "max"))
        m["H2_coords_minus_base"] = paired_case_diff(g, ("coords", "max"), ("base", "max"))
    judged = g[g["value_pred"].notna() & g.get("value_rule", pd.Series(dtype=float)).notna()] if "value_rule" in g else g.iloc[:0]
    if len(judged):
        m["value_agreement"] = float(((judged["value_rule"] / judged["value_pred"] - 1).abs() <= 0.02).mean())
    summary["by_model"][model] = m
summary["phase1_effort"] = effort_decision(done[done["model"].str.startswith("claude-")])
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(summary, indent=2))
print(json.dumps(summary, indent=2))
