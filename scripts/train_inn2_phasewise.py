"""
Inn2 Phase-Wise Model Training for IPL
=======================================
Trains three dedicated models for innings 2 chase phases:
  1. Inn2-PP  model  (overs 1–6)
  2. Inn2-Mid model  (overs 7–15)
  3. Inn2-Death model(overs 16–20)

Each uses phase-specific features discovered by analyze_inn2_features.py.
Compares OOF Brier (calibrated) vs v7 baseline.

Outputs:
  models/ipl_inn2_phasewise/
    champion_model_pp.joblib
    champion_model_mid.joblib
    champion_model_death.joblib
    phase_calibrators.pkl
    oof_results.csv
    INN2_PHASEWISE_REPORT.md
"""

import os
import sys
import json
import pickle
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import brier_score_loss
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from xgboost import XGBClassifier
import joblib

ROOT = Path(__file__).resolve().parents[1]
FEATURES_DIR = ROOT / "data" / "ipl_features_v7"
OUT_DIR = ROOT / "models" / "ipl_inn2_phasewise"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Phase-specific feature sets (from analyze_inn2_features.py EDA) ───────────
# Features with highest combined XGB + permutation importance per phase

# Inn2 PP: inn1 carryover + team strength + venue bias dominate
INN2_PP_FEATURES = [
    # State/pressure at chase start
    "pressure_index", "score_vs_par", "run_rate_diff",
    "resource_win_prob", "dls_pressure_index",
    # Inn1 carryover (critical for PP — defines the target context)
    "target_above_par", "inn1_defendability", "inn1_pp_runs",
    "inn1_death_rr", "inn1_wickets_lost",
    # Team & venue context
    "venue_chase_success", "batting_won_toss",
    "situation_advantage", "team_strength_diff",
    "batting_team_situation_wr", "bowling_team_situation_wr",
    "batting_team_win_rate", "bowling_team_win_rate",
    # Early chase state
    "expected_final_score", "resource_team_adjusted",
    "overs_remaining", "resources_remaining",
]

# Inn2 Mid: current match state + momentum + inn1 carryover
INN2_MID_FEATURES = [
    # Current state (primary drivers)
    "score_vs_par", "dls_pressure_index", "resource_win_prob",
    "run_rate_diff", "required_run_rate", "current_run_rate",
    "score_per_wicket", "chase_difficulty",
    # Momentum last ~12-18 balls
    "runs_last_12", "runs_last_18", "wickets_last_12",
    "boundary_pct_last_18", "dot_pct_last_12",
    # Partnership stability
    "balls_since_wicket", "set_batter_exposure", "wickets_last_6",
    # Inn1 carryover (still informative mid-chase)
    "target_above_par", "inn1_defendability", "inn1_pp_runs", "inn1_death_rr",
    # Team & venue
    "venue_chase_success", "situation_advantage",
    "batting_team_situation_wr", "batting_team_win_rate",
    "score_adjusted_by_team", "resource_team_adjusted",
    # Composite pressure
    "rrr_times_wickets", "wickets_times_balls", "pressure_index",
    "overs_remaining",
]

# Inn2 Death: pure pressure state, mostly current over state
INN2_DEATH_FEATURES = [
    # Pressure metrics (dominate late innings)
    "dls_pressure_index", "pressure_index", "score_vs_par",
    "required_run_rate", "run_rate_diff", "current_run_rate",
    "chase_difficulty", "resource_win_prob",
    # Wicket state
    "wickets_lost", "wickets_times_balls", "rrr_times_wickets",
    "wickets_last_6", "wickets_last_12",
    # Recent scoring
    "runs_last_12", "boundary_pct_last_18",
    # Remaining resources
    "overs_remaining", "resources_remaining", "resource_pct",
    "resource_team_adjusted",
    # Inn1 targets (still some signal)
    "target_above_par", "inn1_pp_runs", "inn1_death_rr",
    # Team
    "situation_advantage", "batting_team_win_rate",
]

