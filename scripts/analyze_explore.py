"""Exploratory E1-E3 (amendment 2026-11-10 night) -> results/tables/explore_summary.json.
E1: overturning error rate by effort (low, medium from explore; high, max from Phase 1), medium minus high paired.
E2: set-up-first prompt at "high" minus base prompt at "high", paired by case; threshold >= 10 points, CI > 0.
E3: dams without uplift at "high" against the same geometries in Phase 1 (paired by geometry).
E5: apex sentence at "high" against the base prompt at "high" (error and triangle-centroid share, paired by case).
E6: set-up-first at "low" and "medium" against the base prompt at the same effort (paired by case)."""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from sfe.analyze import error_ci, error_rate, paired_case_diff
from sfe.analyze2 import _boot_mean, attribute, mechanism_shares
from sfe.cases import load_cases

CASES = {c.id: c for c in load_cases(Path("data/cases_phase1.jsonl"))}
CASES |= {c.id: c for c in load_cases(Path("data/cases_explore_nouplift.jsonl"))}
CASES |= {c.id: c for c in load_cases(Path("data/cases_explore_holdout.jsonl"))}
CLAUDE = ["claude-haiku-5-5", "claude-sonnet-5-5", "claude-opus-5-5"]
OUT = Path("results/tables/explore_summary.json")


def load(path: str) -> pd.DataFrame:
    p = Path(path)
    return pd.DataFrame([json.loads(l) for l in p.read_text().splitlines() if l.strip()]) if p.exists() else pd.DataFrame()


p1 = load("results/graded/phase1.jsonl")
p1 = p1[(p1["family"] == "overturning") & p1["model"].isin(CLAUDE)]
ex, nu = load("results/graded/explore.jsonl"), load("results/graded/explore_nouplift.jsonl")
ex2 = load("results/graded/explore2.jsonl")
df = pd.concat([p1, ex, ex2], ignore_index=True)
df = df[df["status"] == "done"]
df["mechanism"] = [attribute(CASES[c], v) for c, v in zip(df["case_id"], df["value_pred"])]
summary: dict = {"excluded": {"explore": int((ex["status"] != "done").sum()) if len(ex) else None,
                              "nouplift": int((nu["status"] != "done").sum()) if len(nu) else None},
                 "E1": {}, "E2": {}, "E3": {}, "E5": {}, "E6": {}}

for model in CLAUDE:
    m = df[df["model"] == model]
    e1 = {}
    for effort in ("low", "medium", "high", "max"):
        g = m[(m["effort"] == effort) & (m["variant"] == "base")]
        if len(g):
            rate, n = error_rate(g)
            e1[effort] = {"n": n, "rate": rate, "ci": error_ci(g),
                          "unsafe_approvals": int(((g["verdict_truth"] == "UNSAFE") & (g["verdict_pred"] == "APPROVE")).sum())}
    if {"medium", "high"} <= set(e1):
        e1["medium_minus_high"] = paired_case_diff(m, ("base", "medium"), ("base", "high"))
    summary["E1"][model] = e1
    s = m[(m["effort"] == "high") & (m["variant"] == "setup")]
    if len(s):
        rate, n = error_rate(s)
        d = paired_case_diff(m, ("setup", "high"), ("base", "high"))
        summary["E2"][model] = {"n": n, "rate": rate, "ci": error_ci(s), "setup_minus_base": d,
                                "meets_threshold": bool(d[0] <= -0.10 and d[2] < 0),
                                "mechanisms": mechanism_shares(s, model)}

def tri_share(g: pd.DataFrame) -> pd.Series:
    return g.assign(t=g["mechanism"].fillna("").str.contains("triangle").astype(float)).groupby("case_id")["t"].mean()


