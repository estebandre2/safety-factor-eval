"""Study II Phase 2 analysis (spec 2026-11-10 H4-H6, Holm; amendment: cost-matched comparison)
-> results/tables/phase2_summary.json"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from sfe.analyze2 import _paired, _per_case_mean, holm, protocol_diff, review_rates, reviewer_diff

RAW = Path("results/raw/phase2.jsonl")
P1_GRADED, P1_RAW = Path("results/graded/phase1.jsonl"), Path("results/raw/phase1.jsonl")
OUT = Path("results/tables/phase2_summary.json")
CLAUDE = ["claude-haiku-5-5", "claude-sonnet-5-5", "claude-opus-5-5"]
DS = "deepseek-flash"
EXTRA = ["gemini-3-flash-preview", "gpt-oss-120b"]  # amendment 2026-11-10 (after Phase 2): own Holm family (H5x), pre-registered family unchanged

rv = pd.DataFrame([json.loads(l) for l in RAW.read_text().splitlines()])
rv["out_tokens"] = rv["usage"].apply(lambda u: u.get("output_tokens", 0))
done = rv[rv["status"] == "done"]
summary: dict = {"reviews": len(rv), "not_done": int((rv["status"] != "done").sum()),
                 "unparseable": int((done["detected"].isna() & done["false_alarm"].isna()).sum()),
                 "rates": {}, "contrasts": {}, "cost_matched": {}}

for (reviewer, protocol), g in done.groupby(["reviewer", "protocol"]):
    r = review_rates(g)
    r["value_correct_when_flagging_wrong"] = float(g[g["detected"] == True]["value_correct"].mean())  # noqa: E712
    r["mean_output_tokens"] = float(g["out_tokens"].mean())
    r["n"] = len(g)
    summary["rates"][f"{reviewer} | {protocol}"] = r

contrasts, pvals = {}, {}
for reviewer in CLAUDE + [DS]:
    for protocol in ("P2", "P3"):
        d = protocol_diff(done, reviewer, protocol)
        key = f"H4 {reviewer} {protocol}-P1"
        contrasts[key], pvals[key] = d, d["detection"][3]
for reviewer in CLAUDE:  # H5: DeepSeek Flash vs each Claude reviewer, P1, Claude-authored answers (all pool answers)
    d = reviewer_diff(done, DS, reviewer, "P1")
    key = f"H5 {DS} - {reviewer} (P1)"
    contrasts[key], pvals[key] = {"detection": d}, d[3]
opus_wrong = done[done["author"] == "claude-opus-5-5"]
h6 = _paired(_per_case_mean(opus_wrong[(opus_wrong["reviewer"] == "claude-haiku-5-5") & (opus_wrong["protocol"] == "P2")], "detected"),
             _per_case_mean(opus_wrong[(opus_wrong["reviewer"] == "claude-opus-5-5") & (opus_wrong["protocol"] == "P1")], "detected"))
contrasts["H6 Haiku-P2 minus Opus-P1 on Opus answers"] = {"detection": h6, "supported": bool(h6[1] > -0.05)}
pvals["H6 Haiku-P2 minus Opus-P1 on Opus answers"] = h6[3]
adj = holm({k: v for k, v in pvals.items() if not np.isnan(v)})
for k in contrasts:
    contrasts[k]["holm_p"] = adj.get(k)
summary["contrasts"] = contrasts

extra, extra_p = {}, {}
for other in EXTRA:
    if not (done["reviewer"] == other).any():
        continue
    for reviewer in CLAUDE:
        d = reviewer_diff(done, other, reviewer, "P1")
        key = f"H5x {other} - {reviewer} (P1)"
        extra[key], extra_p[key] = {"detection": d}, d[3]
adj_x = holm({k: v for k, v in extra_p.items() if not np.isnan(v)})
for k in extra:
    extra[k]["holm_p"] = adj_x.get(k)
summary["contrasts_extra"] = extra

# Cost-matched: author at "high" + one reviewer at "high", versus the author alone at "max" (overturning).
p1 = pd.DataFrame([json.loads(l) for l in P1_GRADED.read_text().splitlines()])
tokens = {json.loads(l)["trial_id"]: json.loads(l)["usage"]["output_tokens"] for l in P1_RAW.read_text().splitlines()}
p1["out_tokens"] = p1["trial_id"].map(tokens)
ovt = p1[(p1["family"] == "overturning") & p1["model"].isin(CLAUDE)]
for author in CLAUDE:
    hi, mx = ovt[(ovt["model"] == author) & (ovt["effort"] == "high")], ovt[(ovt["model"] == author) & (ovt["effort"] == "max")]
    e = float(hi["numeric_error"].astype(bool).mean())
    entry = {"author_high_error": e, "author_max_accuracy": float(1 - mx["numeric_error"].astype(bool).mean()),
             "author_high_tokens": float(hi["out_tokens"].mean()), "author_max_tokens": float(mx["out_tokens"].mean()),
             "pipelines": {}}
    mine = done[done["author"] == author]
    for (reviewer, protocol), g in mine.groupby(["reviewer", "protocol"]):
        w, c = g[g["answer_wrong"]], g[~g["answer_wrong"]]
        det = float(w["detected"].astype(bool).mean()) if len(w) else float("nan")
        fix = float((w["detected"].astype(bool) & (w["value_correct"] == True)).mean()) if len(w) else float("nan")  # noqa: E712
        fa = float(c["false_alarm"].astype(bool).mean()) if len(c) else float("nan")
        keep = float(1 - (c["false_alarm"].astype(bool) & (c["value_correct"] != True)).mean()) if len(c) else float("nan")  # noqa: E712
        entry["pipelines"][f"{reviewer} | {protocol}"] = {
            "expected_accuracy": (1 - e) * keep + e * fix, "detection": det, "false_alarm": fa,
            "tokens_author_plus_review": entry["author_high_tokens"] + float(g["out_tokens"].mean()), "n": len(g)}
    summary["cost_matched"][author] = entry

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(summary, indent=2, default=str))
print(json.dumps({k: summary[k] for k in ("reviews", "not_done", "unparseable")}, indent=1))