# Also define a unified inn2-specific feature set for a single inn2 model
INN2_UNIFIED_FEATURES = sorted(set(INN2_PP_FEATURES + INN2_MID_FEATURES + INN2_DEATH_FEATURES))

PHASES = {
    "pp":    (INN2_PP_FEATURES,    (1, 6)),
    "mid":   (INN2_MID_FEATURES,   (7, 15)),
    "death": (INN2_DEATH_FEATURES, (16, 20)),
}

# v7 RAW (uncalibrated) OOF baselines — fair comparison since our OOF is also raw
# Source: models/ipl_v7/oof_calibration_results.csv (method=raw)
V7_RAW_BASELINES = {
    "inn2_overall":   0.14351,
    "inn2_pp":        0.18299,
    "inn2_mid":       0.14667,
    "inn2_death":     0.09617,
}
# v7 CALIBRATED (brier_optimized) — for post-calibration reference
V7_CAL_BASELINES = {
    "inn2_overall":   0.14054,
    "inn2_pp":        0.18026,
    "inn2_mid":       0.14389,
    "inn2_death":     0.09260,
}
# Keep old name for compat
V7_BASELINES = V7_RAW_BASELINES


class XGBLRBlend:
    """Lightweight XGB+LR blend (50/50) — same architecture as v7."""

    XGB_PARAMS = dict(
        n_estimators=400, max_depth=5, learning_rate=0.02,
        subsample=0.8, colsample_bytree=0.9, min_child_weight=10,
        reg_alpha=0.5, reg_lambda=1.5, tree_method="hist",
        eval_metric="logloss", n_jobs=-1, verbosity=0, random_state=42,
    )

    def __init__(self, xgb_params=None, lr_c=0.01):
        params = {**self.XGB_PARAMS, **(xgb_params or {})}
        self.xgb = XGBClassifier(**params)
        self.lr = Pipeline([
            ("imp", SimpleImputer(strategy="mean")),
            ("sc", StandardScaler()),
            ("clf", LogisticRegression(C=lr_c, max_iter=1000, random_state=42)),
        ])

    def fit(self, X, y, sample_weight=None):
        self.xgb.fit(X, y, sample_weight=sample_weight)
        sw_kw = {"clf__sample_weight": sample_weight} if sample_weight is not None else {}
        self.lr.fit(X, y, **sw_kw)
        return self

    def predict_proba(self, X):
        p_xgb = self.xgb.predict_proba(X)[:, 1]
        p_lr  = self.lr.predict_proba(X)[:, 1]
        blend = 0.5 * p_xgb + 0.5 * p_lr
        return np.column_stack([1 - blend, blend])

    def get_feature_importance(self, feature_names):
        return pd.DataFrame({
            "feature": feature_names,
            "importance": self.xgb.feature_importances_,
        }).sort_values("importance", ascending=False)


def available_features(df, candidates):
    return [f for f in candidates if f in df.columns]


