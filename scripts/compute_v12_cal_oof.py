"""
Compute v12 calibrated OOF Brier + LogLoss.

Approach: re-run same 5-fold season CV, apply v12 calibrators (Platt for MID,
isotonic for PP/Death) to each fold's raw OOF preds, compute Brier + LogLoss.
This matches the approach v11 used in oof_calibrated_results.csv.
"""
import warnings; warnings.filterwarnings("ignore")
import json, pickle, sys
import numpy as np, pandas as pd
import joblib
from pathlib import Path
from scipy.special import logit
from sklearn.linear_model import LogisticRegression
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import brier_score_loss, log_loss

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from bbl_pipeline.training.blend_model import XGBLRBlend  # for unpickling

# PlattCalibrator must match the class that pickled the calibrators
class PlattCalibrator:
    def __init__(self, C=1.0): self.C = C; self._eps = 1e-6
    def fit(self, raw, y):
        X = logit(np.clip(raw, self._eps, 1-self._eps)).reshape(-1, 1)
        self._lr = LogisticRegression(C=self.C, max_iter=2000, random_state=42)
        self._lr.fit(X, y.astype(int)); return self
    def transform(self, raw):
        X = logit(np.clip(raw, self._eps, 1-self._eps)).reshape(-1, 1)
        return self._lr.predict_proba(X)[:, 1]
    def predict(self, raw): return self.transform(raw)

V11 = Path("models/ipl_inn2_v1")
V12 = Path("models/ipl_v12")
DATA = Path("data/ipl_inn2_features_v1/training.parquet")
PHASE_OVERS = {"pp": (1, 6), "mid": (7, 15), "death": (16, 20)}

def add_pp_feats(df):
    d = df.copy()
    rrr = d["required_run_rate"].clip(lower=0.1)
    tap = d["target_above_par"]; vcs = d["venue_chase_success"]; res = d["resources_remaining"]
    d["pp_ease_score"]          = (-tap) / rrr
    d["pp_rrr_ease"]             = 10.0 - d["required_run_rate"]
    d["chase_ease_x_venue"]      = (-tap.clip(upper=0)) * vcs
    d["low_target_strong_venue"] = (tap < -15).astype(float) * vcs
    d["pp_resources_adj_ease"]   = (-tap) * res
    return d

def safe_X(df_s, feats):
    avail = [f for f in feats if f in df_s.columns]
    return df_s[avail].fillna(df_s[avail].median()).values

# Load
print("Loading data...")
df = pd.read_parquet(DATA)
df = df.sort_values(["match_id", "innings", "over", "ball"]).reset_index(drop=True)
df = df[df["innings"] == 2].copy()
df = add_pp_feats(df)
ALL_SEASONS = sorted(df["season"].unique())
print(f"  Inn2 rows: {len(df):,}  seasons: {len(ALL_SEASONS)}")

v11_feats = json.load(open(V11 / "phase_features.json"))
v12_feats = json.load(open(V12 / "phase_features.json"))
v12_cals  = pickle.load(open(V12 / "phase_oof_calibrators.pkl", "rb"))

# Run 5-fold season OOF for both v11 and v12
N_FOLDS = 5

