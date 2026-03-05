"""
Temporal Split Validation: MC vs ML for Male International Cricket

Definitively answers: which is better on truly unseen data?

Split:
  - Train:  pre-2024  (ML trains here, MC needs no training)
  - Val:    2024      (tune / sanity-check)
  - Test:   2025+     (final held-out verdict)

Formats:  ODI Male,  T20I Male

MC baseline  = resource_win_prob feature (physics-based, no training needed)
ML model     = XGBLogRegEnsemble trained on pre-2024 data only

Metrics: Brier Score, ECE (10-bin), Log-Loss
"""

import os
import sys
import argparse
import warnings
from pathlib import Path
import time

import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import brier_score_loss, log_loss

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
warnings.filterwarnings("ignore", category=FutureWarning)

from bbl_pipeline.training.trainer import XGBLogRegEnsemble


# ── helpers ──────────────────────────────────────────────────────────────

def ece(probs: np.ndarray, labels: np.ndarray, n_bins: int = 10) -> float:
    """Expected Calibration Error (equal-width bins)."""
    bins = np.linspace(0, 1, n_bins + 1)
    idx = np.clip(np.digitize(probs, bins) - 1, 0, n_bins - 1)
    total = 0.0
    for b in range(n_bins):
        mask = idx == b
        if not mask.any():
            continue
        total += mask.sum() / len(probs) * abs(probs[mask].mean() - labels[mask].mean())
    return total


def metrics_dict(probs: np.ndarray, labels: np.ndarray) -> dict:
    """Return {brier, ece, logloss}."""
    p = np.clip(probs, 1e-7, 1 - 1e-7)
    return {
        "brier": brier_score_loss(labels, p),
        "ece": ece(p, labels),
        "logloss": log_loss(labels, p),
    }


def load_raw_dates(raw_dir: str) -> pd.Series:
    """Load match_id + date from raw parquets, return date Series aligned to
    the sorted ball index (same order as training.parquet)."""
    dfs = []
    for root, _, files in os.walk(raw_dir):
        for f in files:
            if f.endswith(".parquet"):
                dfs.append(pd.read_parquet(
                    os.path.join(root, f),
                    columns=["match_id", "date", "innings", "over", "ball"],
                ))
    raw = pd.concat(dfs, ignore_index=True)
    raw = raw.sort_values(["match_id", "innings", "over", "ball"]).reset_index(drop=True)
    raw["date"] = pd.to_datetime(raw["date"])
    return raw[["match_id", "date"]]


def phase_label(row):
    """Return phase name based on overs_remaining and format total overs."""
    overs_bowled = row["_total_overs"] - row["overs_remaining"]
    if row["_total_overs"] == 50:  # ODI
        if overs_bowled < 10:
            return "PP (1-10)"
        elif overs_bowled < 34:
            return "Middle (11-34)"
        elif overs_bowled < 40:
            return "Setup (35-40)"
        else:
            return "Death (41-50)"
    else:  # T20
        if overs_bowled < 6:
            return "PP (1-6)"
        elif overs_bowled < 15:
            return "Middle (7-15)"
        else:
            return "Death (16-20)"


# ── main pipeline ────────────────────────────────────────────────────────

FORMAT_CONFIGS = {
    "odi_male": {
        "features_dir": "data/odi_features_v1",
        "raw_dir": "data/odi_raw/matches",
        "total_overs": 50,
        "label": "ODI Male",
    },
    "t20i_male": {
        "features_dir": "data/t20_international_male_features_v1",
        "raw_dir": "data/t20_international_male_raw/matches",
        "total_overs": 20,
        "label": "T20I Male",
    },
}


