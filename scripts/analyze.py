"""Build result tables and figures from every graded results file."""
import json
from pathlib import Path

import pandas as pd

from sfe.analyze import attribution, contrasts, make_figures, rates

if __name__ == "__main__":
    rows = [json.loads(l) for p in sorted(Path("results/graded").glob("*.jsonl")) for l in p.read_text().splitlines() if l.strip()]
    df = pd.DataFrame(rows)
    tables = Path("results/tables")
    tables.mkdir(parents=True, exist_ok=True)
    m0 = df[df["arm"] == "M0"]
    rates(m0, ["model", "condition"]).to_csv(tables / "m0_by_model_condition.csv", index=False)
    rates(m0, ["model", "mode"]).to_csv(tables / "m0_by_model_mode.csv", index=False)
    rates(m0, ["family", "category"]).to_csv(tables / "m0_by_family_category.csv", index=False)
    rates(df[df["condition"] != "neutral"], ["model", "arm"]).to_csv(tables / "arms_under_pressure.csv", index=False)
    rates(df[df["verdict_truth"] == "SAFE"], ["model", "arm"]).to_csv(tables / "false_rejection_by_arm.csv", index=False)
    attribution(m0, ["model"]).to_csv(tables / "attribution_m0.csv", index=False)
    contrasts(m0, "condition", "neutral").to_csv(tables / "contrasts_condition.csv", index=False)
    contrasts(df[df["condition"] != "neutral"], "arm", "M0").to_csv(tables / "contrasts_arm.csv", index=False)
    for path in make_figures(df, Path("results/figures")):
        print("figure", path)
    print("tables in", tables)
