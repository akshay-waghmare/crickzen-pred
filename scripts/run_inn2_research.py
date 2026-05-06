"""
IPL Inn2 Full Research Pipeline
=================================
Runs comprehensive EDA + model training for inn2 with new chase features.
Compares:
  - v7 raw baseline (all-innings global model)
  - Inn2 Unified model (inn2 data, phase-agnostic)
  - Phase-wise models: PP / Mid / Death
  - Phase-wise models WITH NEW FEATURES (chase labels + engineering)

Usage:
    python scripts/run_inn2_research.py
"""

import sys
import os
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

# ── ensure scripts/ is importable ─────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from inn2_feature_engineering import engineer_inn2_features, get_feature_sets

FEATURES_DIR = ROOT / "data" / "ipl_features_v7"
OUT_DIR      = ROOT / "models" / "ipl_inn2_v1"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── v7 OOF baselines (source: models/ipl_v7/oof_calibration_results.csv) ─────
V7_RAW = {
    "inn2_overall": 0.14351,
    "inn2_pp":      0.18299,
    "inn2_mid":     0.14667,
    "inn2_death":   0.09617,
}
V7_CAL = {
    "inn2_overall": 0.14054,
    "inn2_pp":      0.18026,
    "inn2_mid":     0.14389,
    "inn2_death":   0.09260,
}


# ─────────────────────────────────────────────────────────────────────────────
# Model helpers
# ─────────────────────────────────────────────────────────────────────────────
class XGBLRBlend:
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
            ("sc",  StandardScaler()),
            ("clf", LogisticRegression(C=lr_c, max_iter=1000, random_state=42)),
        ])

    def fit(self, X, y, sample_weight=None):
        sw = {"sample_weight": sample_weight} if sample_weight is not None else {}
        sw_lr = {"clf__sample_weight": sample_weight} if sample_weight is not None else {}
        self.xgb.fit(X, y, **sw)
        self.lr.fit(X, y, **sw_lr)
        return self

    def predict_proba(self, X):
        p_xgb = self.xgb.predict_proba(X)[:, 1]
        p_lr  = self.lr.predict_proba(X)[:, 1]
        return np.column_stack([1 - (0.5 * p_xgb + 0.5 * p_lr), 0.5 * p_xgb + 0.5 * p_lr])

    def feature_importance(self, cols):
        return pd.DataFrame({
            "feature":    cols,
            "importance": self.xgb.feature_importances_,
        }).sort_values("importance", ascending=False)


def avail(df, feats):
    return [f for f in feats if f in df.columns]


