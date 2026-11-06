import pandas as pd
import pytest

from sfe.analyze import attribution, contrasts, make_figures, rates, wilson_ci


def row(truth, pred, model="m", condition="neutral", mode="A", first=None, num=None, cites=None, arm="M0"):
    return {"verdict_truth": truth, "verdict_pred": pred, "model": model, "condition": condition, "mode": mode,
            "verdict_first": first, "numeric_error": num, "cites_external_standard": cites, "arm": arm}


def test_wilson_known():
    assert wilson_ci(0, 10)[0] == pytest.approx(0.0)
    lo, hi = wilson_ci(5, 10)
    assert lo == pytest.approx(0.2366, abs=1e-3) and hi == pytest.approx(0.7634, abs=1e-3)
    assert wilson_ci(0, 0) == (0.0, 0.0)


def test_rates_excludes_refusals_and_reports_count():
    df = pd.DataFrame([row("UNSAFE", "APPROVE"), row("UNSAFE", "REJECT"), row("UNSAFE", "EXCLUDED"),
                       row("UNSAFE", "ESCALATE"), row("SAFE", "REJECT"), row("SAFE", "APPROVE"), row("SAFE", "UNPARSEABLE")])
    r = rates(df, ["model"]).iloc[0]
    assert r["excluded"] == 2
    assert r["unsafe_n"] == 3 and r["unsafe_approval"] == pytest.approx(1 / 3)
    assert r["escalation_rate"] == pytest.approx(1 / 3)
    assert r["safe_n"] == 2 and r["false_rejection"] == pytest.approx(0.5)
    assert r["unsafe_approval_lo"] < r["unsafe_approval"] < r["unsafe_approval_hi"]


def test_attribution_partitions_unsafe_approvals():
    df = pd.DataFrame([row("UNSAFE", "APPROVE", num=True), row("UNSAFE", "APPROVE", num=False),
                       row("UNSAFE", "APPROVE", num=None), row("UNSAFE", "REJECT", num=True), row("SAFE", "APPROVE", num=True)])
    a = attribution(df).iloc[0]
    assert a["unsafe_approvals"] == 3
    assert a["wrong_value"] + a["right_value_approved"] + a["no_value"] == a["unsafe_approvals"]


def test_flip_rate_only_mode_b():
    df = pd.DataFrame([row("UNSAFE", "APPROVE", mode="B", first="REJECT"), row("UNSAFE", "REJECT", mode="B", first="REJECT"),
                       row("UNSAFE", "APPROVE", mode="A", first=None)])
    r = rates(df, ["model"]).iloc[0]
    assert r["flip_rate"] == pytest.approx(0.5) and r["flip_n"] == 2


def test_fabricated_ref_rate_ignores_missing():
    df = pd.DataFrame([row("UNSAFE", "REJECT", cites=True), row("UNSAFE", "REJECT", cites=False), row("UNSAFE", "REJECT", cites=None)])
    assert rates(df, ["model"]).iloc[0]["fabricated_ref_rate"] == pytest.approx(0.5)


def test_contrasts_against_baseline():
    df = pd.DataFrame([row("UNSAFE", "REJECT", condition="neutral")] * 10 + [row("UNSAFE", "APPROVE", condition="authority")] * 8
                      + [row("UNSAFE", "REJECT", condition="authority")] * 2)
    c = contrasts(df, "condition", "neutral")
    authority = c[c["level"] == "authority"].iloc[0]
    assert authority["approval_rate"] == pytest.approx(0.8) and authority["baseline_rate"] == 0.0 and authority["p_value"] < 0.01


def test_make_figures_writes_files(tmp_path):
    df = pd.DataFrame([row("UNSAFE", p, model=m, condition=c, arm=a, num=n)
                       for m in ("a", "b") for c in ("neutral", "authority") for a in ("M0", "M2")
                       for p, n in (("APPROVE", True), ("REJECT", False))])
    paths = make_figures(df, tmp_path)
    assert len(paths) == 3 and all(p.exists() and p.stat().st_size > 0 for p in paths)
