"""Quick validation: compare Inn2 Brier at each calibration stage (v6 model)."""
import pandas as pd
import numpy as np
import joblib
from sklearn.metrics import brier_score_loss

data = pd.read_parquet("data/ipl_features_latest/training.parquet")
model = joblib.load("models/ipl_v6/champion_model.joblib")
cal_data = joblib.load("models/ipl_v6/isotonic_calibrator.pkl")
pt_data = joblib.load("models/ipl_v6/phase_target_calibrators.pkl")

feats = model.TOP_FEATURES
inn2 = data[data["innings"] == 2].reset_index(drop=True)
X2 = inn2[feats]

p_raw = model.predict_proba(X2)[:, 1]
per_over = cal_data.get("per_over_calibrators", {})

# Per-over calibration
p_po = p_raw.copy()
for i in range(len(inn2)):
    over_1idx = int(inn2.at[i, "over"]) + 1
    k = f"inn2_over{over_1idx}"
    if k in per_over:
        p_po[i] = float(per_over[k].predict([p_raw[i]])[0])

# Phase x target calibration
pt_cals = pt_data["calibrators"]
p_pt = p_po.copy()
for i in range(len(inn2)):
    over_1idx = int(inn2.at[i, "over"]) + 1
    if over_1idx <= 6:
        ph = "PP"
    elif over_1idx <= 15:
        ph = "Mid"
    else:
        ph = "Death"
    tap = float(inn2.at[i, "target_above_par"]) if "target_above_par" in inn2.columns else 0.0
    if tap < -15:
        tcat = "below_par"
    elif tap <= 15:
        tcat = "on_par"
    else:
        tcat = "above_par"
    k = f"{ph}_{tcat}"
    if k in pt_cals:
        p_pt[i] = float(pt_cals[k].predict([p_po[i]])[0])

y2 = inn2["is_winner"].values
print(f"Inn2 raw Brier:       {brier_score_loss(y2, p_raw):.4f}")
print(f"Inn2 per-over Brier:  {brier_score_loss(y2, p_po):.4f}")
print(f"Inn2 phase*tgt Brier: {brier_score_loss(y2, p_pt):.4f}")

# Phase breakdown
for ph, lo, hi in [("PP", 0, 5), ("Mid", 6, 14), ("Death", 15, 19)]:
    mask = (inn2["over"] >= lo) & (inn2["over"] <= hi)
    idx = mask.values
    print(f"  {ph:6s} raw:{brier_score_loss(y2[idx], p_raw[idx]):.4f}  "
          f"po:{brier_score_loss(y2[idx], p_po[idx]):.4f}  "
          f"pt:{brier_score_loss(y2[idx], p_pt[idx]):.4f}")