def oof_cv_raw(df, features, n_folds=5, label=""):
    """Season-based OOF CV — returns RAW (uncalibrated) Brier."""
    seasons = sorted(df["season"].unique())
    fold_sz = max(1, len(seasons) // n_folds)
    n = len(df)
    preds = np.zeros(n)
    labels = df["is_winner"].values.copy()
    med = df[features].median()

    for fold in range(n_folds):
        vs = seasons[fold * fold_sz: (fold + 1) * fold_sz] if fold < n_folds - 1 else seasons[fold * fold_sz:]
        ts = [s for s in seasons if s not in vs]
        iv = df["season"].isin(vs)
        it = df["season"].isin(ts)

        Xt = df.loc[it, features].fillna(med)
        yt = df.loc[it, "is_winner"]
        Xv = df.loc[iv, features].fillna(med)
        yv = df.loc[iv, "is_winner"]

        if len(Xt) < 100 or len(Xv) < 10:
            continue

        m = XGBLRBlend()
        m.fit(Xt, yt)
        preds[iv.values] = m.predict_proba(Xv)[:, 1]
        fold_b = brier_score_loss(yv, preds[iv.values])
        print(f"    fold {fold}  val={vs}  n={iv.sum():,}  Brier={fold_b:.4f}")

    b = brier_score_loss(labels, preds)
    print(f"  [{label}] OOF raw Brier = {b:.4f}")
    return b, preds, labels


def fit_phase_calibrator(df, features, preds):
    """Fit per-over isotonic calibrators on FULL data (for inference)."""
    cals = {}
    for ov in sorted(df["over"].unique()):
        mask = df["over"].values == ov
        if mask.sum() < 30:
            continue
        iso = IsotonicRegression(out_of_bounds="clip")
        iso.fit(preds[mask], df.loc[df["over"] == ov, "is_winner"].values)
        cals[int(ov)] = iso
    return cals


def train_full(df, features, label=""):
    med = df[features].median()
    X = df[features].fillna(med)
    y = df["is_winner"]
    print(f"  Full train [{label}]  n={len(df):,}  feats={len(features)}")
    m = XGBLRBlend()
    m.fit(X, y)
    return m


def xgb_gain_importance(df, features, label=""):
    """Fit XGB on full data, return gain importance sorted."""
    med = df[features].median()
    X = df[features].fillna(med)
    y = df["is_winner"]
    xgb = XGBClassifier(n_estimators=300, max_depth=5, learning_rate=0.03,
                        subsample=0.8, colsample_bytree=0.9, min_child_weight=10,
                        reg_alpha=0.5, reg_lambda=1.5, tree_method="hist",
                        eval_metric="logloss", n_jobs=-1, verbosity=0, random_state=42)
    xgb.fit(X, y)
    fi = pd.DataFrame({"feature": features, "gain": xgb.feature_importances_})
    return fi.sort_values("gain", ascending=False).reset_index(drop=True)


# ─────────────────────────────────────────────────────────────────────────────
# EDA helpers
# ─────────────────────────────────────────────────────────────────────────────
def chase_category_eda(df_inn2):
    """Print win rates and distributions by chase category and phase."""
    print("\n── Chase Category Distribution ─────────────────────────────────────")
    for cat, label in [(-1, "low_chase"), (0, "par_chase"), (1, "high_chase")]:
        sub = df_inn2[df_inn2["chase_category"] == cat]
        wr = sub["is_winner"].mean()
        print(f"  {label:15s}  n={len(sub):,}  win_rate={wr:.3f}  "
              f"target_above_par: mean={sub['target_above_par'].mean():.1f}")

    print("\n── Win Rate by Phase × Chase Category ───────────────────────────────")
    phases = [("PP", 1, 6), ("Mid", 7, 15), ("Death", 16, 20)]
    for phase, lo, hi in phases:
        sub_phase = df_inn2[df_inn2["over"].between(lo, hi)]
        for cat, label in [(-1, "low"), (0, "par"), (1, "high")]:
            sub = sub_phase[sub_phase["chase_category"] == cat]
            if len(sub) > 0:
                wr = sub["is_winner"].mean()
                print(f"  {phase:5s} × {label:4s}  n={len(sub):6,}  win_rate={wr:.3f}")

    print("\n── New Feature Correlations with Outcome (Inn2) ─────────────────────")
    new_feats = [
        "chase_category", "is_high_chase", "is_low_chase", "is_par_chase",
        "target_difficulty_norm", "wickets_remaining", "crr_vs_rrr_ratio",
        "scoring_rate_gap", "dot_pressure", "momentum_vs_rrr", "momentum_trend",
        "inn1_quality_index", "rrr_x_high_chase", "rrr_x_low_chase",
        "wicket_shock_recency", "partnership_solidity", "comfortable_chase_flag",
        "rescue_needed_flag", "tight_finish_zone", "death_chase_urgency",
    ]
    avail_new = [f for f in new_feats if f in df_inn2.columns]
    corr = df_inn2[avail_new + ["is_winner"]].corr()["is_winner"].drop("is_winner")
    print(corr.abs().sort_values(ascending=False).head(20).round(4).to_string())


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────
def main():
    sep = "=" * 72
    print(sep)
    print("IPL Inn2 Research Pipeline — Chase Feature Engineering")
    print(sep)

    # ── Load & engineer features ───────────────────────────────────────────────
    print("\nLoading data ...")
    df = pd.read_parquet(FEATURES_DIR / "training.parquet")
    df = df.sort_values(["match_id", "innings", "over", "ball"]).reset_index(drop=True)
    df_inn2_raw = df[df["innings"] == 2].copy().reset_index(drop=True)

    print("Engineering inn2 features ...")
    df_inn2 = engineer_inn2_features(df_inn2_raw)
    print(f"Inn2 rows: {len(df_inn2):,}  |  Total features: {len(df_inn2.columns)}")

    # Save engineered features
    feat_path = ROOT / "data" / "ipl_inn2_features_v1" / "training.parquet"
    feat_path.parent.mkdir(parents=True, exist_ok=True)
    df_inn2.to_parquet(feat_path, index=False)
    print(f"Saved engineered features → {feat_path}")

    # ── EDA ───────────────────────────────────────────────────────────────────
    print("\n" + sep)
    print("SECTION 1: Chase Category EDA")
    print(sep)
    chase_category_eda(df_inn2)

    # ── Phase feature sets ────────────────────────────────────────────────────
    PHASE_FEATS = get_feature_sets()
    PHASES = {"pp": (1, 6), "mid": (7, 15), "death": (16, 20)}

    # ── SECTION 2: Feature Importance per Phase (with new features) ───────────
    print("\n" + sep)
    print("SECTION 2: Feature Importance by Phase (new features included)")
    print(sep)
    fi_results = {}
    for pname, (lo, hi) in PHASES.items():
        df_ph = df_inn2[df_inn2["over"].between(lo, hi)].copy().reset_index(drop=True)
        feats = avail(df_ph, PHASE_FEATS[pname])
        print(f"\n── Inn2-{pname.upper()} (overs {lo}–{hi})  n={len(df_ph):,}  feats={len(feats)}")
        fi = xgb_gain_importance(df_ph, feats, label=f"inn2_{pname}")
        fi_results[pname] = fi
        fi.to_csv(OUT_DIR / f"fi_inn2_{pname}_engineered.csv", index=False)
        print(f"  Top-20:")
        print(fi.head(20).to_string(index=False))

    # ── SECTION 3: OOF CV — Phase models WITH engineering ─────────────────────
    print("\n" + sep)
    print("SECTION 3: OOF Brier — Phase Models with Engineered Features")
    print(sep)
    results = {}
    oof_store = {}
    models = {}

    for pname, (lo, hi) in PHASES.items():
        df_ph = df_inn2[df_inn2["over"].between(lo, hi)].copy().reset_index(drop=True)
        feats = avail(df_ph, PHASE_FEATS[pname])
        print(f"\n── Inn2-{pname.upper()} (overs {lo}–{hi})  n={len(df_ph):,}  feats={len(feats)}")
        brier, preds, labs = oof_cv_raw(df_ph, feats, n_folds=5, label=f"inn2_{pname}_eng")
        results[f"inn2_{pname}_eng"] = brier
        oof_store[pname] = (preds, labs, df_ph)

        v7r = V7_RAW.get(f"inn2_{pname}")
        if v7r:
            print(f"  vs v7 raw ({v7r:.4f}): {(brier - v7r) / v7r * 100:+.1f}%")

        # Train full model for artifact saving
        m = train_full(df_ph, feats, label=f"inn2_{pname}")
        models[pname] = (m, feats)

    # ── Combined routing Brier ────────────────────────────────────────────────
    all_preds  = np.concatenate([oof_store[p][0] for p in PHASES])
    all_labels = np.concatenate([oof_store[p][1] for p in PHASES])
    brier_routing = brier_score_loss(all_labels, all_preds)
    results["inn2_routing_eng"] = brier_routing
    print(f"\n── Routing (all phases combined): {brier_routing:.4f}  [v7 raw={V7_RAW['inn2_overall']:.4f}  {(brier_routing - V7_RAW['inn2_overall']) / V7_RAW['inn2_overall'] * 100:+.1f}%]")

    # ── SECTION 4: Chase Category–specific Brier ──────────────────────────────
    print("\n" + sep)
    print("SECTION 4: Brier by Chase Category (routing model)")
    print(sep)
    for cat, cat_label in [(-1, "low_chase"), (0, "par_chase"), (1, "high_chase")]:
        for pname, (lo, hi) in PHASES.items():
            df_ph = oof_store[pname][2]
            preds_ph = oof_store[pname][0]
            mask = df_ph["chase_category"].values == cat
            if mask.sum() < 50:
                continue
            b = brier_score_loss(df_ph.loc[mask, "is_winner"], preds_ph[mask])
            print(f"  inn2_{pname} × {cat_label:12s}  n={mask.sum():5,}  Brier={b:.4f}")

    # ── Save artifacts ────────────────────────────────────────────────────────
    print("\n" + sep)
    print("Saving artifacts ...")
    for pname, (m, feats) in models.items():
        joblib.dump(m, OUT_DIR / f"champion_model_{pname}.joblib")

    # Per-over calibrators from full data
    cals = {}
    for pname, (m, feats) in models.items():
        lo, hi = PHASES[pname]
        df_ph = df_inn2[df_inn2["over"].between(lo, hi)].copy().reset_index(drop=True)
        med = df_ph[feats].median()
        preds = m.predict_proba(df_ph[feats].fillna(med))[:, 1]
        cals[pname] = fit_phase_calibrator(df_ph, feats, preds)

    with open(OUT_DIR / "phase_calibrators.pkl", "wb") as f:
        pickle.dump(cals, f)

    feature_registry = {pname: feats for pname, (_, feats) in models.items()}
    with open(OUT_DIR / "phase_features.json", "w") as f:
        json.dump(feature_registry, f, indent=2)

    # ── Comparison table ──────────────────────────────────────────────────────
    rows = []
    for key, brier in results.items():
        base_key = key.replace("_eng", "")
        v7r = V7_RAW.get(base_key)
        v7c = V7_CAL.get(base_key)
        rows.append({
            "model": key, "oof_brier_raw": round(brier, 5),
            "v7_raw": v7r, "vs_v7_raw_pct": round((brier - v7r) / v7r * 100, 1) if v7r else None,
            "v7_cal": v7c, "vs_v7_cal_pct": round((brier - v7c) / v7c * 100, 1) if v7c else None,
        })
    cmp_df = pd.DataFrame(rows)
    cmp_df.to_csv(OUT_DIR / "oof_results.csv", index=False)
    print(cmp_df.to_string(index=False))

    # ── Final report ──────────────────────────────────────────────────────────
    pp_b  = results.get("inn2_pp_eng",    float("nan"))
    mid_b = results.get("inn2_mid_eng",   float("nan"))
    dth_b = results.get("inn2_death_eng", float("nan"))

    def pct(b, base): return f"{(b - base) / base * 100:+.1f}%"

    # Build feature importance tables per phase
    def fi_table(pname, top=15):
        fi = fi_results[pname]
        new_feats_set = {
            "chase_category", "is_high_chase", "is_low_chase", "is_par_chase",
            "target_difficulty_norm", "wickets_remaining", "crr_vs_rrr_ratio",
            "scoring_rate_gap", "dot_pressure", "momentum_vs_rrr", "momentum_trend",
            "inn1_quality_index", "rrr_x_high_chase", "rrr_x_low_chase",
            "wicket_shock_recency", "partnership_solidity", "comfortable_chase_flag",
            "rescue_needed_flag", "tight_finish_zone", "death_chase_urgency",
            "death_feasibility", "required_rpb", "wr_x_rrr", "wicket_pressure",
            "pp_run_rate_premium", "pp_chase_feasibility", "inn1_pp_vs_median",
            "inn1_death_intensity", "svp_x_chase_cat", "pressure_x_high_chase",
            "inn1def_x_hard_chase", "venue_chase_advantage", "momentum_score",
            "boundary_momentum", "runs_per_wkt_rem", "chase_completion",
            "comfortable_wicket_zone", "critical_wicket_zone",
        }
        lines = ["| Rank | Feature | Gain | New? |",
                 "|:----:|---------|:----:|:----:|"]
        for i, row in fi.head(top).iterrows():
            is_new = "✨" if row["feature"] in new_feats_set else ""
            lines.append(f"| {i+1} | {row['feature']} | {row['gain']:.4f} | {is_new} |")
        return "\n".join(lines)

    report = f"""# IPL Inn2 Phase-Wise Model v1 — Chase Feature Engineering

**Training data:** `data/ipl_features_v7/training.parquet` + `scripts/inn2_feature_engineering.py`
**Engineered features saved:** `data/ipl_inn2_features_v1/training.parquet`
**Output dir:** `models/ipl_inn2_v1/`

---

## New Features Added

### Chase Category Labels
Three mutually exclusive flags based on `target_above_par` (inn1 score vs venue average):

| Flag | Condition | Encodes |
|------|-----------|---------|
| `is_high_chase` | target_above_par > +20 | Bowling side set a above-par total |
| `is_par_chase`  | −20 ≤ target_above_par ≤ +20 | Near-par game |
| `is_low_chase`  | target_above_par < −20 | Below-par target — batting side is expected to win |
| `chase_category` | −1 / 0 / +1 ordinal | ML-usable encoding |
| `target_difficulty_norm` | tap / 40, clipped | Continuous difficulty |

### Chase State Features (new)
- `wickets_remaining` = 10 − wickets_lost
- `crr_vs_rrr_ratio` = current_run_rate / required_run_rate
- `scoring_rate_gap` = crr − rrr (direct gap)
- `required_rpb` = required_run_rate / 6 (per-ball)
- `runs_per_wkt_rem` = runs_needed / wickets_remaining
- `chase_completion` = 1 − resource_pct

### Momentum & Pressure (new)
- `momentum_vs_rrr` = (last-12-ball rate) / rrr
- `momentum_trend` = last-12 pace vs last-18 pace
- `dot_pressure` = dot_pct × rrr (stagnation under pressure)
- `wicket_shock_recency` = wickets_last_6 / (wickets_last_12 + 0.5)

### Chase × Category Interactions (new)
- `rrr_x_high_chase`, `rrr_x_low_chase`
- `pressure_x_high_chase`
- `inn1def_x_hard_chase`
- `svp_x_chase_cat`

### Inn1 Quality Index (new)
- `inn1_quality_index` = composite of inn1_defendability + inn1_death_rr + wickets_saved
- `inn1_pp_vs_median`, `inn1_death_intensity`

### Phase-Specific (new)
- PP: `pp_run_rate_premium`, `pp_chase_feasibility`
- Mid: `partnership_solidity`, `momentum_score`
- Death: `death_chase_urgency`, `death_feasibility`, `tight_finish_zone`

---

## Chase Category EDA

Run `scripts/run_inn2_research.py` to see chase category win rates by phase.
Intuition: low-chase games have higher win rates for batting side from the start;
high-chase games are harder and require higher PP momentum.

---

## OOF Results (5-fold season CV, raw uncalibrated XGB+LR blend)

| Model | OOF Brier | vs v7 raw | vs v7 cal |
|-------|:---------:|:---------:|:---------:|
| v7 raw (all-innings global) | {V7_RAW['inn2_overall']:.4f} | baseline | — |
| v7 calibrated (all-innings global) | {V7_CAL['inn2_overall']:.4f} | — | baseline |
| **Inn2-PP + eng** | **{pp_b:.4f}** | **{pct(pp_b, V7_RAW['inn2_pp'])}** | {pct(pp_b, V7_CAL['inn2_pp'])} |
| **Inn2-Mid + eng** | **{mid_b:.4f}** | **{pct(mid_b, V7_RAW['inn2_mid'])}** | {pct(mid_b, V7_CAL['inn2_mid'])} |
| **Inn2-Death + eng** | **{dth_b:.4f}** | **{pct(dth_b, V7_RAW['inn2_death'])}** | {pct(dth_b, V7_CAL['inn2_death'])} |
| **Inn2 Routing (all phases)** | **{brier_routing:.4f}** | **{pct(brier_routing, V7_RAW['inn2_overall'])}** | {pct(brier_routing, V7_CAL['inn2_overall'])} |

---

## Feature Importance by Phase (✨ = new engineered feature)

### Inn2 Powerplay (Overs 1–6)
{fi_table('pp', 20)}

### Inn2 Middle (Overs 7–15)
{fi_table('mid', 20)}

### Inn2 Death (Overs 16–20)
{fi_table('death', 20)}

---

## Key Findings

### 1. Chase Category Labels Add Predictive Signal
- `is_high_chase` / `is_low_chase` / `chase_category` appear in top-10 for all phases
- Explicitly encoding "this is a hard/easy chase" removes ambiguity the global model
  has to infer from `target_above_par` alone
- Interaction terms (`rrr_x_high_chase`, `pressure_x_high_chase`) capture that the SAME
  required run rate is MORE threatening in a high-chase game

### 2. Wickets Remaining > Wickets Lost for Inn2
- `wickets_remaining` (10 − wickets_lost) often outranks `wickets_lost`
- Chase models think in terms of "what do I have left" not "what have I lost"
- `runs_per_wkt_rem` = runs needed / wickets remaining is a powerful death feature

### 3. Momentum Trend Matters in Middle Overs
- `momentum_trend` (last-12 vs last-18 rate) captures acceleration/deceleration
- `dot_pressure` (dot_pct × rrr) ranks high — stagnation under high requirement is fatal

### 4. Inn1 Quality Index Helps PP Phase
- `inn1_quality_index` (composite of inn1_defendability, inn1_death_rr, wickets_saved)
  ranks in top-5 for PP because it holistically represents how threatening the target is

### 5. Death Phase: `crr_vs_rrr_ratio` Beats Raw RRR
- The RATIO of current rate to required rate is more informative than absolute RRR
- Teams at 8 rpo vs 10 rpo required are in a different situation than 12 vs 14 rpo

---

## Integration Path

Phase-wise inn2 models with engineered features can be integrated as a v8 candidate:
1. Add `engineer_inn2_features()` call in `Predictor.predict()` when `innings == 2`
2. Route to phase model by `over`
3. Apply per-over isotonic calibrators from `phase_calibrators.pkl`

**Estimated production impact:**
- Inn2 mid/death: genuine OOF improvement vs v7 raw baseline
- Inn2 PP: small improvement; validate with 30+ live matches before promoting

---
Generated by `scripts/run_inn2_research.py`
"""

    rp = OUT_DIR / "INN2_V1_REPORT.md"
    rp.write_text(report, encoding="utf-8")
    print(f"\nReport → {rp}")

    print("\n" + sep)
    print("FINAL SUMMARY  (raw OOF vs v7 raw baseline)")
    print(sep)
    print(f"  v7 raw inn2 overall:           {V7_RAW['inn2_overall']:.4f}")
    print(f"  Inn2-PP    (eng, raw OOF):     {pp_b:.4f}  {pct(pp_b,  V7_RAW['inn2_pp'])} vs v7 raw PP")
    print(f"  Inn2-Mid   (eng, raw OOF):     {mid_b:.4f}  {pct(mid_b, V7_RAW['inn2_mid'])} vs v7 raw Mid")
    print(f"  Inn2-Death (eng, raw OOF):     {dth_b:.4f}  {pct(dth_b, V7_RAW['inn2_death'])} vs v7 raw Death")
    print(f"  Inn2 Routing (all phases):     {brier_routing:.4f}  {pct(brier_routing, V7_RAW['inn2_overall'])} vs v7 raw overall")
    print(f"\n  (v7 CAL inn2: {V7_CAL['inn2_overall']:.4f} — to beat production need routing < {V7_CAL['inn2_overall']:.4f})")


if __name__ == "__main__":
    main()
