"""
PSL Per-Over & Per-Segment Temperature Scaling (OOF)
=====================================================
Replaces the per-over isotonic calibrators in models/psl_v2 with
temperature scalers fitted on the full OOF training data (78k rows).

Why OOF instead of betx21 (15 matches)?
  Each over has ~1,900 training rows → stable 1-parameter fit.
  betx21 has ~15 obs/over → too sparse for LOMO to generalise.

Methods compared on 5-fold OOF:
  1. isotonic_per_over   — existing brier_optimized (IsotonicRegression)
  2. temp_per_over       — TemperatureScaler per inn×over
  3. temp_per_phase      — TemperatureScaler per inn×phase (6 calibrators)
  4. platt_per_inn       — Platt per innings (2 calibrators)
  5. temp_per_inn        — Temperature per innings (2 calibrators)
  6. temp_global         — Single global temperature

Winner replaces per_over_calibrators in models/psl_v2/isotonic_calibrator.pkl
and the betx21 comparison is re-run with the new calibrators.
"""
import sys, warnings, joblib
warnings.filterwarnings("ignore")
sys.path.insert(0, "src")

import numpy as np
import pandas as pd
from pathlib import Path
from scipy.optimize import minimize
from scipy.special import logit, expit
from sklearn.model_selection import KFold
from sklearn.isotonic import IsotonicRegression

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TRAIN_PARQUET = PROJECT_ROOT / "data" / "psl_features_v1" / "training.parquet"
MODEL_DIR     = PROJECT_ROOT / "models" / "psl_v2"
BETX21_PARQUET = PROJECT_ROOT / "data" / "psl_betx21_model_vs_market.parquet"

N_SPLITS = 5
MIN_OBS  = 30   # minimum per segment for calibrator to be fitted

# ── helpers ───────────────────────────────────────────────────────────────

def brier(p, y): return float(np.mean((p - y) ** 2))

def ece(p, y, n=10):
    edges = np.linspace(0, 1, n + 1); t = len(p); acc = 0.0
    for i in range(n):
        m = (p >= edges[i]) & (p < edges[i + 1] if i < n - 1 else p <= edges[i + 1])
        if m.sum(): acc += (m.sum() / t) * abs(p[m].mean() - y[m].mean())
    return acc

def phase(o):
    if o <= 6:    return "powerplay"
    elif o <= 15: return "middle"
    else:         return "death"


class TemperatureScaler:
    """Single-parameter temperature scaler (NLL-optimised)."""
    def __init__(self):
        self.T = 1.0

    def fit(self, probs, y):
        probs = np.clip(probs, 1e-7, 1 - 1e-7)
        lgt = logit(probs)
        def nll(T):
            p = expit(lgt / T[0])
            p = np.clip(p, 1e-7, 1 - 1e-7)
            return -np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))
        res = minimize(nll, [1.0], bounds=[(0.1, 10.0)], method="L-BFGS-B")
        self.T = float(res.x[0])
        return self

    def predict(self, probs):
        probs = np.clip(np.asarray(probs, float), 1e-7, 1 - 1e-7)
        return expit(logit(probs) / self.T)


class PlattScaler:
    """Two-parameter Platt scaler: sigmoid(a*logit(p) + b)."""
    def __init__(self):
        self.a = 1.0
        self.b = 0.0

    def fit(self, probs, y):
        probs = np.clip(probs, 1e-7, 1 - 1e-7)
        lgt = logit(probs)
        def nll(params):
            p = expit(params[0] * lgt + params[1])
            p = np.clip(p, 1e-7, 1 - 1e-7)
            return -np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))
        res = minimize(nll, [1.0, 0.0], bounds=[(0.1, 10.0), (-5.0, 5.0)], method="L-BFGS-B")
        self.a, self.b = float(res.x[0]), float(res.x[1])
        return self

    def predict(self, probs):
        probs = np.clip(np.asarray(probs, float), 1e-7, 1 - 1e-7)
        return expit(self.a * logit(probs) + self.b)


