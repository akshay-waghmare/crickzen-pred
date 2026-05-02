"""Compare v6 vs v7 IPL model: Brier, Log Loss, ECE at each calibration stage.
Vectorized: applies per-over and phase×target calibration without per-row loops.
"""
import numpy as np
import pandas as pd
import joblib
from sklearn.metrics import brier_score_loss, log_loss

DATA_V6 = "data/ipl_features_v6/training.parquet"
DATA_V7 = "data/ipl_features_v7/training.parquet"
MODELS = {
    "v6": {"model": "models/ipl_v6/champion_model.joblib",
           "cal":   "models/ipl_v6/isotonic_calibrator.pkl",
           "pt":    "models/ipl_v6/phase_target_calibrators.pkl",
           "data":  DATA_V6},
    "v7": {"model": "models/ipl_v7/champion_model.joblib",
           "cal":   "models/ipl_v7/isotonic_calibrator.pkl",
           "pt":    "models/ipl_v7/phase_target_calibrators.pkl",
           "data":  DATA_V7},
}

def ece(y_true, y_prob, n_bins=10):
    bins = np.linspace(0, 1, n_bins + 1)
    total = len(y_true)
    ece_val = 0.0
    for lo, hi in zip(bins[:-1], bins[1:]):
        mask = (y_prob >= lo) & (y_prob < hi)
        n = mask.sum()
        if n == 0:
            continue
        ece_val += (n / total) * abs(y_true[mask].mean() - y_prob[mask].mean())
    return ece_val

def apply_per_over_vec(p_raw, df, per_over_cals, inn):
    """Vectorized: group rows by over key, apply calibrator per group."""
    p = p_raw.copy()
    over_1idx = (df["over"].values.astype(int) + 1)
    keys = np.array([f"inn{inn}_over{o}" for o in over_1idx])
    for k in np.unique(keys):
        if k not in per_over_cals:
            continue
        mask = keys == k
        p[mask] = per_over_cals[k].predict(p_raw[mask])
    return p

def apply_phase_target_vec(p_po, df, pt_cals):
    """Vectorized: group inn2 rows by phase×target key, apply calibrator."""
    p = p_po.copy()
    over_1idx = df["over"].values.astype(int) + 1
    phase = np.where(over_1idx <= 6, "PP", np.where(over_1idx <= 15, "Mid", "Death"))
    tap = df["target_above_par"].values.astype(float) if "target_above_par" in df.columns else np.zeros(len(df))
    tcat = np.where(tap < -15, "below_par", np.where(tap <= 15, "on_par", "above_par"))
    keys = np.array([f"{ph}_{tc}" for ph, tc in zip(phase, tcat)])
    for k in np.unique(keys):
        if k not in pt_cals:
            continue
        mask = keys == k
        p[mask] = pt_cals[k].predict(p_po[mask])
    return p

def metrics(y, p, label=""):
    b  = brier_score_loss(y, p)
    ll = log_loss(y, p)
    e  = ece(y, p)
    n  = len(y)
    return {"label": label, "n": n, "Brier": b, "LogLoss": ll, "ECE": e}

def run_model(name, paths, data):
    print(f"\n{'='*65}")
    print(f"  MODEL: ipl_{name}")
    print(f"{'='*65}")
    model    = joblib.load(paths["model"])
    cal_data = joblib.load(paths["cal"])
    pt_data  = joblib.load(paths["pt"])
    per_over = cal_data.get("per_over_calibrators", {})
    pt_cals  = pt_data["calibrators"]
    # Use only features present in the data (handles v6 vs v7 feature set differences)
    feats    = [f for f in model.TOP_FEATURES if f in data.columns]

    # Overall predictions
    y_all  = data["is_winner"].values
    p_raw_all = model.predict_proba(data[feats])[:, 1]
    p_po_all  = np.zeros_like(p_raw_all)
    p_pt_all  = np.zeros_like(p_raw_all)

    rows = []
    for inn in [1, 2]:
        mask = data["innings"] == inn
        sub  = data[mask].reset_index(drop=True)
        y    = sub["is_winner"].values
        p_raw = p_raw_all[mask.values]
        p_po  = apply_per_over_vec(p_raw, sub, per_over, inn)
        p_pt  = apply_phase_target_vec(p_po, sub, pt_cals) if inn == 2 else p_po.copy()
        p_po_all[mask.values] = p_po
        p_pt_all[mask.values] = p_pt

        rows.append(metrics(y, p_raw, f"Inn{inn} Raw"))
        rows.append(metrics(y, p_po,  f"Inn{inn} PerOver"))
        if inn == 2:
            rows.append(metrics(y, p_pt, f"Inn{inn} Phase*Tgt"))

        # Phase breakdown for inn2
        if inn == 2:
            over_1 = sub["over"].values.astype(int) + 1
            for ph_name, lo, hi in [("PP", 1, 6), ("Mid", 7, 15), ("Death", 16, 20)]:
                ph_mask = (over_1 >= lo) & (over_1 <= hi)
                if ph_mask.sum() == 0:
                    continue
                rows.append(metrics(y[ph_mask], p_raw[ph_mask], f"  Inn2 {ph_name:5s} Raw"))
                rows.append(metrics(y[ph_mask], p_po[ph_mask],  f"  Inn2 {ph_name:5s} PerOver"))
                rows.append(metrics(y[ph_mask], p_pt[ph_mask],  f"  Inn2 {ph_name:5s} Phase*Tgt"))

    # Insert overall rows at top
    overall = [
        metrics(y_all, p_raw_all, "OVERALL Raw"),
        metrics(y_all, p_po_all,  "OVERALL PerOver"),
        metrics(y_all, p_pt_all,  "OVERALL Phase*Tgt"),
    ]
    rows = overall + rows

    result = pd.DataFrame(rows)
    result["Brier"]   = result["Brier"].map("{:.4f}".format)
    result["LogLoss"] = result["LogLoss"].map("{:.4f}".format)
    result["ECE"]     = result["ECE"].map("{:.4f}".format)
    print(result.to_string(index=False))
    return result

data_v6 = pd.read_parquet(DATA_V6)
data_v7 = pd.read_parquet(DATA_V7)
print(f"Loaded v6: {len(data_v6):,} rows | v7: {len(data_v7):,} rows")
r6 = run_model("v6", MODELS["v6"], data_v6)
r7 = run_model("v7", MODELS["v7"], data_v7)

