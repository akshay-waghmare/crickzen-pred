import warnings; warnings.filterwarnings("ignore")
import sys
from pathlib import Path

sys.path.insert(0, "src")
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd

from ipl_v13_mid_split_common import (
    build_mid_split_analysis,
    load_training_data,
    load_v12_features,
)

pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 20)
pd.set_option("display.max_rows", 200)


def fmt_df(df: pd.DataFrame, cols: list[str], title: str, decimals: int = 4):
    print(f"\n{title}")
    print("-" * len(title))
    show = df[cols].copy()
    numeric_cols = show.select_dtypes(include="number").columns
    show[numeric_cols] = show[numeric_cols].astype(float).round(decimals)
    print(show.to_string(index=False))


def fmt_list(title: str, values: list[str]):
    print(f"\n{title} ({len(values)})")
    print("-" * (len(title) + len(str(len(values))) + 3))
    print(", ".join(values) if values else "None")


def main():
    print("Loading IPL inn2 data for MID split EDA...")
    df = load_training_data()
    v12_feats = load_v12_features()
    mid_features = v12_feats["mid"]
    analysis = build_mid_split_analysis(df, mid_features)

    print(f"  Total inn2 rows: {len(df):,}")
    print(f"  MID features in v12: {len(mid_features)}")
    print(f"  Early MID rows (7-11): {len(analysis['early_df']):,}")
    print(f"  Late MID rows  (12-15): {len(analysis['late_df']):,}")
    print(f"  MID rows total (7-15): {len(analysis['mid_df']):,}")

    fmt_df(
        analysis["importance_early"].head(20),
        ["feature", "gain_early"],
        "Top 20 XGBoost gain features — Early MID (7-11)",
    )
    fmt_df(
        analysis["importance_late"].head(20),
        ["feature", "gain_late"],
        "Top 20 XGBoost gain features — Late MID (12-15)",
    )

    fmt_list("Important only in EARLY top-20", analysis["only_early"])
    fmt_list("Important only in LATE top-20", analysis["only_late"])
    fmt_list("Shared across both top-20 lists", analysis["shared_top20"])

    top30 = analysis["top30_stats"].copy()
    top30["corr_drift"] = (top30["corr_early"] - top30["corr_late"]).abs()
    fmt_df(
        top30,
        [
            "feature",
            "gain_early",
            "gain_late",
            "mean_early",
            "std_early",
            "corr_early",
            "mean_late",
            "std_late",
            "corr_late",
            "corr_drift",
        ],
        "Top 30 current MID features — stats and correlation drift",
    )

    pred_df = analysis["prediction_comparison"].copy()
    fmt_df(
        pred_df,
        ["phase", "model_scope", "n", "mean_pred", "std_pred", "pct_45_55", "pct_extreme", "brier"],
        "Prediction distribution + OOF Brier (shared MID vs split models)",
    )

    candidate_df = analysis["candidate_summary"].copy()
    fmt_df(
        candidate_df.sort_values(["abs_diff", "abs_corr_early"], ascending=[False, False]),
        ["feature", "corr_early", "corr_late", "abs_diff", "verdict"],
        "Candidate feature summary",
    )

    fmt_list("Recommended removals from EARLY MID", analysis["recommended_removals"]["early_mid"])
    fmt_list("Recommended removals from LATE MID", analysis["recommended_removals"]["late_mid"])
    fmt_list("Top features to ADD to EARLY MID", analysis["recommended_additions"]["early_mid"])
    fmt_list("Top features to ADD to LATE MID", analysis["recommended_additions"]["late_mid"])

    print("\nEDA complete.")


if __name__ == "__main__":
    main()
