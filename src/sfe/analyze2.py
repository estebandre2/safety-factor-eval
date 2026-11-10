"""Study II Phase 1 analysis (spec 2026-11-10 §2 H3, H3b; amendment H7)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from sfe.analyze import BOOTSTRAP_DRAWS
from sfe.cases import Case
from sfe.cases2 import mechanism_values, orientation, pair_id

TOLERANCE = 0.02
H3_MIN_POINTS = 0.10
H7_MIN_POINTS = 0.15


def attribute(case: Case, value: float | None) -> str | None:
    """Mechanism whose value matches within 2%: a unique match, 'ambiguous', 'other', or None if correct/missing."""
    if value is None or abs(value / case.true_value - 1) <= TOLERANCE:
        return None
    hits = [k for k, v in mechanism_values(case).items() if abs(value / v - 1) <= TOLERANCE]
    return hits[0] if len(hits) == 1 else ("ambiguous" if hits else "other")


def _boot_mean(values: np.ndarray, seed: int = 0) -> tuple[float, float, float]:
    if len(values) == 0:
        return (float("nan"),) * 3
    idx = np.random.default_rng(seed).integers(0, len(values), size=(BOOTSTRAP_DRAWS, len(values)))
    draws = values[idx].mean(axis=1)
    return (float(values.mean()), float(np.quantile(draws, 0.025)), float(np.quantile(draws, 0.975)))


def _case_rates(df: pd.DataFrame) -> pd.Series:
    g = df[df["numeric_error"].notna()]
    return g.assign(e=g["numeric_error"].astype(bool)).groupby("case_id")["e"].mean()


def h3_paired(df: pd.DataFrame, family: str, cases: dict[str, Case] | None = None) -> tuple[float, float, float]:
    """Gate/wall: hard minus easy error rate, paired by geometry (pair_id); bootstrap over geometries."""
    from sfe.cases2 import generate_phase1_cases
    cases = cases or {c.id: c for c in generate_phase1_cases()}
    rates = _case_rates(df[df["family"] == family])
    pairs: dict[str, dict[str, float]] = {}
    for cid, r in rates.items():
        pairs.setdefault(pair_id(cases[cid]), {})[orientation(cases[cid])] = r
    diffs = np.array([p["hard"] - p["easy"] for p in pairs.values() if {"hard", "easy"} <= set(p)])
    return _boot_mean(diffs)


def h3_overturning(df: pd.DataFrame) -> tuple[float, float, float]:
    """Overturning: per case, share of answers with a hard-load mechanism minus share with an easy-load one."""
    g = df[(df["family"] == "overturning") & df["numeric_error"].notna()]
    hard = g["mechanism"].fillna("").str.contains(r"\(hard\)")
    easy = g["mechanism"].fillna("").str.contains(r"\(easy\)")
    per = pd.DataFrame({"case_id": g["case_id"], "d": hard.astype(float) - easy.astype(float)}).groupby("case_id")["d"].mean()
    return _boot_mean(per.to_numpy())


def h7_effort(df: pd.DataFrame, model: str, cases: dict[str, Case] | None = None) -> dict:
    """High-arm minus max-arm error rate for one model, paired by case; overall and per family/orientation."""
    from sfe.cases2 import generate_phase1_cases
    cases = cases or {c.id: c for c in generate_phase1_cases()}
    m = df[df["model"] == model]
    high, mx = _case_rates(m[m["effort"] == "high"]), _case_rates(m[m["effort"] == "max"])
    common = high.index.intersection(mx.index)
    diffs = (high[common] - mx[common])
    out: dict = {"all": _boot_mean(diffs.to_numpy())}
    groups: dict[str, list[float]] = {}
    for cid, d in diffs.items():
        c = cases[cid]
        groups.setdefault(f"{c.family}{'-' + orientation(c) if orientation(c) else ''}", []).append(d)
    out.update({k: _boot_mean(np.array(v)) for k, v in sorted(groups.items())})
    diff, lo, _ = out["all"]
    out["supported"] = bool(diff >= H7_MIN_POINTS and lo > 0)
    return out


def mechanism_shares(df: pd.DataFrame, model: str) -> dict[str, int]:
    labels = df[df["model"] == model]["mechanism"].dropna()
    return {k: int(v) for k, v in labels.value_counts().items()}
