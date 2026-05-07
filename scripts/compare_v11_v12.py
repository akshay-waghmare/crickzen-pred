"""
v11 vs v12 — Inn-wise and Phase-wise Brier + LogLoss comparison (OOS 2025+2026)
"""
import warnings; warnings.filterwarnings("ignore")
import json, pickle, sys
import numpy as np, pandas as pd
import joblib
from pathlib import Path
from scipy.special import logit
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from bbl_pipeline.training.blend_model import XGBLRBlend  # needed for unpickling

# ── PlattCalibrator (needed to unpickle v12 calibrators) ──────────────────────
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
OOS_SEASONS = ["2025", "2026"]
PHASE_OVERS = {"PP": (1, 6), "MID": (7, 15), "DEATH": (16, 20)}


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


def apply_cal_vec(cals, phase, over_arr, raw):
    """Vectorized calibration: group by over, apply per-over or phase fallback."""
    out = raw.copy()
    per_over = cals[phase]["per_over"]
    phase_iso = cals[phase]["phase_iso"]
    for ov in np.unique(over_arr):
        mask = over_arr == ov
        cal = per_over.get(int(ov), phase_iso)
        out[mask] = cal.transform(raw[mask])
    return out


def m(y, p):
    p = np.clip(p, 1e-7, 1 - 1e-7)
    return brier_score_loss(y, p), log_loss(y, p)


# ── Load ──────────────────────────────────────────────────────────────────────
print("Loading data...")
df = pd.read_parquet(DATA)
df = df.sort_values(["match_id", "innings", "over", "ball"]).reset_index(drop=True)
df = df[df["innings"] == 2].copy()
df = add_pp_feats(df)
oos = df[df["season"].isin(OOS_SEASONS)].copy()
print(f"  OOS rows (inn2, {OOS_SEASONS}): {len(oos):,}")

print("Loading models...")
v11_feats = json.load(open(V11 / "phase_features.json"))
v12_feats = json.load(open(V12 / "phase_features.json"))
v11_cals  = pickle.load(open(V11 / "phase_oof_calibrators.pkl", "rb"))
v12_cals  = pickle.load(open(V12 / "phase_oof_calibrators.pkl", "rb"))
v11_models = {p: joblib.load(V11 / f"champion_model_{p}.joblib") for p in ["pp", "mid", "death"]}
v12_models = {p: joblib.load(V12 / f"champion_model_{p}.joblib") for p in ["pp", "mid", "death"]}
print("  Done.")

# ── Predict per phase ─────────────────────────────────────────────────────────
results = {}
for phase, (lo, hi) in PHASE_OVERS.items():
    ph = phase.lower()
    sub = oos[(oos["over"] >= lo) & (oos["over"] <= hi)]
    y = sub["is_winner"].values; overs = sub["over"].values
    raw11 = v11_models[ph].predict_proba(safe_X(sub, v11_feats[ph]))[:, 1]
    raw12 = v12_models[ph].predict_proba(safe_X(sub, v12_feats[ph]))[:, 1]
    cal11 = apply_cal_vec(v11_cals, ph, overs, raw11)
    cal12 = apply_cal_vec(v12_cals, ph, overs, raw12)
    results[phase] = dict(y=y, raw11=raw11, cal11=cal11, raw12=raw12, cal12=cal12, n=len(y))
    print(f"  {phase}: {len(y):,} rows done")

# Overall (all phases concatenated)
results["OVERALL"] = {
    k: np.concatenate([results[p][k] for p in ["PP", "MID", "DEATH"]])
    for k in ["y", "raw11", "cal11", "raw12", "cal12"]
}
results["OVERALL"]["n"] = len(results["OVERALL"]["y"])

# ── Print table ───────────────────────────────────────────────────────────────
W = 138
print()
print("=" * W)
print("  IPL v11 vs v12  |  OOS 2025+2026  |  Inn2 Phase Breakdown")
print("=" * W)
print(f"  {'Phase':<12}{'N':>7}   {'v11 Raw Br':>11}{'v11 Cal Br':>11}{'v12 Raw Br':>11}{'v12 Cal Br':>11}   {'Δ Cal Brier':>11}   {'v11 Cal LL':>11}{'v12 Cal LL':>11}   {'Δ LogLoss':>10}")
print("  " + "-" * (W - 2))
for phase in ["OVERALL", "PP", "MID", "DEATH"]:
    r = results[phase]; y = r["y"]
    b11r, ll11r = m(y, r["raw11"]); b11c, ll11c = m(y, r["cal11"])
    b12r, ll12r = m(y, r["raw12"]); b12c, ll12c = m(y, r["cal12"])
    d_b = (b12c - b11c) / b11c * 100
    d_l = (ll12c - ll11c) / ll11c * 100
    sb = "▼" if d_b < -0.05 else ("▲" if d_b > 0.05 else "≈")
    sl = "▼" if d_l < -0.05 else ("▲" if d_l > 0.05 else "≈")
    sep = "━" if phase == "OVERALL" else " "
    line = (f"  {phase:<12}{r['n']:>7}   "
            f"{b11r:>11.5f}{b11c:>11.5f}{b12r:>11.5f}{b12c:>11.5f}   "
            f"  {sb} {d_b:>+7.2f}%   "
            f"{ll11c:>11.5f}{ll12c:>11.5f}   "
            f"  {sl} {d_l:>+6.2f}%")
    print(line)
    if phase == "OVERALL":
        print("  " + "-" * (W - 2))
print("=" * W)
print()
print("  ▼ v12 better  ▲ v12 worse  ≈ within ±0.05%  |  Brier & LogLoss: lower = better")
print()