def run_oof(feats_dict, phase, phase_df):
    seasons = sorted(phase_df["season"].unique())
    fold_size = max(1, len(seasons) // N_FOLDS)
    n = len(phase_df)
    oof_raw = np.zeros(n)
    oof_y   = phase_df["is_winner"].values.copy()
    oof_ov  = phase_df["over"].values.copy()

    for fold in range(N_FOLDS):
        val_s = seasons[fold * fold_size: (fold + 1) * fold_size] if fold < N_FOLDS - 1 else seasons[fold * fold_size:]
        tr_s  = [s for s in seasons if s not in val_s]
        tr_m  = phase_df["season"].isin(tr_s)
        va_m  = phase_df["season"].isin(val_s)
        X_tr  = safe_X(phase_df[tr_m], feats_dict[phase])
        X_va  = safe_X(phase_df[va_m], feats_dict[phase])
        y_tr  = phase_df.loc[tr_m, "is_winner"].values
        m = XGBLRBlend(); m.fit(X_tr, y_tr)
        oof_raw[va_m.values] = m.predict_proba(X_va)[:, 1]

    return oof_raw, oof_y, oof_ov

print("\nRunning OOF (5-fold, ~2-3 min)...")
results = {}
for phase, (lo, hi) in PHASE_OVERS.items():
    pf = df[(df["over"] >= lo) & (df["over"] <= hi)].copy().reset_index(drop=True)

    # v11 OOF
    raw11, y, ov = run_oof(v11_feats, phase, pf)
    # v12 OOF
    raw12, _, _  = run_oof(v12_feats, phase, pf)

    # Apply v12 calibrators (same approach as v11's oof_calibrated_results.csv)
    per_over = v12_cals[phase]["per_over"]
    phase_iso = v12_cals[phase]["phase_iso"]
    cal12 = raw12.copy()
    for ov_val in np.unique(ov):
        mask = ov == ov_val
        c = per_over.get(int(ov_val), phase_iso)
        cal12[mask] = c.transform(raw12[mask])

    # v11 OOF calibrated: use v11's per-over isotonic from v11 cals
    v11_cals_data = pickle.load(open(V11 / "phase_oof_calibrators.pkl", "rb"))
    per_over11 = v11_cals_data[phase]["per_over"]
    phase_iso11 = v11_cals_data[phase]["phase_iso"]
    cal11 = raw11.copy()
    for ov_val in np.unique(ov):
        mask = ov == ov_val
        c = per_over11.get(int(ov_val), phase_iso11)
        cal11[mask] = c.transform(raw11[mask])

    def m(y, p):
        p = np.clip(p, 1e-7, 1-1e-7)
        return brier_score_loss(y, p), log_loss(y, p)

    b11r, ll11r = m(y, raw11);  b11c, ll11c = m(y, cal11)
    b12r, ll12r = m(y, raw12);  b12c, ll12c = m(y, cal12)
    results[phase] = dict(n=len(y),
        v11_raw=b11r, v11_cal=b11c, v11_ll=ll11c,
        v12_raw=b12r, v12_cal=b12c, v12_ll=ll12c)
    print(f"  {phase.upper()}: n={len(y):,}  v11_cal={b11c:.5f}  v12_cal={b12c:.5f}  v11_ll={ll11c:.5f}  v12_ll={ll12c:.5f}")

# Routing overall (weighted by phase size)
all_n = sum(r["n"] for r in results.values())
w_b11c = sum(r["n"] * r["v11_cal"] for r in results.values()) / all_n
w_b12c = sum(r["n"] * r["v12_cal"] for r in results.values()) / all_n
w_ll11 = sum(r["n"] * r["v11_ll"]  for r in results.values()) / all_n
w_ll12 = sum(r["n"] * r["v12_ll"]  for r in results.values()) / all_n

print()
W = 126
print("=" * W)
print("  IPL v11 vs v12  |  OOF (5-fold season CV, all 19 seasons)  |  Inn2 Phase Breakdown")
print("=" * W)
print(f"  {'Phase':<12}{'N':>7}   {'v11 Raw Br':>11}{'v11 Cal Br':>11}{'v12 Raw Br':>11}{'v12 Cal Br':>11}   {'Δ Brier':>9}   {'v11 Cal LL':>11}{'v12 Cal LL':>11}   {'Δ LL':>8}")
print("  " + "-" * (W - 2))
for phase_label, phase_key in [("INN2 OVERALL", None), ("Inn2 PP", "pp"), ("Inn2 MID", "mid"), ("Inn2 DEATH", "death")]:
    if phase_key is None:
        b11r = sum(r["n"]*r["v11_raw"] for r in results.values()) / all_n
        r_row = dict(n=all_n, v11_raw=b11r, v11_cal=w_b11c, v12_raw=sum(r["n"]*r["v12_raw"] for r in results.values())/all_n, v12_cal=w_b12c, v11_ll=w_ll11, v12_ll=w_ll12)
    else:
        r_row = results[phase_key]
    d_b = (r_row["v12_cal"] - r_row["v11_cal"]) / r_row["v11_cal"] * 100
    d_l = (r_row["v12_ll"]  - r_row["v11_ll"])  / r_row["v11_ll"]  * 100
    sb = "▼" if d_b < -0.1 else ("▲" if d_b > 0.1 else "≈")
    sl = "▼" if d_l < -0.1 else ("▲" if d_l > 0.1 else "≈")
    print(f"  {phase_label:<12}{r_row['n']:>7}   {r_row['v11_raw']:>11.5f}{r_row['v11_cal']:>11.5f}{r_row['v12_raw']:>11.5f}{r_row['v12_cal']:>11.5f}   {sb}{d_b:>+8.2f}%   {r_row['v11_ll']:>11.5f}{r_row['v12_ll']:>11.5f}   {sl}{d_l:>+6.2f}%")
    if phase_key is None:
        print("  " + "-" * (W - 2))
print("=" * W)
print()
print("  ▼ v12 better  ▲ v12 worse  ≈ within ±0.1%  |  Brier & LogLoss: lower = better")
print("  OOF calibrators applied to same OOF preds (standard approach, matches v11 oof_calibrated_results.csv)")

# Save summary for registry update
import json
summary = {
    "v11_routing_brier_oof_cal": round(w_b11c, 5),
    "v12_routing_brier_oof_cal": round(w_b12c, 5),
    "phases": {ph: {
        "n": results[ph]["n"],
        "v11_cal": round(results[ph]["v11_cal"], 5),
        "v12_cal": round(results[ph]["v12_cal"], 5),
        "v11_ll":  round(results[ph]["v11_ll"],  5),
        "v12_ll":  round(results[ph]["v12_ll"],  5),
    } for ph in ["pp", "mid", "death"]}
}
with open("models/ipl_v12/oof_calibrated_comparison.json", "w") as f:
    json.dump(summary, f, indent=2)
print(f"\n  Saved: models/ipl_v12/oof_calibrated_comparison.json")