def run_format(fmt_key: str, cfg: dict, sample_per_over: int = 0):
    """Full temporal validation for one format."""

    label = cfg["label"]
    t0 = time.time()
    print(f"\n{'='*90}")
    print(f"  {label}  —  Temporal MC vs ML Validation")
    print(f"{'='*90}")

    # 1. Load features + add dates from raw data ─────────────────────────
    print(f"Loading features from {cfg['features_dir']} ...")
    features = pd.read_parquet(Path(cfg["features_dir"]) / "training.parquet")

    print(f"Loading dates from {cfg['raw_dir']} ...")
    raw_meta = load_raw_dates(cfg["raw_dir"])
    assert len(raw_meta) == len(features), (
        f"Row mismatch: raw={len(raw_meta)}, features={len(features)}"
    )
    features["match_id"] = raw_meta["match_id"].values
    features["date"] = raw_meta["date"].values
    features["year"] = features["date"].dt.year
    features["_total_overs"] = cfg["total_overs"]

    # 2. Temporal split ───────────────────────────────────────────────────
    train_mask = features["year"] < 2024
    val_mask   = features["year"] == 2024
    test_mask  = features["year"] >= 2025

    df_train = features[train_mask].copy()
    df_val   = features[val_mask].copy()
    df_test  = features[test_mask].copy()

    n_train_matches = df_train["match_id"].nunique()
    n_val_matches   = df_val["match_id"].nunique()
    n_test_matches  = df_test["match_id"].nunique()

    print(f"\n  Split            | Matches | Ball-states")
    print(f"  -----------------+---------+------------")
    print(f"  Train  (< 2024)  | {n_train_matches:>7} | {len(df_train):>10,}")
    print(f"  Val    (= 2024)  | {n_val_matches:>7} | {len(df_val):>10,}")
    print(f"  Test   (≥ 2025)  | {n_test_matches:>7} | {len(df_test):>10,}")

    if len(df_val) == 0 or len(df_test) == 0:
        print("  ⚠ Insufficient data for val or test — skipping format.")
        return None

    # 3. Optional subsampling (1 per over per match for speed) ───────────
    if sample_per_over > 0:
        for name, part in [("val", df_val), ("test", df_test)]:
            pass  # keep full for accuracy

    # 4. Train ML model on pre-2024 data ─────────────────────────────────
    print(f"\n  Training ML model (XGBLogRegEnsemble) on {len(df_train):,} rows ...")
    target_col = "is_winner"
    ml_model = XGBLogRegEnsemble()

    X_train = df_train.drop(columns=["is_winner", "match_id", "date", "year", "_total_overs"])
    y_train = df_train[target_col]
    ml_model.fit(X_train, y_train)
    used_features = ml_model.selected_features_
    print(f"  ML model fitted — {len(used_features)} features used.")

    # 5. Train an isotonic calibrator for ML on validation set ────────────
    X_val = df_val[used_features].fillna(0)
    y_val = df_val[target_col].values
    ml_val_raw = ml_model.predict_proba(pd.DataFrame(X_val, columns=used_features))[:, 1]

    iso_ml = IsotonicRegression(y_min=0.001, y_max=0.999, out_of_bounds="clip")
    iso_ml.fit(ml_val_raw, y_val)
    print("  Isotonic calibrator fitted on val for ML.")

    # 6. Train an isotonic calibrator for MC on validation set ────────────
    mc_val_raw = df_val["resource_win_prob"].values
    iso_mc = IsotonicRegression(y_min=0.001, y_max=0.999, out_of_bounds="clip")
    iso_mc.fit(mc_val_raw, y_val)
    print("  Isotonic calibrator fitted on val for MC.")

    # 7. Evaluate on each split ──────────────────────────────────────────
    results_all = []

    for split_name, df_split in [("Val (2024)", df_val), ("Test (2025+)", df_test)]:
        X_split = df_split[used_features].fillna(0)
        y_true  = df_split[target_col].values

        # ML predictions
        ml_raw  = ml_model.predict_proba(pd.DataFrame(X_split, columns=used_features))[:, 1]
        ml_cal  = iso_ml.predict(ml_raw)

        # MC predictions (resource_win_prob — already computed, no training)
        mc_raw  = df_split["resource_win_prob"].values
        mc_cal  = iso_mc.predict(mc_raw)

        # Hybrid: average of calibrated MC + calibrated ML
        hybrid  = 0.5 * ml_cal + 0.5 * mc_cal

        # Overall metrics
        for method, probs in [
            ("MC (raw)", mc_raw),
            ("MC (cal)", mc_cal),
            ("ML (raw)", ml_raw),
            ("ML (cal)", ml_cal),
            ("Hybrid",   hybrid),
        ]:
            m = metrics_dict(probs, y_true)
            results_all.append({
                "format": label,
                "split": split_name,
                "method": method,
                "n_states": len(y_true),
                **m,
            })

        # Per-innings metrics
        for inn in sorted(df_split["innings"].unique()):
            mask = df_split["innings"].values == inn
            if mask.sum() < 50:
                continue
            y_sub = y_true[mask]
            for method, probs in [
                ("MC (raw)", mc_raw[mask]),
                ("MC (cal)", mc_cal[mask]),
                ("ML (raw)", ml_raw[mask]),
                ("ML (cal)", ml_cal[mask]),
                ("Hybrid",   hybrid[mask]),
            ]:
                m = metrics_dict(probs, y_sub)
                results_all.append({
                    "format": label,
                    "split": f"{split_name} Inn{int(inn)}",
                    "method": method,
                    "n_states": int(mask.sum()),
                    **m,
                })

        # Per-phase metrics
        df_split = df_split.copy()
        df_split["phase"] = df_split.apply(phase_label, axis=1)
        for inn in sorted(df_split["innings"].unique()):
            for ph in df_split["phase"].unique():
                mask = (df_split["innings"].values == inn) & (df_split["phase"].values == ph)
                if mask.sum() < 30:
                    continue
                y_sub = y_true[mask]
                for method, probs in [
                    ("MC (raw)", mc_raw[mask]),
                    ("MC (cal)", mc_cal[mask]),
                    ("ML (raw)", ml_raw[mask]),
                    ("ML (cal)", ml_cal[mask]),
                    ("Hybrid",   hybrid[mask]),
                ]:
                    m = metrics_dict(probs, y_sub)
                    results_all.append({
                        "format": label,
                        "split": f"{split_name} Inn{int(inn)} {ph}",
                        "method": method,
                        "n_states": int(mask.sum()),
                        **m,
                    })

    elapsed = time.time() - t0
    print(f"\n  Completed {label} in {elapsed:.1f}s")
    return pd.DataFrame(results_all)