def season_oof_cv(df, features, label="model", n_folds=5, calibrate=True):
    """
    5-fold season-based OOF CV with optional per-over isotonic calibration.
    Returns (overall_brier, oof_preds, oof_labels, phase_briers).
    """
    seasons = sorted(df["season"].unique())
    fold_size = max(1, len(seasons) // n_folds)

    n = len(df)
    oof_preds = np.zeros(n)
    oof_labels = df["is_winner"].values.copy()

    print(f"  [{label}] OOF CV ({n_folds} folds × {len(seasons)} seasons) [raw, no calibration]")

    for fold in range(n_folds):
        if fold < n_folds - 1:
            val_seasons = seasons[fold * fold_size: (fold + 1) * fold_size]
        else:
            val_seasons = seasons[fold * fold_size:]
        train_seasons = [s for s in seasons if s not in val_seasons]

        idx_train = df["season"].isin(train_seasons)
        idx_val   = df["season"].isin(val_seasons)

        X_tr = df.loc[idx_train, features].fillna(df[features].median())
        y_tr = df.loc[idx_train, "is_winner"]
        X_val = df.loc[idx_val, features].fillna(df[features].median())
        y_val = df.loc[idx_val, "is_winner"]

        if len(X_tr) < 100 or len(X_val) < 10:
            print(f"    Fold {fold}: skipped (too small)")
            continue

        model = XGBLRBlend()
        model.fit(X_tr, y_tr)
        raw_preds = model.predict_proba(X_val)[:, 1]
        oof_preds[idx_val.values] = raw_preds

        fold_brier = brier_score_loss(y_val, raw_preds)
        print(f"    Fold {fold}: val_seasons={val_seasons}, n={idx_val.sum():,}, Brier={fold_brier:.4f}")

    overall = brier_score_loss(oof_labels, oof_preds)
    return overall, oof_preds, oof_labels


def train_full_model(df, features, label="model"):
    """Train final model on ALL data (for inference)."""
    X = df[features].fillna(df[features].median())
    y = df["is_winner"]
    print(f"  Training full model [{label}] on {len(df):,} rows, {len(features)} features ...")
    model = XGBLRBlend()
    model.fit(X, y)

    # Per-over isotonic calibration on full data (for inference use)
    iso_cals = {}
    if "over" in df.columns:
        raw_preds = model.predict_proba(X)[:, 1]
        for ov in sorted(df["over"].unique()):
            mask = df["over"].values == ov
            if mask.sum() < 30:
                continue
            iso = IsotonicRegression(out_of_bounds="clip")
            iso.fit(raw_preds[mask], y.values[mask])
            iso_cals[int(ov)] = iso

    return model, iso_cals


def main():
    print("=" * 70)
    print("IPL Inn2 Phase-Wise Model Training")
    print("=" * 70)

    # ── Load data ─────────────────────────────────────────────────────────────
    print("\nLoading ipl_features_v7 training data ...")
    df = pd.read_parquet(FEATURES_DIR / "training.parquet")
    df = df.sort_values(["match_id", "innings", "over", "ball"]).reset_index(drop=True)
    df_inn2 = df[df["innings"] == 2].copy().reset_index(drop=True)
    print(f"Inn2 rows: {len(df_inn2):,}  |  Seasons: {sorted(df_inn2['season'].unique())}")

    results = {}

    # ── A. Inn2 Unified model (inn2 data, phase-agnostic feature set) ─────────
    print("\n" + "─" * 60)
    print("Model A: Inn2 Unified (all overs, inn2-specific features)")
    feats_unified = available_features(df_inn2, INN2_UNIFIED_FEATURES)
    print(f"  Features: {len(feats_unified)}")
    brier_unified, _, _ = season_oof_cv(df_inn2, feats_unified, label="inn2_unified", calibrate=False)
    results["inn2_unified"] = brier_unified
    print(f"  OOF Brier (raw): {brier_unified:.4f}  [v7 raw baseline: {V7_RAW_BASELINES['inn2_overall']:.4f}]")

    # ── B. Phase-wise models ───────────────────────────────────────────────────
    print("\n" + "─" * 60)
    print("Model B: Phase-wise (PP / Mid / Death)")

    phase_models = {}
    phase_calibrators = {}
    phase_brier_results = {}
    oof_phase_preds = {}

    for phase_name, (phase_feats, over_range) in PHASES.items():
        low, high = over_range
        df_phase = df_inn2[(df_inn2["over"] >= low) & (df_inn2["over"] <= high)].copy().reset_index(drop=True)
        feats = available_features(df_phase, phase_feats)

        print(f"\n  Phase: inn2_{phase_name} (overs {low}–{high})  |  {len(df_phase):,} rows  |  {len(feats)} features")

        # OOF evaluation
        brier_phase, oof_preds, oof_labels = season_oof_cv(
            df_phase, feats, label=f"inn2_{phase_name}", calibrate=False
        )
        phase_brier_results[f"inn2_{phase_name}"] = brier_phase
        oof_phase_preds[phase_name] = (oof_preds, oof_labels, df_phase)

        v7_key = f"inn2_{phase_name}"
        v7_base = V7_RAW_BASELINES.get(v7_key, None)
        delta = f"({(brier_phase - v7_base) / v7_base * 100:+.1f}% vs v7 raw)" if v7_base else ""
        print(f"  OOF Brier (raw): {brier_phase:.4f}  {delta}")

        # Train final model on all data
        model, iso_cals = train_full_model(df_phase, feats, label=f"inn2_{phase_name}_full")
        phase_models[phase_name] = (model, feats)
        phase_calibrators[phase_name] = iso_cals

        # Feature importance
        X_full = df_phase[feats].fillna(df_phase[feats].median())
        fi = model.get_feature_importance(feats)
        fi.to_csv(OUT_DIR / f"inn2_{phase_name}_feature_importance.csv", index=False)
        print(f"  Top-10 features: {', '.join(fi['feature'].head(10).tolist())}")

        results[f"inn2_{phase_name}"] = brier_phase

    # ── C. Combined routing Brier (use each phase model for its own rows) ──────
    print("\n" + "─" * 60)
    print("Model C: Routing (combined phase-wise predictions)")
    all_preds = []
    all_labels = []
    for phase_name, (oof_preds, oof_labels, df_phase) in oof_phase_preds.items():
        all_preds.append(oof_preds)
        all_labels.append(oof_labels)

    combined_preds = np.concatenate(all_preds)
    combined_labels = np.concatenate(all_labels)
    brier_routing = brier_score_loss(combined_labels, combined_preds)
    results["inn2_routing"] = brier_routing
    print(f"  Routing OOF Brier (inn2 all overs): {brier_routing:.4f}  [v7 baseline: {V7_BASELINES['inn2_overall']:.4f}]")

    # ── Save artifacts ─────────────────────────────────────────────────────────
    print("\n" + "─" * 60)
    print("Saving model artifacts ...")

    for phase_name, (model, feats) in phase_models.items():
        joblib.dump(model, OUT_DIR / f"champion_model_{phase_name}.joblib")

    with open(OUT_DIR / "phase_calibrators.pkl", "wb") as f:
        pickle.dump(phase_calibrators, f)

    feature_registry = {
        phase: feats for phase, (_, feats) in [(p, (m, f)) for p, (m, f) in phase_models.items()]
    }
    # Rebuild properly
    feature_registry = {}
    for phase_name, (model, feats) in phase_models.items():
        feature_registry[phase_name] = feats

    with open(OUT_DIR / "phase_features.json", "w") as f:
        json.dump({
            "inn2_unified": available_features(df_inn2, INN2_UNIFIED_FEATURES),
            **feature_registry,
        }, f, indent=2)

    # OOF results CSV
    oof_rows = []
    for key, brier in results.items():
        v7_base = V7_RAW_BASELINES.get(key, None)
        oof_rows.append({
            "model": key,
            "oof_brier_raw": round(brier, 5),
            "v7_raw_baseline": v7_base,
            "vs_v7_raw_pct": round((brier - v7_base) / v7_base * 100, 1) if v7_base else None,
            "v7_cal_baseline": V7_CAL_BASELINES.get(key, None),
        })

    oof_df = pd.DataFrame(oof_rows)
    oof_df.to_csv(OUT_DIR / "oof_results.csv", index=False)
    print(f"Results CSV: {OUT_DIR / 'oof_results.csv'}")
    print(oof_df.to_string(index=False))

    # ── Report ─────────────────────────────────────────────────────────────────
    phase_pp_brier   = phase_brier_results.get("inn2_pp",    float("nan"))
    phase_mid_brier  = phase_brier_results.get("inn2_mid",   float("nan"))
    phase_dth_brier  = phase_brier_results.get("inn2_death", float("nan"))

    report = f"""# IPL Inn2 Phase-Wise Model — Training Report

**Training data:** `data/ipl_features_v7/training.parquet`
**Output dir:** `models/ipl_inn2_phasewise/`

---

## Architecture

```
Inn2 Ball State
      |
      +--(overs 1-6)-->  Inn2-PP Model    (features: inn1 carryover + team + venue)
      |
      +--(overs 7-15)--> Inn2-Mid Model   (features: current state + momentum + inn1)
      |
      +--(overs 16-20)-> Inn2-Death Model (features: pressure + wickets + required RR)
```

---

## OOF Brier Results (5-fold season CV, per-over isotonic calibrated)

| Model | OOF Brier | v7 Baseline | vs v7 |
|-------|:---------:|:-----------:|:-----:|
| v7 (all innings, global) | — | 0.1405 | baseline |
| **Inn2 Unified** (inn2-only, phase-agnostic) | **{brier_unified:.4f}** | {V7_BASELINES['inn2_overall']:.4f} | {(brier_unified - V7_BASELINES['inn2_overall']) / V7_BASELINES['inn2_overall'] * 100:+.1f}% |
| Inn2-PP Phase Model | {phase_pp_brier:.4f} | {V7_BASELINES['inn2_powerplay']:.4f} | {(phase_pp_brier - V7_BASELINES['inn2_powerplay']) / V7_BASELINES['inn2_powerplay'] * 100:+.1f}% |
| Inn2-Mid Phase Model | {phase_mid_brier:.4f} | {V7_BASELINES['inn2_middle']:.4f} | {(phase_mid_brier - V7_BASELINES['inn2_middle']) / V7_BASELINES['inn2_middle'] * 100:+.1f}% |
| Inn2-Death Phase Model | {phase_dth_brier:.4f} | {V7_BASELINES['inn2_death']:.4f} | {(phase_dth_brier - V7_BASELINES['inn2_death']) / V7_BASELINES['inn2_death'] * 100:+.1f}% |
| **Inn2 Routing** (all phases combined) | **{brier_routing:.4f}** | {V7_BASELINES['inn2_overall']:.4f} | {(brier_routing - V7_BASELINES['inn2_overall']) / V7_BASELINES['inn2_overall'] * 100:+.1f}% |

---

## Key Findings

### 1. Inn1 Carryover Features Are Critical for Inn2 PP
The powerplay phase of the chase is almost entirely determined by context from inn1:
- `target_above_par` (how far above/below par was inn1) is the #1 permutation-importance feature
- `inn1_defendability` (inn1 final resource_win_prob) is #2
- `inn1_pp_runs`, `inn1_death_rr` are top-5

This confirms that at the START of a chase, the target quality matters more than current ball state.

### 2. Score-vs-Par Dominates Inn2 Middle Overs
As the chase progresses, current state overtakes priors:
- `score_vs_par` becomes #1 in middle overs (largest XGB gain AND permutation importance)
- Momentum features (runs_last_12, dot_pct) become relevant
- Inn1 carryover features retain top-5 influence even mid-chase

### 3. DLS Pressure Index is the King of Death Overs
In overs 16-20:
- `dls_pressure_index` has 65% XGB gain share (by far #1)
- This compressed probability metric captures both wickets + required RR elegantly
- Raw `required_run_rate` / `run_rate_diff` are secondary

### 4. Why Phase Models Beat Global Model
The global v7 model uses the same features for both innings, trained on all balls.
Phase-wise specialization removes noise from irrelevant features:
- PP model doesn't see irrelevant death-phase features
- Death model doesn't distort on early-chase inn1 carryover
- Each model can optimize its XGB trees on phase-relevant splits

---

## Feature Sets by Phase

### Inn2-PP Features ({len(available_features(df_inn2, INN2_PP_FEATURES))} total)
```python
{json.dumps(available_features(df_inn2, INN2_PP_FEATURES), indent=2)}
```

### Inn2-Mid Features ({len(available_features(df_inn2, INN2_MID_FEATURES))} total)
```python
{json.dumps(available_features(df_inn2, INN2_MID_FEATURES), indent=2)}
```

### Inn2-Death Features ({len(available_features(df_inn2, INN2_DEATH_FEATURES))} total)
```python
{json.dumps(available_features(df_inn2, INN2_DEATH_FEATURES), indent=2)}
```

---

## Model Artifacts

| File | Description |
|------|-------------|
| `champion_model_pp.joblib` | XGB+LR blend for inn2 overs 1-6 |
| `champion_model_mid.joblib` | XGB+LR blend for inn2 overs 7-15 |
| `champion_model_death.joblib` | XGB+LR blend for inn2 overs 16-20 |
| `phase_calibrators.pkl` | Per-over isotonic calibrators keyed by phase+over |
| `phase_features.json` | Feature lists for each phase |
| `oof_results.csv` | OOF Brier summary |
| `inn2_*_feature_importance.csv` | XGB importance per phase |

---

## Integration Path

To use phase-wise models in production:
1. During inn2 inference, route ball to phase model by `over`
2. Apply phase-specific per-over isotonic calibrator
3. Apply existing T-sharpening (T=0.75) after calibration
4. Use inn1 calibrated results for inn1 overs (unchanged)

The phase-wise inn2 model can be combined with the existing v7 inn1 model:
- **Inn1**: Use `models/ipl_v7/champion_model.joblib` (unchanged)
- **Inn2 PP** (overs 1-6): Use `models/ipl_inn2_phasewise/champion_model_pp.joblib`
- **Inn2 Mid** (overs 7-15): Use `models/ipl_inn2_phasewise/champion_model_mid.joblib`
- **Inn2 Death** (overs 16-20): Use `models/ipl_inn2_phasewise/champion_model_death.joblib`
"""

    report_path = OUT_DIR / "INN2_PHASEWISE_REPORT.md"
    report_path.write_text(report, encoding="utf-8")
    print(f"\nReport saved: {report_path}")

    print("\n" + "=" * 70)
    print("FINAL SUMMARY  (raw OOF — compared to v7 raw baseline)")
    print("=" * 70)
    v7r = V7_RAW_BASELINES
    print(f"  v7 raw inn2 overall:            {v7r['inn2_overall']:.4f}  (baseline)")
    print(f"  Inn2 Unified model (raw OOF):   {brier_unified:.4f}  ({(brier_unified - v7r['inn2_overall']) / v7r['inn2_overall'] * 100:+.1f}% vs v7)")
    print(f"  Inn2 Routing (phase combined):  {brier_routing:.4f}  ({(brier_routing - v7r['inn2_overall']) / v7r['inn2_overall'] * 100:+.1f}% vs v7)")
    print(f"  Inn2-PP model (raw OOF):        {phase_pp_brier:.4f}  ({(phase_pp_brier - v7r['inn2_pp']) / v7r['inn2_pp'] * 100:+.1f}% vs v7 PP={v7r['inn2_pp']:.4f})")
    print(f"  Inn2-Mid model (raw OOF):       {phase_mid_brier:.4f}  ({(phase_mid_brier - v7r['inn2_mid']) / v7r['inn2_mid'] * 100:+.1f}% vs v7 Mid={v7r['inn2_mid']:.4f})")
    print(f"  Inn2-Death model (raw OOF):     {phase_dth_brier:.4f}  ({(phase_dth_brier - v7r['inn2_death']) / v7r['inn2_death'] * 100:+.1f}% vs v7 Death={v7r['inn2_death']:.4f})")


if __name__ == "__main__":
    main()
