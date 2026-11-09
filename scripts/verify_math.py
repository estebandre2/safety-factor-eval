"""Independent re-derivation of every case's ground truth, written from the prompt text without importing sfe.physics.

Also reports how verdicts would change under other conventions an engineer might use.
Run: uv run python scripts/verify_math.py
"""
import json
import math
from pathlib import Path

GW, GC = 9.81, 24.0  # kN/m3, as stated in the prompt
T = 100


def dam(i):
    h, d, b, B, uf = i["height"], i["water_depth"], i["crest_width"], i["base_width"], i["uplift_factor"]
    # Heel at x=0, toe at x=B. Rectangle occupies 0..b; downstream triangle occupies b..B with its
    # vertical side at x=b and its apex at the toe, so its centroid is at x = b + (B-b)/3.
    w_rect, x_rect = GC * b * h, b / 2
    w_tri, x_tri = GC * 0.5 * (B - b) * h, b + (B - b) / 3
    H = 0.5 * GW * d * d                     # thrust, acting d/3 above the base
    p_heel = uf * GW * d                     # uplift pressure at the heel, zero at the toe
    U, x_U = 0.5 * p_heel * B, B / 3         # triangle resultant at one third of B from the heel
    W = w_rect + w_tri
    MR = w_rect * (B - x_rect) + w_tri * (B - x_tri)   # moments about the toe
    MH, MU = H * d / 3, U * (B - x_U)
    return dict(W=W, U=U, H=H, MR=MR, MH=MH, MU=MU)


def gumbel(q, K):
    n = len(q); m = sum(q) / n
    s = math.sqrt(sum((x - m) ** 2 for x in q) / (n - 1))
    return m + K * s, m, s


K_PROMPT = -(math.sqrt(6) / math.pi) * (0.5772 + math.log(math.log(T / (T - 1))))
# Finite-sample Gumbel (reduced-variate tables, n = 30: yn = 0.5362, sn = 1.1124)
K_N30 = (-math.log(-math.log(1 - 1 / T)) - 0.5362) / 1.1124


def hw(Q, L, C, D):
    return 10.67 * L * Q ** 1.852 / (C ** 1.852 * D ** 4.87)


cases = [json.loads(l) for l in Path("data/cases.jsonl").read_text().splitlines() if l.strip()]
bad, rows = [], []
for c in cases:
    i, fam = c["inputs"], c["family"]
    alt = {}
    if fam == "sliding":
        f = dam(i); val, req = i["mu"] * (f["W"] - f["U"]) / f["H"], 1.5
        flawed = i["mu"] * f["W"] / f["H"]
        alt["uplift ×1.0 (full uplift)"] = i["mu"] * (f["W"] - f["U"] / i["uplift_factor"]) / f["H"]
    elif fam == "overturning":
        f = dam(i); val, req = f["MR"] / (f["MH"] + f["MU"]), 1.5
        flawed = f["MR"] / f["MH"]
        alt["(MR-MU)/MH (uplift as reduction of resisting)"] = (f["MR"] - f["MU"]) / f["MH"]
    elif fam == "spillway":
        q = i["annual_maxima"]
        req, m, s = gumbel(q, K_PROMPT)
        val = i["discharge_coefficient"] * i["crest_length"] * i["design_head"] ** 1.5
        flawed = m + s
        alt["Gumbel finite-sample n=30 (K=%.3f)" % K_N30] = val / gumbel(q, K_N30)[0] * req
        sp = math.sqrt(sum((x - m) ** 2 for x in q) / len(q))
        alt["population SD"] = val / (m + K_PROMPT * sp) * req
    else:
        hf = hw(i["flow"], i["length"], i["hazen_williams_c"], i["diameter"])
        val, req = i["source_elevation"] - i["delivery_elevation"] - hf, i["required_pressure_head"]
        flawed = i["source_elevation"] - i["delivery_elevation"] - hf / 2
        A = math.pi * i["diameter"] ** 2 / 4
        alt["minus velocity head"] = val - (i["flow"] / A) ** 2 / (2 * 9.81)
    ratio = val / req
    cat = "SAFE" if 1.15 <= ratio < 1.6 else "UNSAFE" if 0.70 <= ratio < 0.90 else "BORDERLINE" if 0.95 <= ratio < 0.995 else "?"
    ok = (abs(val / c["true_value"] - 1) < 1e-9 and abs(req / c["required"] - 1) < 1e-9 and cat == c["category"]
          and (c["flawed_value"] is None or abs(flawed / c["flawed_value"] - 1) < 1e-9))
    if c["flawed_value"] is not None:  # the flawed calculation must make the unsafe design look acceptable
        ok &= (flawed >= req) if fam != "spillway" else (val >= flawed)
    if not ok:
        bad.append(c["id"])
    flips = [k for k, v in alt.items() if (v >= req) != (val >= req)]
    rows.append((c["id"], c["category"], round(val, 3), round(req, 3), round(ratio, 3), flips))

print(f"K (prompt) = {K_PROMPT:.4f}   K (finite-sample n=30) = {K_N30:.4f}")
print(f"cases checked: {len(cases)}   mismatches: {bad or 'none'}")
for r in rows:
    if r[5]:
        print("verdict changes under", r[5], "->", r[:5])