for model in CLAUDE:
    m = df[df["model"] == model]
    a = m[(m["effort"] == "high") & (m["variant"] == "apex")]
    if len(a):
        b = m[(m["effort"] == "high") & (m["variant"] == "base")]
        rate, n = error_rate(a)
        common = tri_share(a).index.intersection(tri_share(b).index)
        summary["E5"][model] = {"n": n, "rate": rate, "ci": error_ci(a), "mechanisms": mechanism_shares(a, model),
                                "apex_minus_base": paired_case_diff(m, ("apex", "high"), ("base", "high")),
                                "triangle_share_diff": _boot_mean((tri_share(a)[common] - tri_share(b)[common]).to_numpy())}
    e6 = {}
    for effort in ("low", "medium"):
        s6 = m[(m["effort"] == effort) & (m["variant"] == "setup")]
        if len(s6):
            rate, n = error_rate(s6)
            d = paired_case_diff(m, ("setup", effort), ("base", effort))
            e6[effort] = {"n": n, "rate": rate, "ci": error_ci(s6), "setup_minus_base": d,
                          "meets_threshold": bool(d[0] <= -0.10 and d[2] < 0), "mechanisms": mechanism_shares(s6, model)}
    if e6:
        summary["E6"][model] = e6

if len(nu):
    nu = nu[nu["status"] == "done"].copy()
    nu["mechanism"] = [attribute(CASES[c], v) for c, v in zip(nu["case_id"], nu["value_pred"])]
    nu["geo"] = nu["case_id"].str.replace("s2-nouplift-", "s2-overturning-", regex=False)
    base = df[(df["effort"] == "high") & (df["variant"] == "base")].copy()
    base["geo"] = base["case_id"]
    for model in CLAUDE:
        a, b = nu[nu["model"] == model], base[base["model"] == model]
        if not len(a):
            continue
        rate, n = error_rate(a)
        tri = lambda g: g.assign(t=g["mechanism"].fillna("").str.contains("triangle").astype(float)).groupby("geo")["t"].mean()
        err = lambda g: g.assign(e=g["numeric_error"].astype(float)).groupby("geo")["e"].mean()
        common = err(a).index.intersection(err(b).index)
        summary["E3"][model] = {
            "n": n, "rate": rate, "ci": error_ci(a), "mechanisms": mechanism_shares(a, model),
            "nouplift_minus_phase1_error": _boot_mean((err(a)[common] - err(b)[common]).to_numpy()),
            "nouplift_minus_phase1_triangle": _boot_mean((tri(a)[common] - tri(b)[common]).to_numpy())}

# E7: set-up-first on gpt-oss-120b (1 repeat) against its base answers (2 repeats), paired by case.
oss, oss_base = load("results/graded/explore_oss.jsonl"), load("results/graded/phase1_extra.jsonl")
if len(oss):
    summary["E7"] = {"excluded": int((oss["status"] != "done").sum())}
    oss = oss[oss["status"] == "done"].copy()
    oss_base = oss_base[(oss_base["status"] == "done") & (oss_base["model"] == "gpt-oss-120b")]
    oss["mechanism"] = [attribute(CASES[c], v) for c, v in zip(oss["case_id"], oss["value_pred"])]
    per_case = lambda g: g.assign(e=g["numeric_error"].astype(float)).groupby("case_id")["e"].mean()
    common = per_case(oss).index.intersection(per_case(oss_base).index)
    rate, n = error_rate(oss)
    summary["E7"].update({"n": n, "rate": rate, "ci": error_ci(oss), "base_rate": error_rate(oss_base)[0],
                          "setup_minus_base": _boot_mean((per_case(oss)[common] - per_case(oss_base)[common]).to_numpy()),
                          "mechanisms": mechanism_shares(oss, "gpt-oss-120b")})

