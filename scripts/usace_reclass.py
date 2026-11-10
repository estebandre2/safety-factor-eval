"""Reclassify the dam cases under USACE EM 1110-2-2100 (Tables 3-2, 3-3, 3-5); also with the two observed lever-arm mistakes."""
import json, math
exec(open("scripts/verify_math.py").read().split("cases = ")[0])
cs=[json.loads(l) for l in open("data/cases.jsonl")]
def resultant(i, tri_wrong=False, up_wrong=False):
    h,d,b,B,uf=i["height"],i["water_depth"],i["crest_width"],i["base_width"],i["uplift_factor"]
    wr,wt=GC*b*h,GC*.5*(B-b)*h
    at=(B-b)/3 if tri_wrong else 2*(B-b)/3
    H=GW*d*d/2; U=uf*GW*d*B/2; au=B/3 if up_wrong else 2*B/3
    x=(wr*(B-b/2)+wt*at-H*d/3-U*au)/(wr+wt-U)   # distance of resultant from the toe
    comp=min(1.0,3*x/B) if x<B/3 else (1.0 if x<=2*B/3 else min(1.0,3*(B-x)/B))
    return x/B, comp
def usace(comp):  # Table 3-5: usual 100% compression
    return "OK" if comp>=0.999 else ("75%+" if comp>=0.75 else "FAIL")
print("OVERTURNING family: study label | study FS | resultant x/B from toe | % base in compression | USACE usual (Table 3-5) | with uplift arm B/3 | with triangle centroid wrong")
for c in cs:
    if c["family"]!="overturning": continue
    x,comp=resultant(c["inputs"]); xu,cu=resultant(c["inputs"],up_wrong=True); xt,ct=resultant(c["inputs"],tri_wrong=True)
    print(f'{c["id"]} {c["category"]:10} FS={c["true_value"]:.2f} x/B={x:.3f} comp={comp:.0%} {usace(comp):5} | upliftB/3 -> {cu:.0%} {usace(cu):5} | tri wrong -> {ct:.0%} {usace(ct)}')
print("\nSLIDING family: study FS vs USACE Table 3-2 (critical: usual 2.0 ordinary / 1.7 well-defined) and Table 3-3 (normal: 1.5 / 1.4); plus resultant location")
for c in cs:
    if c["family"]!="sliding": continue
    fs=c["true_value"]; x,comp=resultant(c["inputs"])
    print(f'{c["id"]} {c["category"]:10} FS={fs:.2f}  crit-ordinary(2.0):{"OK" if fs>=2.0 else "FAIL"} crit-welldef(1.7):{"OK" if fs>=1.7 else "FAIL"} normal-ordinary(1.5):{"OK" if fs>=1.5 else "FAIL"}  resultant comp={comp:.0%} {usace(comp)}')