# ── reporting ────────────────────────────────────────────────────────────

def print_report(results_df: pd.DataFrame):
    """Pretty-print the comparison report."""

    for fmt in results_df["format"].unique():
        fmt_df = results_df[results_df["format"] == fmt]
        print(f"\n{'#'*90}")
        print(f"  TEMPORAL VALIDATION REPORT — {fmt}")
        print(f"{'#'*90}")

        # Group by split and show overall + breakdown
        for split in sorted(fmt_df["split"].unique(), key=lambda s: ("Val" in s, len(s), s)):
            sub = fmt_df[fmt_df["split"] == split]
            n = sub["n_states"].iloc[0]

            # Determine indentation level
            depth = split.count("Inn") + split.count("PP") + split.count("Middle") + split.count("Death") + split.count("Setup")
            indent = "  " * min(depth, 2)

            print(f"\n{indent}┌─ {split}  (N={n:,})")
            print(f"{indent}│ {'Method':<14} │ {'Brier':>8} │ {'ECE':>8} │ {'LogLoss':>8} │")
            print(f"{indent}│ {'─'*14}─┼{'─'*10}┼{'─'*10}┼{'─'*10}│")

            # Sort: show MC raw, MC cal, ML raw, ML cal, Hybrid
            method_order = ["MC (raw)", "MC (cal)", "ML (raw)", "ML (cal)", "Hybrid"]
            for method in method_order:
                row = sub[sub["method"] == method]
                if row.empty:
                    continue
                r = row.iloc[0]
                # Highlight best Brier
                brier_val = r["brier"]
                ece_val = r["ece"]
                ll_val = r["logloss"]
                print(f"{indent}│ {method:<14} │ {brier_val:>8.4f} │ {ece_val:>8.4f} │ {ll_val:>8.4f} │")
            print(f"{indent}└{'─'*48}")

        # Summary: who wins on test set overall?
        test_overall = fmt_df[
            (fmt_df["split"].str.startswith("Test")) &
            (~fmt_df["split"].str.contains("Inn"))
        ]
        if not test_overall.empty:
            print(f"\n  ★ TEST SET VERDICT ({fmt}):")
            best = test_overall.loc[test_overall["brier"].idxmin()]
            print(f"    Best Brier on held-out 2025+ data: {best['method']} = {best['brier']:.4f}")
            for _, r in test_overall.sort_values("brier").iterrows():
                marker = " ◀ BEST" if r["brier"] == best["brier"] else ""
                print(f"      {r['method']:<14}  Brier={r['brier']:.4f}  ECE={r['ece']:.4f}  LL={r['logloss']:.4f}{marker}")


# ── entry point ──────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Temporal MC vs ML validation for male international cricket"
    )
    parser.add_argument(
        "--formats",
        nargs="+",
        default=["odi_male", "t20i_male"],
        choices=list(FORMAT_CONFIGS.keys()),
        help="Formats to evaluate (default: both)",
    )
    args = parser.parse_args()

    all_results = []
    for fmt_key in args.formats:
        cfg = FORMAT_CONFIGS[fmt_key]
        df = run_format(fmt_key, cfg)
        if df is not None:
            all_results.append(df)

    if all_results:
        combined = pd.concat(all_results, ignore_index=True)
        print_report(combined)

        # Save CSV
        out_path = Path("data") / "temporal_mc_vs_ml_validation.csv"
        combined.to_csv(out_path, index=False)
        print(f"\n  Results saved to {out_path}")
    else:
        print("\nNo results produced.")


if __name__ == "__main__":
    main()
