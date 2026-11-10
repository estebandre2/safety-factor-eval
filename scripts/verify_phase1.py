"""Independent re-derivation of the Phase 1 gate and wall cases from the prompt text (spec 2026-11-10 §3).
Does not import sfe.physics or sfe.physics2. Overturning and sliding reuse Study I formulas already checked by
scripts/verify_math.py; they are re-checked here too."""
import json
from dataclasses import asdict

from sfe.cases2 import generate_phase1_cases

GW, GC = 9.81, 24.0
bad = []
cases = generate_phase1_cases()
for c in cases:
    i, text = c.inputs, c.assumptions
    if c.family == "gate":
        d, w = i["gate_height"], i["gate_width"]
        F = 0.5 * GW * d * d * w
        # resultant at d/3 above the bottom edge; read the hinge position from the prompt text
        arm = d / 3 if "hinged at its bottom edge" in text else 2 * d / 3
        value = F * arm / d
        ok_side = (i["latch_capacity"] >= value) == (c.verdict == "SAFE")
    elif c.family == "wall":
        H, B, b, ka, gs = i["wall_height"], i["base_width"], i["top_width"], i["ka"], i["gamma_s"]
        t = B - b
        front = "front face is battered" in text
        m_r = GC * b * H * ((t + b / 2) if front else b / 2) + GC * 0.5 * t * H * ((2 * t / 3) if front else (b + t / 3))
        value = m_r / (0.5 * ka * gs * H * H * H / 3)
        ok_side = (value >= 2.0) == (c.verdict == "SAFE")
    elif c.family == "overturning":
        h, d, bc, B, uf = i["height"], i["water_depth"], i["crest_width"], i["base_width"], i["uplift_factor"]
        mr = GC * bc * h * (B - bc / 2) + GC * 0.5 * (B - bc) * h * (2 * (B - bc) / 3)
        mo = 0.5 * GW * d * d * d / 3 + uf * GW * d * B / 2 * (2 * B / 3)
        value = mr / mo
        ok_side = (value >= 1.5) == (c.verdict == "SAFE")
    else:
        h, d, bc, B, uf, mu = (i[k] for k in ("height", "water_depth", "crest_width", "base_width", "uplift_factor", "mu"))
        W = GC * bc * h + GC * 0.5 * (B - bc) * h
        value = mu * (W - uf * GW * d * B / 2) / (0.5 * GW * d * d)
        ok_side = (value >= 1.5) == (c.verdict == "SAFE")
    if abs(value / c.true_value - 1) > 1e-9 or not ok_side:
        bad.append((c.id, value, c.true_value))
print(f"cases checked: {len(cases)}   mismatches: {bad or 'none'}")