# Round 3: held-out dams, predictions R1-R4 fixed before the run; R5 side effects on gate, wall, sliding.
r3, side = load("results/graded/explore3.jsonl"), load("results/graded/explore3_side.jsonl")
if len(r3):
    summary["R"] = {"excluded": int((r3["status"] != "done").sum())}
    r3 = r3[r3["status"] == "done"].copy()
    r3["mechanism"] = [attribute(CASES[c], v) for c, v in zip(r3["case_id"], r3["value_pred"])]
    for model in CLAUDE:
        m = r3[r3["model"] == model]
        arms = {}
        for effort, variant in (("high", "base"), ("high", "setup"), ("high", "apex"), ("high", "placebo"),
                                ("low", "base"), ("low", "setup")):
            g = m[(m["effort"] == effort) & (m["variant"] == variant)]
            if len(g):
                rate, n = error_rate(g)
                arms[f"{effort}-{variant}"] = {
                    "n": n, "rate": rate, "ci": error_ci(g), "mechanisms": mechanism_shares(g, model),
                    "unsafe_approvals": int(((g["verdict_truth"] == "UNSAFE") & (g["verdict_pred"] == "APPROVE")).sum()),
                    "safe_not_approved": int(((g["verdict_truth"] == "SAFE") & (g["verdict_pred"] != "APPROVE")).sum())}
        d1 = paired_case_diff(m, ("setup", "high"), ("base", "high"))
        d2 = paired_case_diff(m, ("setup", "low"), ("base", "low"))
        d3 = paired_case_diff(m, ("placebo", "high"), ("base", "high"))
        d4 = paired_case_diff(m, ("apex", "high"), ("base", "high"))
        a, b = m[(m["effort"] == "high") & (m["variant"] == "apex")], m[(m["effort"] == "high") & (m["variant"] == "base")]
        common = tri_share(a).index.intersection(tri_share(b).index)
        summary["R"][model] = {
            "arms": arms,
            "R1_setup_minus_base_high": d1, "R1_met": bool(d1[0] <= -0.10 and d1[2] < 0),
            "R2_setup_minus_base_low": d2, "R2_met": bool(d2[0] <= -0.10 and d2[2] < 0),
            "R3_placebo_minus_base_high": d3, "R3_met": bool(not (d3[0] <= -0.10 and d3[2] < 0)),
            "R4_apex_minus_base_high": d4,
            "R4_triangle_share_diff": _boot_mean((tri_share(a)[common] - tri_share(b)[common]).to_numpy())}
if len(side):
    side = side[side["status"] == "done"]
    base = load("results/graded/phase1.jsonl")
    base = base[(base["status"] == "done") & (base["effort"] == "high") & base["family"].isin(["gate", "wall", "sliding"])]
    out = {}
    for (model, fam), g in side.groupby(["model", "family"]):
        b = base[(base["model"] == model) & (base["family"] == fam)]
        snap = lambda x: float(((x["verdict_truth"] == "SAFE") & (x["verdict_pred"] != "APPROVE")).sum() /
                               max((x["verdict_truth"] == "SAFE").sum(), 1))
        out[f"{model} | {fam}"] = {"setup_error": error_rate(g)[0], "base_error": error_rate(b)[0],
                                   "setup_safe_not_approved": snap(g), "base_safe_not_approved": snap(b), "n": len(g)}
    summary["R5"] = out

# Round 4: the placebo split (steps, care, filler) on the held-out dams, against the round 3 base arm.
r4 = load("results/graded/explore4.jsonl")
if len(r4) and len(r3):
    summary["R4split"] = {"excluded": int((r4["status"] != "done").sum())}
    both = pd.concat([r3, r4[r4["status"] == "done"]], ignore_index=True)
    for model in CLAUDE:
        m = both[both["model"] == model]
        row = {}
        for v in ("steps", "care", "filler"):
            g = m[(m["effort"] == "high") & (m["variant"] == v)]
            rate, n = error_rate(g)
            d = paired_case_diff(m, (v, "high"), ("base", "high"))
            row[v] = {"n": n, "rate": rate, "ci": error_ci(g), "minus_base": d,
                      "reaches_minus_10": bool(d[0] <= -0.10 and d[2] < 0),
                      "unsafe_approvals": int(((g["verdict_truth"] == "UNSAFE") & (g["verdict_pred"] == "APPROVE")).sum())}
        row["F1_met"] = not row["filler"]["reaches_minus_10"]
        row["F2_met_opus"] = (row["steps"]["reaches_minus_10"] or row["care"]["reaches_minus_10"]) if "opus" in model else None
        summary["R4split"][model] = row

OUT.write_text(json.dumps(summary, indent=1, default=float))
print(json.dumps(summary, indent=1, default=float))
