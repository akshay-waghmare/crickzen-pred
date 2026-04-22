"""
PSL Model vs Market Analysis
=============================
Compare our PSL ML model predictions against live market odds captured
in recorded match states (data/match_states/psl/).

Unlike the IPL analysis (which parses raw betx21 data), this script uses
pre-recorded match states that already contain both model probabilities
AND market odds in a unified schema.

Usage:
    python scripts/analyze_psl_model_vs_market.py

Outputs:
    data/psl_model_vs_market.parquet       — Full ball-by-ball data
    data/psl_model_vs_market_summary.csv   — Per-phase/innings summary
    data/psl_model_vs_market_report.md     — Findings + recommendations
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, log_loss

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

STATES_DIR = ROOT / "data" / "match_states" / "psl"
OUTPUT_DIR = ROOT / "data"


# ---------------------------------------------------------------------------
# Load & validate
# ---------------------------------------------------------------------------

def load_match_states() -> pd.DataFrame:
    """Load all PSL match state parquet files from the states directory."""
    files = sorted(STATES_DIR.glob("*.parquet"))
    if not files:
        raise FileNotFoundError(f"No parquet files found in {STATES_DIR}")

    dfs = []
    for f in files:
        df = pd.read_parquet(f)
        df["source_file"] = f.stem
        dfs.append(df)

    df = pd.concat(dfs, ignore_index=True)
    print(f"Loaded {len(df):,} ball states from {len(files)} file(s)")
    print(f"  Columns: {len(df.columns)}")
    print(f"  Innings: {df['innings'].value_counts().to_dict()}")
    print(f"  Matches: {df['match_id'].nunique() if 'match_id' in df.columns else 'N/A'}")
    return df


def validate_and_clean(df: pd.DataFrame) -> pd.DataFrame:
    """Drop rows with missing market or model data, add derived columns."""
    n0 = len(df)

    # Drop rows where market data is missing
    df = df.dropna(subset=["market_batting_team_prob", "market_bowling_team_prob"])
    df = df[df["market_batting_team_prob"].between(0.01, 0.99)]

    # Drop rows where model prob is missing
    model_cols = [c for c in ["model_final_prob", "model_calibrated_per_over", "model_calibrated_phase"] if c in df.columns]
    if not model_cols:
        raise ValueError("No model probability columns found in match states")

    primary_model_col = model_cols[0]  # model_final_prob preferred
    df = df.dropna(subset=[primary_model_col])
    df[primary_model_col] = df[primary_model_col].clip(0.01, 0.99)

    print(f"After cleaning: {len(df):,} rows (dropped {n0 - len(df):,})")

    # Align: model_prob is batting team's win probability
    df["model_prob"] = df[primary_model_col]
    df["market_prob"] = df["market_batting_team_prob"].clip(0.01, 0.99)

    # Deviation
    df["deviation"] = df["model_prob"] - df["market_prob"]
    df["deviation_abs"] = df["deviation"].abs()

    # Phase label
    if "match_phase" in df.columns:
        df["phase"] = df["match_phase"]
    else:
        df["phase"] = "unknown"

    return df


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def compute_metrics(y_true: pd.Series, y_pred: pd.Series, label: str) -> dict:
    """Compute Brier, ECE, LogLoss for a probability column."""
    y_true = y_true.values.astype(float)
    y_pred = y_pred.clip(0.001, 0.999).values.astype(float)

    brier = brier_score_loss(y_true, y_pred)
    ll = log_loss(y_true, y_pred)

    # ECE: 10 equal-width bins
    bins = np.linspace(0, 1, 11)
    ece = 0.0
    n = len(y_true)
    for i in range(len(bins) - 1):
        mask = (y_pred >= bins[i]) & (y_pred < bins[i + 1])
        if mask.sum() == 0:
            continue
        frac_pos = y_true[mask].mean()
        mean_pred = y_pred[mask].mean()
        ece += mask.sum() / n * abs(frac_pos - mean_pred)

    return {"label": label, "n": n, "brier": round(brier, 4), "ece": round(ece, 4), "logloss": round(ll, 4)}


def segment_analysis(df: pd.DataFrame) -> pd.DataFrame:
    """Run metrics across multiple segments."""
    rows = []

    # Available outcome column
    outcome_col = None
    for c in ["is_winner", "batting_team_won"]:
        if c in df.columns and df[c].notna().sum() > 50:
            outcome_col = c
            break

    if outcome_col is None:
        print("  ⚠ No outcome column found — skipping Brier/ECE analysis")
        return pd.DataFrame()

    y = df[outcome_col].astype(float)

    model_cols_to_test = {}
    for alias, col in [
        ("model_final", "model_final_prob"),
        ("model_per_over", "model_calibrated_per_over"),
        ("model_phase", "model_calibrated_phase"),
        ("model_combined", "model_calibrated_combined"),
        ("model_raw", "model_raw_prob"),
        ("market", "market_prob"),
    ]:
        if col in df.columns:
            model_cols_to_test[alias] = col

    # Overall
    for alias, col in model_cols_to_test.items():
        rows.append({**compute_metrics(y, df[col].clip(0.01, 0.99), alias), "segment": "overall", "innings": "all"})

    # By innings
    for inn in [1, 2]:
        sub = df[df["innings"] == inn]
        if len(sub) < 50:
            continue
        y_inn = sub[outcome_col].astype(float)
        for alias, col in model_cols_to_test.items():
            rows.append({**compute_metrics(y_inn, sub[col].clip(0.01, 0.99), alias), "segment": f"inn{inn}", "innings": str(inn)})

    # By phase
    for phase in ["powerplay", "middle", "death"]:
        sub = df[df["phase"].str.lower().str.contains(phase, na=False)]
        if len(sub) < 30:
            continue
        y_p = sub[outcome_col].astype(float)
        for alias, col in model_cols_to_test.items():
            rows.append({**compute_metrics(y_p, sub[col].clip(0.01, 0.99), alias), "segment": phase, "innings": "all"})

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Deviation analysis
# ---------------------------------------------------------------------------

def deviation_analysis(df: pd.DataFrame) -> dict:
    """Analyse model vs market deviation patterns."""
    results = {}

    # Overall stats
    results["overall"] = {
        "mean_deviation": round(df["deviation"].mean(), 4),
        "std_deviation": round(df["deviation"].std(), 4),
        "mean_abs_deviation": round(df["deviation_abs"].mean(), 4),
        "pct_model_higher": round((df["deviation"] > 0.05).mean(), 3),
        "pct_market_higher": round((df["deviation"] < -0.05).mean(), 3),
        "correlation": round(df["model_prob"].corr(df["market_prob"]), 4),
    }

    # By phase
    phase_stats = {}
    for phase in df["phase"].unique():
        sub = df[df["phase"] == phase]
        if len(sub) < 20:
            continue
        phase_stats[phase] = {
            "n": len(sub),
            "mean_deviation": round(sub["deviation"].mean(), 4),
            "mean_abs_deviation": round(sub["deviation_abs"].mean(), 4),
        }
    results["by_phase"] = phase_stats

    # Calibration bins: is the market's probability better or worse than model?
    bins = [0, 0.2, 0.35, 0.5, 0.65, 0.8, 1.0]
    labels = ["<20%", "20-35%", "35-50%", "50-65%", "65-80%", ">80%"]
    df["market_bin"] = pd.cut(df["market_prob"], bins=bins, labels=labels)
    bin_stats = df.groupby("market_bin", observed=True).agg(
        n=("market_prob", "count"),
        mean_market=("market_prob", "mean"),
        mean_model=("model_prob", "mean"),
        mean_deviation=("deviation", "mean"),
    ).reset_index()
    results["by_market_bin"] = bin_stats.to_dict("records")

    return results


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def generate_report(df: pd.DataFrame, metrics_df: pd.DataFrame, dev: dict) -> str:
    lines = []
    lines.append("# PSL Model vs Market Analysis\n")
    lines.append(f"**Generated**: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}  ")
    lines.append(f"**Data**: {len(df):,} ball states from {df['match_id'].nunique() if 'match_id' in df.columns else 'N/A'} match(es)  ")
    lines.append(f"**Model**: {df['model_version'].iloc[0] if 'model_version' in df.columns else 'unknown'}  ")
    lines.append(f"**Feature Store**: {df['feature_store_version'].iloc[0] if 'feature_store_version' in df.columns else 'unknown'}  ")
    lines.append("")

    # Model vs Market correlation
    ov = dev["overall"]
    lines.append("## Model vs Market Alignment\n")
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Correlation (model vs market) | {ov['correlation']:.4f} |")
    lines.append(f"| Mean deviation (model − market) | {ov['mean_deviation']:+.4f} |")
    lines.append(f"| Std deviation | {ov['std_deviation']:.4f} |")
    lines.append(f"| Mean absolute deviation | {ov['mean_abs_deviation']:.4f} |")
    lines.append(f"| % model > market by >5% | {ov['pct_model_higher']:.1%} |")
    lines.append(f"| % market > model by >5% | {ov['pct_market_higher']:.1%} |")
    lines.append("")

    # Phase breakdown
    if dev.get("by_phase"):
        lines.append("## Deviation by Phase\n")
        lines.append("| Phase | N | Mean Dev | Mean |Dev| |")
        lines.append("|-------|---|----------|---------|")
        for phase, s in dev["by_phase"].items():
            lines.append(f"| {phase} | {s['n']:,} | {s['mean_deviation']:+.4f} | {s['mean_abs_deviation']:.4f} |")
        lines.append("")

    # Metrics table
    if not metrics_df.empty:
        overall = metrics_df[metrics_df["segment"] == "overall"].copy()
        overall = overall.sort_values("brier")
        lines.append("## Predictive Accuracy (Overall)\n")
        lines.append("| Source | Brier ↓ | ECE ↓ | LogLoss ↓ | N |")
        lines.append("|--------|---------|-------|-----------|---|")
        for _, row in overall.iterrows():
            lines.append(f"| {row['label']} | **{row['brier']:.4f}** | {row['ece']:.4f} | {row['logloss']:.4f} | {row['n']:,} |")
        lines.append("")

        # By innings
        for inn in ["1", "2"]:
            inn_df = metrics_df[metrics_df["innings"] == inn].sort_values("brier")
            if inn_df.empty:
                continue
            lines.append(f"### Innings {inn}\n")
            lines.append("| Source | Brier ↓ | ECE ↓ | LogLoss ↓ |")
            lines.append("|--------|---------|-------|-----------|")
            for _, row in inn_df.iterrows():
                lines.append(f"| {row['label']} | {row['brier']:.4f} | {row['ece']:.4f} | {row['logloss']:.4f} |")
            lines.append("")

    # Market bin calibration
    if dev.get("by_market_bin"):
        lines.append("## Market Calibration — Model Deviation by Market Probability Bucket\n")
        lines.append("| Market Range | N | Avg Market | Avg Model | Mean Dev |")
        lines.append("|-------------|---|-----------|-----------|---------|")
        for b in dev["by_market_bin"]:
            lines.append(
                f"| {b['market_bin']} | {int(b['n']):,} | "
                f"{b['mean_market']:.3f} | {b['mean_model']:.3f} | "
                f"{b['mean_deviation']:+.4f} |"
            )
        lines.append("")

    # Model version note
    model_versions = df["model_version"].value_counts().to_dict() if "model_version" in df.columns else {}
    lines.append("## Data Notes\n")
    lines.append(f"- Model versions in data: {model_versions}")
    lines.append(f"- Note: if model_version = 't20_male_v2', data was recorded before PSL v1 was trained.")
    lines.append(f"  Re-record match states after PSL v1 deployment for accurate PSL v1 vs market comparison.")
    lines.append(f"- Market odds source: betx21.live (embedded in match state logger)")
    lines.append("")
    lines.append(f"*Analysis generated by `scripts/analyze_psl_model_vs_market.py`*")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("PSL MODEL vs MARKET ANALYSIS")
    print("=" * 60)

    # Load
    df = load_match_states()

    # Clean
    df = validate_and_clean(df)

    # Segment metrics
    print("\nComputing accuracy metrics...")
    metrics_df = segment_analysis(df)
    if not metrics_df.empty:
        overall = metrics_df[metrics_df["segment"] == "overall"].sort_values("brier")
        print("\nOverall accuracy (sorted by Brier):")
        print(overall[["label", "brier", "ece", "logloss", "n"]].to_string(index=False))

    # Deviation analysis
    print("\nComputing model vs market deviation...")
    dev = deviation_analysis(df)
    ov = dev["overall"]
    print(f"  Correlation:      {ov['correlation']:.4f}")
    print(f"  Mean deviation:   {ov['mean_deviation']:+.4f}")
    print(f"  Mean |deviation|: {ov['mean_abs_deviation']:.4f}")

    # Save outputs
    parquet_path = OUTPUT_DIR / "psl_model_vs_market.parquet"
    df.to_parquet(parquet_path, index=False)
    print(f"\n✅ Saved: {parquet_path}")

    if not metrics_df.empty:
        csv_path = OUTPUT_DIR / "psl_model_vs_market_summary.csv"
        metrics_df.to_csv(csv_path, index=False)
        print(f"✅ Saved: {csv_path}")

    report = generate_report(df, metrics_df, dev)
    report_path = OUTPUT_DIR / "psl_model_vs_market_report.md"
    report_path.write_text(report, encoding="utf-8")
    print(f"✅ Saved: {report_path}")


if __name__ == "__main__":
    main()
