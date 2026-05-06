"""
Inn2 Phase Model — Calibrated OOF Evaluation
==============================================
Runs proper 5-fold season-based OOF with per-over isotonic calibration
(same method as bbl-pipeline analyze-oof / brier_optimized) for each
inn2 phase model (PP / Mid / Death).

Outputs
-------
  models/ipl_inn2_v1/
    oof_calibrated_results.csv    — per-phase calibrated Brier vs v7
    phase_oof_calibrators.pkl     — per-over isotonic calibrators for inference
    INN2_V1_CALIBRATION_REPORT.md — formatted comparison table
"""

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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from inn2_feature_engineering import engineer_inn2_features

FEATURES_DIR = ROOT / "data" / "ipl_features_v7"
INN2_DIR     = ROOT / "data" / "ipl_inn2_features_v1"
OUT_DIR      = ROOT / "models" / "ipl_inn2_v1"

# ── Baselines (from models/ipl_v7/oof_calibration_results.csv) ────────────────
V7_RAW = {
    "inn2_pp":    0.18299,
    "inn2_mid":   0.14667,
    "inn2_death": 0.09617,
    "inn2_all":   0.14351,
}
V7_CAL = {
    "inn2_pp":    0.18026,
    "inn2_mid":   0.14389,
    "inn2_death": 0.09260,
    "inn2_all":   0.14054,
}


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

    def fit(self, X, y):
        self.xgb.fit(X, y)
        self.lr.fit(X, y)
        return self

    def predict_proba(self, X):
        p_xgb = self.xgb.predict_proba(X)[:, 1]
        p_lr  = self.lr.predict_proba(X)[:, 1]
        return 0.5 * p_xgb + 0.5 * p_lr


