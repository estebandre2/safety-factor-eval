"""Match each wrong overturning value to a specific lever-arm mistake (within 2%); writes results/tables/overturning_error_mechanisms.csv."""
import json,collections
from pathlib import Path
from sfe.cases import load_cases
from sfe.physics import GAMMA_C, GAMMA_W
cases={c.id:c for c in load_cases(Path("data/cases.jsonl"))}
def fs(i, tri_wrong=False, up_wrong=False, no_uplift=False):
    h,d,bc,B,uf=i["height"],i["water_depth"],i["crest_width"],i["base_width"],i["uplift_factor"]
    wr=GAMMA_C*bc*h; wt=GAMMA_C*.5*(B-bc)*h
    at=(B-bc)/3 if tri_wrong else 2*(B-bc)/3
    H=GAMMA_W*d*d/2; U=uf*GAMMA_W*d*B/2
    au=B/3 if up_wrong else 2*B/3
    mo=H*d/3+(0 if no_uplift else U*au)
    return (wr*(B-bc/2)+wt*at)/mo
V={"uplift arm B/3 (too high)":dict(up_wrong=True),"triangle centroid (B-b)/3 from toe (too low)":dict(tri_wrong=True),
   "both":dict(tri_wrong=True,up_wrong=True),"uplift omitted":dict(no_uplift=True)}
rows=[json.loads(l) for f in ["results/graded/full_claude.jsonl","results/graded/full_deepseek.jsonl"] for l in open(f)]
out=collections.Counter(); tot=collections.Counter()
for r in rows:
    if r["family"]!="overturning" or not r["numeric_error"] or r["value_pred"] is None: continue
    c=cases[r["case_id"]]; v=r["value_pred"]; tot[r["model"]]+=1
    hits=[k for k,kw in V.items() if abs(v/fs(c.inputs,**kw)-1)<=0.02]
    lab=hits[0] if len(hits)==1 else ("ambiguous" if hits else "other")  # Study II §5: no first-match assignment
    out[(r["model"],lab)]+=1
lines=["model,mechanism,count,wrong_overturning_values"]+[f"{m},{lab},{n},{tot[m]}" for (m,lab),n in sorted(out.items())]
Path("results/tables/overturning_error_mechanisms.csv").write_text("\n".join(lines)+"\n")
print("\n".join(lines))
