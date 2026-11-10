"""Study II Phase 1 analysis: orientation (H3), mechanisms (H3b), effort generalization (H7)."""
import pandas as pd

from sfe.analyze2 import attribute, h3_paired, h7_effort, mechanism_shares
from sfe.cases2 import generate_phase1_cases, mechanism_values, orientation, pair_id

CASES = {c.id: c for c in generate_phase1_cases()}
GATES = [c for c in CASES.values() if c.family == "gate"]


def test_attribute_unique_ambiguous_other():
    c = next(c for c in CASES.values() if c.family == "overturning")
    up = mechanism_values(c)["uplift_arm (hard)"]
    assert attribute(c, up) == "uplift_arm (hard)"
    assert attribute(c, c.true_value) is None  # correct value: no mechanism
    assert attribute(c, c.true_value * 3) == "other"


def _rows(spec):
    return pd.DataFrame([{"case_id": cid, "family": CASES[cid].family, "model": m, "effort": e,
                          "numeric_error": err} for cid, m, e, err in spec])


def test_h3_paired_by_geometry():
    spec = []
    for c in GATES:
        hard = orientation(c) == "hard"
        spec += [(c.id, "m", "high", hard), (c.id, "m", "high", hard)]
    diff, lo, hi = h3_paired(_rows(spec), "gate")
    assert diff == 1.0 and lo == 1.0 and hi == 1.0


def test_h7_high_minus_max_by_case():
    spec = []
    for c in GATES:
        spec += [(c.id, "m", "high", True), (c.id, "m", "max", False)]
    out = h7_effort(_rows(spec), "m")
    assert out["all"][0] == 1.0 and out["supported"] is True


def test_mechanism_shares_counts_labels():
    df = pd.DataFrame({"model": ["m", "m", "m"], "mechanism": ["uplift_arm (hard)", "uplift_arm (hard)", "other"]})
    assert mechanism_shares(df, "m") == {"uplift_arm (hard)": 2, "other": 1}