def fit_seg_calibrators(CalClass, oof_probs, y, seg_labels, min_obs=MIN_OBS):
    """Fit one CalClass instance per unique segment label."""
    calibrators = {}
    for seg in np.unique(seg_labels):
        mask = seg_labels == seg
        if mask.sum() < min_obs:
            continue
        cal = CalClass()
        cal.fit(oof_probs[mask], y[mask])
        calibrators[seg] = cal
    return calibrators


def apply_seg_calibrators(probs, seg_labels, calibrators, fallback_probs=None):
    """Apply per-segment calibrators; fall back to fallback_probs for missing segs."""
    out = (fallback_probs if fallback_probs is not None else probs).copy()
    for seg, cal in calibrators.items():
        mask = seg_labels == seg
        if mask.sum():
            out[mask] = cal.predict(probs[mask])
    return out


# ── Main ──────────────────────────────────────────────────────────────────

def main():
    print(f"Loading PSL training data from {TRAIN_PARQUET}")
    df = pd.read_parquet(TRAIN_PARQUET)
    print(f"  {len(df):,} rows, {df['innings'].nunique()} innings values")

    from bbl_pipeline.training.trainer import XGBLogRegEnsemble
    model = joblib.load(MODEL_DIR / "champion_model.joblib")
    feature_cols = model.feature_names_in_ if hasattr(model, 'feature_names_in_') else model.selected_features_
    X = df[feature_cols].values
    y = df["is_winner"].values.astype(float)
    innings_col = df["innings"].values
    over_col    = df["over"].values

    seg_inn   = np.array([f"inn{i}" for i in innings_col])
    seg_phase = np.array([f"inn{i}_{phase(o)}" for i, o in zip(innings_col, over_col)])
    seg_over  = np.array([f"inn{i}_over{o}" for i, o in zip(innings_col, over_col)])

    # ── 5-fold OOF predictions ─────────────────────────────────────────────
    print(f"\nGenerating {N_SPLITS}-fold OOF predictions...")
    kf = KFold(n_splits=N_SPLITS, shuffle=True, random_state=42)
    oof_probs = np.zeros(len(df))

    for fold, (tr_idx, val_idx) in enumerate(kf.split(X, y), 1):
        fold_model = XGBLogRegEnsemble()
        fold_model.fit(df[feature_cols].iloc[tr_idx], y[tr_idx])
        oof_probs[val_idx] = fold_model.predict_proba(df[feature_cols].iloc[val_idx])[:, 1]
        b = brier(oof_probs[val_idx], y[val_idx])
        print(f"  Fold {fold}: Brier={b:.4f}")

    b_raw = brier(oof_probs, y)
    print(f"\n  OOF raw Brier: {b_raw:.4f}  ECE: {ece(oof_probs, y):.4f}")

    # ── Fit and evaluate all methods on OOF ────────────────────────────────
    print("\nFitting calibrators on full OOF predictions...")
    results = {}

    # 1. Isotonic per-over (existing baseline)
    iso_per_over = {}
    for seg in np.unique(seg_over):
        mask = seg_over == seg
        if mask.sum() >= MIN_OBS:
            cal = IsotonicRegression(y_min=0.01, y_max=0.99, out_of_bounds="clip")
            cal.fit(oof_probs[mask], y[mask])
            iso_per_over[seg] = cal
    cal_iso_over = apply_seg_calibrators(oof_probs, seg_over, iso_per_over)
    results["1_isotonic_per_over"] = cal_iso_over

    # 2. Temperature per-over
    temp_per_over = fit_seg_calibrators(TemperatureScaler, oof_probs, y, seg_over)
    cal_temp_over = apply_seg_calibrators(oof_probs, seg_over, temp_per_over)
    results["2_temp_per_over"] = cal_temp_over

    # 3. Temperature per phase (6 segs)
    temp_per_phase = fit_seg_calibrators(TemperatureScaler, oof_probs, y, seg_phase)
    cal_temp_phase = apply_seg_calibrators(oof_probs, seg_phase, temp_per_phase)
    results["3_temp_per_phase"] = cal_temp_phase

    # 4. Platt per innings (2 segs)
    platt_per_inn = fit_seg_calibrators(PlattScaler, oof_probs, y, seg_inn)
    cal_platt_inn = apply_seg_calibrators(oof_probs, seg_inn, platt_per_inn)
    results["4_platt_per_inn"] = cal_platt_inn

    # 5. Temperature per innings
    temp_per_inn = fit_seg_calibrators(TemperatureScaler, oof_probs, y, seg_inn)
    cal_temp_inn = apply_seg_calibrators(oof_probs, seg_inn, temp_per_inn)
    results["5_temp_per_inn"] = cal_temp_inn

    # 6. Global temperature
    temp_global = TemperatureScaler().fit(oof_probs, y)
    cal_temp_global = temp_global.predict(oof_probs)
    results["6_temp_global"] = cal_temp_global

    # ── OOF comparison table ───────────────────────────────────────────────
    print(f"\n{'='*72}")
    print(f"  OOF COMPARISON  ({len(df):,} rows, {df['match_id'].nunique()} matches)")
    print(f"  Raw Brier: {b_raw:.4f}  ECE: {ece(oof_probs,y):.4f}")
    print(f"{'='*72}")
    print(f"  {'Method':<28s} {'Brier':>8s} {'vs Raw':>7s} {'ECE':>8s}  {'#cals':>6s}")
    print(f"  {'-'*60}")
    for name, cal in sorted(results.items(), key=lambda x: brier(x[1], y)):
        bc = brier(cal, y)
        ncals = (len(temp_per_over) if "per_over" in name and "temp" in name
                 else len(iso_per_over) if "isotonic" in name
                 else len(temp_per_phase) if "per_phase" in name
                 else len(platt_per_inn) if "platt" in name
                 else len(temp_per_inn) if "per_inn" in name
                 else 1)
        print(f"  {name:<28s} {bc:8.4f} {(bc/b_raw-1)*100:+6.1f}%  {ece(cal,y):8.4f}  {ncals:6d}")

    # Per-segment OOF
    print(f"\n  Per-segment OOF Brier:")
    print(f"  {'Seg':<22s} {'n':>5s} {'raw':>8s} {'iso_ov':>8s} {'tmp_ov':>8s} {'tmp_ph':>8s} {'platt_in':>9s}")
    print(f"  {'-'*68}")
    for inn in [1, 2]:
        for ph in ["powerplay", "middle", "death"]:
            mask = (innings_col == inn) & np.array([phase(o) == ph for o in over_col])
            if mask.sum() < 5: continue
            seg = f"inn{inn}_{ph}"
            print(f"  {seg:<22s} {mask.sum():5d}"
                  f" {brier(oof_probs[mask],y[mask]):8.4f}"
                  f" {brier(cal_iso_over[mask],y[mask]):8.4f}"
                  f" {brier(cal_temp_over[mask],y[mask]):8.4f}"
                  f" {brier(cal_temp_phase[mask],y[mask]):8.4f}"
                  f" {brier(cal_platt_inn[mask],y[mask]):9.4f}")

    # Temperature values fitted
    print(f"\n  Fitted temperatures (per-over, sample):")
    print(f"  {'Segment':<22s} {'T_temp':>8s}  {'direction'}")
    print(f"  {'-'*55}")
    sample_segs = ["inn1_over6", "inn1_over10", "inn1_over15", "inn1_over19",
                   "inn2_over6", "inn2_over10", "inn2_over15", "inn2_over19"]
    for seg in sample_segs:
        if seg in temp_per_over:
            T = temp_per_over[seg].T
            direction = "softer" if T > 1.05 else "sharper" if T < 0.95 else "neutral"
            print(f"  {seg:<22s} {T:8.3f}  {direction}")

    for seg_name, cal_d in [("per-inn", temp_per_inn), ("per-phase", temp_per_phase)]:
        print(f"\n  Temperatures ({seg_name}):")
        for k, v in sorted(cal_d.items()):
            T = v.T
            direction = "softer" if T > 1.05 else "sharper" if T < 0.95 else "neutral"
            print(f"    {k:<25s} T={T:.3f}  ({direction})")

    # ── Pick best and apply to betx21 ─────────────────────────────────────
    sorted_res = sorted(results.items(), key=lambda x: brier(x[1], y))
    best_name, best_cal = sorted_res[0]
    print(f"\n  Best OOF method: {best_name}")

    if not BETX21_PARQUET.exists():
        print(f"  betx21 parquet not found, skipping live comparison.")
        return

    print(f"\n{'='*72}")
    print(f"  BETX21 LIVE COMPARISON (15 matches)")
    print(f"{'='*72}")

    btx = pd.read_parquet(BETX21_PARQUET)
    btx["ph"] = btx["over"].apply(phase)
    model_p  = btx["model_p_t1"].values.astype(float)
    market_p = btx["market_p_t1"].values.astype(float)
    actual   = btx["actual_t1_wins"].values.astype(float)

    btx_inn  = btx["innings"].values
    btx_over = btx["over"].values

    b_mkt = brier(market_p, actual)
    b_raw_live = brier(model_p, actual)

    def apply_to_live(calibrators, seg_fn):
        """Apply fitted calibrators to live data."""
        out = model_p.copy()
        for seg, cal in calibrators.items():
            mask = seg_fn(seg)
            if mask.sum():
                out[mask] = cal.predict(model_p[mask])
        return out

    # Per-over temperature on live
    def seg_fn_over(seg):
        inn, ov_str = seg.split("_over")
        inn_n = int(inn.replace("inn", ""))
        ov_n  = int(ov_str)
        return (btx_inn == inn_n) & (btx_over == ov_n)

    def seg_fn_phase(seg):
        parts = seg.split("_", 1)
        inn_n = int(parts[0].replace("inn", ""))
        ph    = parts[1]
        return (btx_inn == inn_n) & (btx["ph"].values == ph)

    def seg_fn_inn(seg):
        inn_n = int(seg.replace("inn", ""))
        return btx_inn == inn_n

    live_methods = {
        "raw":            model_p,
        "iso_per_over":   apply_to_live(iso_per_over, seg_fn_over),
        "temp_per_over":  apply_to_live(temp_per_over, seg_fn_over),
        "temp_per_phase": apply_to_live(temp_per_phase, seg_fn_phase),
        "platt_per_inn":  apply_to_live(platt_per_inn, seg_fn_inn),
        "temp_per_inn":   apply_to_live(temp_per_inn, seg_fn_inn),
        "temp_global":    temp_global.predict(model_p),
    }

    gap = b_raw_live - b_mkt
    print(f"  Market Brier: {b_mkt:.4f}  |  Raw: {b_raw_live:.4f}")
    print(f"\n  {'Method':<22s} {'Brier':>8s} {'vs Mkt':>8s} {'Gap Closed':>11s} {'ECE':>8s}")
    print(f"  {'-'*62}")
    print(f"  {'Market':<22s} {b_mkt:8.4f}")
    for name, cal in sorted(live_methods.items(), key=lambda x: brier(x[1], actual)):
        bc  = brier(cal, actual)
        gc  = (1 - (bc - b_mkt) / gap) * 100 if gap > 0 else 0
        win = "  ◄BEATS MKT" if bc < b_mkt else ""
        print(f"  {name:<22s} {bc:8.4f} {(bc/b_mkt-1)*100:+7.1f}% {gc:+10.1f}%{win}   ECE={ece(cal,actual):.4f}")

    # Per-segment live
    best_live_name = min(live_methods, key=lambda k: brier(live_methods[k], actual))
    best_live = live_methods[best_live_name]
    print(f"\n  Best live: {best_live_name}  (Brier={brier(best_live,actual):.4f})")
    print(f"\n  Segment breakdown ({best_live_name}):")
    print(f"  {'Segment':<22s} {'n':>4s} {'mkt':>8s} {'raw':>8s} {'best':>8s} {'vs mkt':>8s}")
    print(f"  {'-'*60}")
    for inn in [1, 2]:
        for ph in ["powerplay", "middle", "death"]:
            mask = (btx_inn == inn) & (btx["ph"].values == ph)
            if mask.sum() < 3: continue
            seg = f"inn{inn}_{ph}"
            bm = brier(market_p[mask], actual[mask])
            br = brier(model_p[mask], actual[mask])
            bc = brier(best_live[mask], actual[mask])
            win = "  ◄" if bc < bm else ""
            print(f"  {seg:<22s} {mask.sum():4d} {bm:8.4f} {br:8.4f} {bc:8.4f} {(bc/bm-1)*100:+7.1f}%{win}")
        mask_inn = btx_inn == inn
        print(f"  {'INN'+str(inn)+' TOTAL':<22s} {mask_inn.sum():4d} "
              f"{brier(market_p[mask_inn],actual[mask_inn]):8.4f} "
              f"{brier(model_p[mask_inn],actual[mask_inn]):8.4f} "
              f"{brier(best_live[mask_inn],actual[mask_inn]):8.4f} "
              f"{(brier(best_live[mask_inn],actual[mask_inn])/brier(market_p[mask_inn],actual[mask_inn])-1)*100:+7.1f}%")
        print()

    # ── Save best calibrators into model ──────────────────────────────────
    best_live_segs = {
        "temp_per_over":  (temp_per_over,  "TemperatureScaler per-over"),
        "temp_per_phase": (temp_per_phase, "TemperatureScaler per-phase"),
        "platt_per_inn":  (platt_per_inn,  "PlattScaler per-innings"),
        "temp_per_inn":   (temp_per_inn,   "TemperatureScaler per-innings"),
        "temp_global":    ({"global": temp_global}, "TemperatureScaler global"),
    }

    # Always save all calibrators for reference
    output = {
        "iso_per_over":   iso_per_over,
        "temp_per_over":  temp_per_over,
        "temp_per_phase": temp_per_phase,
        "platt_per_inn":  platt_per_inn,
        "temp_per_inn":   temp_per_inn,
        "temp_global":    temp_global,
        "oof_brier_raw":  b_raw,
        "oof_brier_iso_per_over":  brier(cal_iso_over, y),
        "oof_brier_temp_per_over": brier(cal_temp_over, y),
        "oof_brier_temp_per_phase":brier(cal_temp_phase, y),
        "oof_brier_platt_per_inn": brier(cal_platt_inn, y),
    }
    out_path = MODEL_DIR / "oof_temp_calibrators.pkl"
    joblib.dump(output, out_path)
    print(f"\n  Saved all calibrators to {out_path}")

    # Decide which to promote to per_over_calibrators in isotonic_calibrator.pkl
    # We use OOF brier as the deciding metric (not live, to avoid overfitting on 15 matches)
    oof_ranking = {
        "1_isotonic_per_over": brier(cal_iso_over, y),
        "2_temp_per_over":     brier(cal_temp_over, y),
        "3_temp_per_phase":    brier(cal_temp_phase, y),
        "4_platt_per_inn":     brier(cal_platt_inn, y),
        "5_temp_per_inn":      brier(cal_temp_inn, y),
    }
    best_oof = min(oof_ranking, key=oof_ranking.get)
    print(f"\n  OOF winner: {best_oof} (Brier={oof_ranking[best_oof]:.4f})")
    print(f"  (Existing isotonic_per_over: {oof_ranking['1_isotonic_per_over']:.4f})")

    if oof_ranking[best_oof] < oof_ranking["1_isotonic_per_over"] - 0.0002:
        print(f"  Improvement >{0.0002:.4f} → promoting {best_oof} to per_over_calibrators")
        cal_path = MODEL_DIR / "isotonic_calibrator.pkl"
        cal_data = joblib.load(cal_path)

        new_po = {"2_temp_per_over": temp_per_over,
                  "3_temp_per_phase": temp_per_phase,
                  "4_platt_per_inn": platt_per_inn}.get(best_oof)
        if new_po:
            cal_data["per_over_calibrators"] = new_po
            joblib.dump(cal_data, cal_path)
            print(f"  Updated {cal_path}")
    else:
        print(f"  OOF improvement < 0.0002 — keeping existing isotonic per-over calibrators.")


if __name__ == "__main__":
    main()
