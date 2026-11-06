"""Build result tables and figures from every graded results file."""
import json
from pathlib import Path

import pandas as pd

from sfe.analyze import attribution, contrasts, make_figures, primary, rates

if __name__ == "__main__":
    rows = [json.loads(l) for p in sorted(Path("results/graded").glob("*.jsonl")) for l in p.read_text().splitlines() if l.strip()]
    df = pd.DataFrame(rows)
    tables = Path("results/tables")
    tables.mkdir(parents=True, exist_ok=True)
    a = primary(df)                      # Mode A: single-turn pressure (primary analysis)
    b = df[df["mode"] == "B"]            # Mode B: neutral first turn, pressure as pushback (flip analysis)
    m0 = a[a["arm"] == "M0"]
    rates(m0, ["model", "condition"]).to_csv(tables / "m0_by_model_condition.csv", index=False)
    rates(m0, ["family", "category"]).to_csv(tables / "m0_by_family_category.csv", index=False)
    rates(b, ["model", "arm", "condition"]).to_csv(tables / "mode_b_flips.csv", index=False)
    rates(a[a["condition"] != "neutral"], ["model", "arm"]).to_csv(tables / "arms_under_pressure.csv", index=False)
    neutral_safe = a[(a["condition"] == "neutral") & (a["verdict_truth"] == "SAFE")]
    rates(neutral_safe, ["model", "arm"]).to_csv(tables / "false_rejection_by_arm_neutral.csv", index=False)
    attribution(m0, ["model"]).to_csv(tables / "attribution_m0.csv", index=False)
    contrasts(m0, "condition", "neutral", by="model").to_csv(tables / "contrasts_condition_by_model.csv", index=False)
    contrasts(a[a["condition"] != "neutral"], "arm", "M0", by="model").to_csv(tables / "contrasts_arm_by_model.csv", index=False)
    for path in make_figures(df, Path("results/figures")):
        print("figure", path)
    print("tables in", tables)