def season_oof(df: pd.DataFrame, features: list, n_folds: int = 5) -> tuple:
    """
    Season-based OOF. Returns (raw_oof_preds, labels) arrays.
    No calibration inside folds — calibration is applied AFTER on full OOF.
    """
    seasons = sorted(df["season"].unique())
    fold_size = max(1, len(seasons) // n_folds)

    oof_preds = np.zeros(len(df))
    labels = df["is_winner"].values.copy()

    for fold in range(n_folds):
        if fold < n_folds - 1:
            val_seasons = seasons[fold * fold_size: (fold + 1) * fold_size]
        else:
            val_seasons = seasons[fold * fold_size:]
        train_seasons = [s for s in seasons if s not in val_seasons]

        idx_tr  = df["season"].isin(train_seasons)
        idx_val = df["season"].isin(val_seasons)
        if idx_tr.sum() < 100 or idx_val.sum() < 10:
            continue

        med = df.loc[idx_tr, features].median()
        X_tr  = df.loc[idx_tr,  features].fillna(med)
        X_val = df.loc[idx_val, features].fillna(med)
        y_tr  = df.loc[idx_tr,  "is_winner"]

        model = XGBLRBlend()
        model.fit(X_tr, y_tr)
        oof_preds[idx_val.values] = model.predict_proba(X_val)

        raw_b = brier_score_loss(df.loc[idx_val, "is_winner"], oof_preds[idx_val.values])
        print(f"      Fold {fold}: val={val_seasons}, n={idx_val.sum():,}, raw_Brier={raw_b:.4f}")

    return oof_preds, labels


def fit_per_over_calibrators(oof_preds: np.ndarray, labels: np.ndarray, overs: np.ndarray) -> dict:
    """
    Fit per-over isotonic calibrators on OOF predictions.
    Same logic as OOFAnalyzer.brier_optimized.
    Returns {over: IsotonicRegression}.
    """
    calibrators = {}
    for ov in sorted(np.unique(overs)):
        mask = overs == ov
        if mask.sum() < 30:
            continue
        iso = IsotonicRegression(out_of_bounds="clip")
        iso.fit(oof_preds[mask], labels[mask])
        calibrators[int(ov)] = iso
    return calibrators


def apply_per_over_calibration(oof_preds: np.ndarray, overs: np.ndarray, calibrators: dict) -> np.ndarray:
    cal_preds = oof_preds.copy()
    for ov, iso in calibrators.items():
        mask = overs == ov
        if mask.sum() > 0:
            cal_preds[mask] = iso.predict(oof_preds[mask])
    return cal_preds


def fit_innings_phase_calibrators(oof_preds: np.ndarray, labels: np.ndarray,
                                   phases: np.ndarray) -> dict:
    """Calibrate per phase (pp / mid / death). Returns {phase: IsotonicRegression}."""
    calibrators = {}
    for ph in np.unique(phases):
        mask = phases == ph
        if mask.sum() < 50:
            continue
        iso = IsotonicRegression(out_of_bounds="clip")
        iso.fit(oof_preds[mask], labels[mask])
        calibrators[str(ph)] = iso
    return calibrators


def main():
    print("=" * 70)
    print("Inn2 Phase Model — Calibrated OOF Evaluation")
    print("=" * 70)

    # ── Load base features ────────────────────────────────────────────────────
    print("\nLoading ipl_features_v7 ...")
    df_base = pd.read_parquet(FEATURES_DIR / "training.parquet")
    df_base = df_base.sort_values(["match_id", "innings", "over", "ball"]).reset_index(drop=True)
    df_inn2_base = df_base[df_base["innings"] == 2].copy().reset_index(drop=True)
    print(f"Inn2 base rows: {len(df_inn2_base):,}")

    # ── Load / build engineered features ─────────────────────────────────────
    eng_path = INN2_DIR / "training.parquet"
    if eng_path.exists():
        print(f"Loading engineered features from {eng_path} ...")
        df_eng = pd.read_parquet(eng_path)
        df_eng = df_eng.sort_values(["match_id", "innings", "over", "ball"]).reset_index(drop=True)
        print(f"Engineered rows: {len(df_eng):,}  cols: {df_eng.shape[1]}")
    else:
        print("Engineered features not found — running engineer_inn2_features() ...")
        df_eng = engineer_inn2_features(df_inn2_base)
        df_eng = df_eng.sort_values(["match_id", "innings", "over", "ball"]).reset_index(drop=True)
        print(f"Engineered: {df_eng.shape}")

    # ── Phase feature sets (from saved phase_features.json) ──────────────────
    feat_json = OUT_DIR / "phase_features.json"
    with open(feat_json) as f:
        phase_feature_sets = json.load(f)
    # Remove the unified entry
    phase_feature_sets.pop("inn2_unified", None)

    # Phase → over range
    PHASE_OVER = {
        "pp":    (1,  6,  "pp"),
        "mid":   (7,  15, "mid"),
        "death": (16, 20, "death"),
    }

    phase_results = {}
    all_phase_calibrators = {}   # for inference: {phase: {over: IsotonicRegression}}
    oof_rows_all = []            # for routing Brier

    for phase_key, (ov_lo, ov_hi, label) in PHASE_OVER.items():
        print(f"\n{'─'*60}")
        print(f"Phase: inn2_{label} (overs {ov_lo}–{ov_hi})")

        df_phase = df_eng[
            (df_eng["innings"] == 2) &
            (df_eng["over"] >= ov_lo) &
            (df_eng["over"] <= ov_hi)
        ].copy().reset_index(drop=True)

        feature_list = [f for f in phase_feature_sets[phase_key] if f in df_phase.columns]
        print(f"  Rows: {len(df_phase):,}  |  Features: {len(feature_list)}")

        # ── OOF raw ───────────────────────────────────────────────────────────
        print("  Running OOF CV (5-fold season-based) ...")
        oof_preds, labels = season_oof(df_phase, feature_list)

        brier_raw = brier_score_loss(labels, oof_preds)
        print(f"  OOF Brier (raw):   {brier_raw:.4f}  "
              f"vs v7_raw={V7_RAW['inn2_'+label]:.4f}  "
              f"({(brier_raw-V7_RAW['inn2_'+label])/V7_RAW['inn2_'+label]*100:+.1f}%)")

        # ── Per-over calibration (brier_optimized) ────────────────────────────
        overs = df_phase["over"].values
        cal_per_over = fit_per_over_calibrators(oof_preds, labels, overs)
        preds_cal = apply_per_over_calibration(oof_preds, overs, cal_per_over)
        brier_cal_perover = brier_score_loss(labels, preds_cal)

        # How many overs had enough samples for a calibrator?
        print(f"  Per-over isotonic: {len(cal_per_over)} calibrators fitted")
        print(f"  OOF Brier (per-over cal):  {brier_cal_perover:.4f}  "
              f"vs v7_cal={V7_CAL['inn2_'+label]:.4f}  "
              f"({(brier_cal_perover-V7_CAL['inn2_'+label])/V7_CAL['inn2_'+label]*100:+.1f}%)")

        # ── Innings×Phase calibration (single isotonic per phase) ────────────
        iso_phase = IsotonicRegression(out_of_bounds="clip")
        iso_phase.fit(oof_preds, labels)
        preds_cal_phase = iso_phase.predict(oof_preds)
        brier_cal_phase = brier_score_loss(labels, preds_cal_phase)
        print(f"  OOF Brier (phase-isotonic): {brier_cal_phase:.4f}")

        phase_results[phase_key] = {
            "raw":       brier_raw,
            "cal_perover": brier_cal_perover,
            "cal_phase":  brier_cal_phase,
            "v7_raw":    V7_RAW["inn2_" + label],
            "v7_cal":    V7_CAL["inn2_" + label],
            "n_rows":    len(df_phase),
        }
        all_phase_calibrators[phase_key] = {
            "per_over":  cal_per_over,
            "phase_iso": iso_phase,
        }
        oof_rows_all.append((oof_preds, preds_cal, labels))

    # ── Routing Brier (all phases combined) ───────────────────────────────────
    print(f"\n{'─'*60}")
    all_raw  = np.concatenate([r[0] for r in oof_rows_all])
    all_cal  = np.concatenate([r[1] for r in oof_rows_all])
    all_lbl  = np.concatenate([r[2] for r in oof_rows_all])

    routing_raw = brier_score_loss(all_lbl, all_raw)
    routing_cal = brier_score_loss(all_lbl, all_cal)
    print(f"Inn2 Routing OOF Brier (raw):      {routing_raw:.4f}  vs v7_raw {V7_RAW['inn2_all']:.4f}  "
          f"({(routing_raw-V7_RAW['inn2_all'])/V7_RAW['inn2_all']*100:+.1f}%)")
    print(f"Inn2 Routing OOF Brier (cal):      {routing_cal:.4f}  vs v7_cal {V7_CAL['inn2_all']:.4f}  "
          f"({(routing_cal-V7_CAL['inn2_all'])/V7_CAL['inn2_all']*100:+.1f}%)")

    # ── Save calibrators ──────────────────────────────────────────────────────
    cal_path = OUT_DIR / "phase_oof_calibrators.pkl"
    with open(cal_path, "wb") as f:
        pickle.dump(all_phase_calibrators, f)
    print(f"\nCalibrators saved → {cal_path}")

    # ── Save results CSV ──────────────────────────────────────────────────────
    rows = []
    for phase_key, r in phase_results.items():
        label = phase_key
        rows.append({
            "phase":         f"inn2_{label}",
            "n_rows":        r["n_rows"],
            "raw_oof":       round(r["raw"], 5),
            "cal_perover":   round(r["cal_perover"], 5),
            "cal_phase_iso": round(r["cal_phase"], 5),
            "v7_raw":        r["v7_raw"],
            "v7_cal":        r["v7_cal"],
            "vs_v7_raw_pct": round((r["raw"] - r["v7_raw"]) / r["v7_raw"] * 100, 1),
            "vs_v7_cal_perover_pct": round(
                (r["cal_perover"] - r["v7_cal"]) / r["v7_cal"] * 100, 1),
        })
    rows.append({
        "phase": "inn2_routing",
        "n_rows": len(all_lbl),
        "raw_oof": round(routing_raw, 5),
        "cal_perover": round(routing_cal, 5),
        "cal_phase_iso": None,
        "v7_raw": V7_RAW["inn2_all"],
        "v7_cal": V7_CAL["inn2_all"],
        "vs_v7_raw_pct": round((routing_raw - V7_RAW["inn2_all"]) / V7_RAW["inn2_all"] * 100, 1),
        "vs_v7_cal_perover_pct": round((routing_cal - V7_CAL["inn2_all"]) / V7_CAL["inn2_all"] * 100, 1),
    })

    df_res = pd.DataFrame(rows)
    csv_path = OUT_DIR / "oof_calibrated_results.csv"
    df_res.to_csv(csv_path, index=False)
    print(f"Results CSV → {csv_path}")
    print("\n" + df_res.to_string(index=False))

    # ── Report ────────────────────────────────────────────────────────────────
    pp  = phase_results.get("pp",    {})
    mid = phase_results.get("mid",   {})
    dth = phase_results.get("death", {})

    def _pct(a, b): return f"{(a-b)/b*100:+.1f}%"

    report = f"""# IPL Inn2 Phase Models — Calibrated OOF Report

## Summary

Phase-specific inn2 models (PP / Mid / Death) with per-over isotonic calibration
vs v7 global model (brier_optimized calibrated).

### OOF Brier Comparison

| Phase | Rows | Raw OOF | Cal (per-over) | v7 Raw | v7 Cal | vs v7-raw | vs v7-cal |
|-------|-----:|:-------:|:--------------:|:------:|:------:|:---------:|:---------:|
| Inn2-PP    | {pp.get('n_rows',0):,} | {pp.get('raw',0):.4f} | **{pp.get('cal_perover',0):.4f}** | {V7_RAW['inn2_pp']:.4f} | {V7_CAL['inn2_pp']:.4f} | {_pct(pp.get('raw',0),V7_RAW['inn2_pp'])} | {_pct(pp.get('cal_perover',0),V7_CAL['inn2_pp'])} |
| Inn2-Mid   | {mid.get('n_rows',0):,} | {mid.get('raw',0):.4f} | **{mid.get('cal_perover',0):.4f}** | {V7_RAW['inn2_mid']:.4f} | {V7_CAL['inn2_mid']:.4f} | {_pct(mid.get('raw',0),V7_RAW['inn2_mid'])} | {_pct(mid.get('cal_perover',0),V7_CAL['inn2_mid'])} |
| Inn2-Death | {dth.get('n_rows',0):,} | {dth.get('raw',0):.4f} | **{dth.get('cal_perover',0):.4f}** | {V7_RAW['inn2_death']:.4f} | {V7_CAL['inn2_death']:.4f} | {_pct(dth.get('raw',0),V7_RAW['inn2_death'])} | {_pct(dth.get('cal_perover',0),V7_CAL['inn2_death'])} |
| **Inn2 Routing** | {len(all_lbl):,} | {routing_raw:.4f} | **{routing_cal:.4f}** | {V7_RAW['inn2_all']:.4f} | {V7_CAL['inn2_all']:.4f} | {_pct(routing_raw,V7_RAW['inn2_all'])} | **{_pct(routing_cal,V7_CAL['inn2_all'])}** |

### Key Insight: Calibration Gap

Calibration closes the gap between raw and v7-cal baselines:

| Phase | Raw vs v7-cal | Cal vs v7-cal | Calibration Gain |
|-------|:-------------:|:-------------:|:----------------:|
| PP    | {_pct(pp.get('raw',0),V7_CAL['inn2_pp'])} | {_pct(pp.get('cal_perover',0),V7_CAL['inn2_pp'])} | {(pp.get('raw',0)-pp.get('cal_perover',0))/V7_CAL['inn2_pp']*100:+.1f}pp |
| Mid   | {_pct(mid.get('raw',0),V7_CAL['inn2_mid'])} | {_pct(mid.get('cal_perover',0),V7_CAL['inn2_mid'])} | {(mid.get('raw',0)-mid.get('cal_perover',0))/V7_CAL['inn2_mid']*100:+.1f}pp |
| Death | {_pct(dth.get('raw',0),V7_CAL['inn2_death'])} | {_pct(dth.get('cal_perover',0),V7_CAL['inn2_death'])} | {(dth.get('raw',0)-dth.get('cal_perover',0))/V7_CAL['inn2_death']*100:+.1f}pp |

### Production Path → ipl_v11

- **Inn1**: Keep v7 global model (best overall: 0.18099)  
- **Inn2**: Route to phase model by over:
  - Overs 1–6 → inn2_pp model + per-over calibrator
  - Overs 7–15 → inn2_mid model + per-over calibrator
  - Overs 16–20 → inn2_death model + per-over calibrator

Calibrators saved: `models/ipl_inn2_v1/phase_oof_calibrators.pkl`
"""

    rpt_path = OUT_DIR / "INN2_V1_CALIBRATION_REPORT.md"
    rpt_path.write_text(report, encoding="utf-8")
    print(f"\nReport → {rpt_path}")
    print("\nDone. ✓")


if __name__ == "__main__":
    main()
