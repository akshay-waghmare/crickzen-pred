"""
Experiment B — Death Live-Chase Feature Block
Add features for close-chase death situations (wickets>=5, RRR~11-13).
Train/Val/Test: pre-2024 / 2024 / 2025+2026
Focus: reduce the 3% uncertain zone, improve calibration for 'alive close chases'
"""
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, joblib, json
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import log_loss
from bbl_pipeline.training.blend_model import XGBLRBlend

print("Loading data…")
df = pd.read_parquet("data/ipl_inn2_features_v1/training.parquet")
df["phase_label"] = df["over"].apply(
    lambda o: "PP" if 1<=o<=6 else ("MID" if 7<=o<=15 else "DEATH"))
death = df[df["phase_label"] == "DEATH"].copy()

with open("models/ipl_inn2_v1/phase_features.json") as f:
    BASE_FEATS = json.load(f)["death"]

TRAIN_SEASONS = {s for s in death["season"].unique() if s < "2024"}
VAL_SEASONS   = {"2024"}
TEST_SEASONS  = {"2025", "2026"}

# ── NEW FEATURE ENGINEERING ───────────────────────────────────────────────────
def add_death_live_chase_features(df_in):
    d = df_in.copy()

    # 1. flag: doable RRR in death (< 13 is difficult but live)
    d["death_rrr_under_13"] = (d["required_run_rate"] < 13).astype(float)

    # 2. flag: many wickets down BUT still a live chase
    d["death_close_alive"] = (
        (d["wickets_lost"] >= 5) & (d["required_run_rate"] < 13)
    ).astype(float)

    # 3. interaction: balls left × wickets lost × RRR (scaled)
    d["balls_wkts_rrr"] = (
        d["balls_remaining"] * d["wickets_lost"] * d["required_run_rate"] / 1000.0
    )

    # 4. batting resources efficiency: how many wickets per required-run-rate unit
    #    low rrr + many wickets = favorable (high positive)
    d["batting_resources_per_rr"] = d["wickets_remaining"] / (
        d["required_run_rate"].clip(lower=0.1)
    )

    # 5. death pressure composite per wicket (high = very under pressure)
    d["death_pressure_per_wkt"] = (
        d["required_run_rate"] * d["wickets_lost"] /
        (d["wickets_remaining"].clip(lower=0.1))
    )

    return d

death = add_death_live_chase_features(death)
NEW_FEATS = ["death_rrr_under_13", "death_close_alive", "balls_wkts_rrr",
             "batting_resources_per_rr", "death_pressure_per_wkt"]
EXPANDED_FEATS = BASE_FEATS + NEW_FEATS

train = death[death["season"].isin(TRAIN_SEASONS)]
val   = death[death["season"].isin(VAL_SEASONS)]
test  = death[death["season"].isin(TEST_SEASONS)]
print(f"  Train: {len(train):,}  Val: {len(val):,}  Test: {len(test):,}")

def safe_feats(df_s, feats):
    return df_s[[f for f in feats if f in df_s.columns]].fillna(0)

X_train_base = safe_feats(train, BASE_FEATS).values
X_val_base   = safe_feats(val,   BASE_FEATS).values
X_test_base  = safe_feats(test,  BASE_FEATS).values

X_train_exp  = safe_feats(train, EXPANDED_FEATS).values
X_val_exp    = safe_feats(val,   EXPANDED_FEATS).values
X_test_exp   = safe_feats(test,  EXPANDED_FEATS).values

y_train = train["is_winner"].values
y_val   = val["is_winner"].values
y_test  = test["is_winner"].values

def train_and_eval(X_tr, X_va, X_te, y_tr, y_va, y_te, label):
    print(f"  Training {label} (n_feats={X_tr.shape[1]})…")
    m = XGBLRBlend()
    m.fit(X_tr, y_tr)

    raw_val  = m.predict_proba(X_va)[:, 1]
    raw_test = m.predict_proba(X_te)[:, 1]

    iso = IsotonicRegression(out_of_bounds="clip")
    iso.fit(raw_val, y_va)
    cal_test = iso.transform(raw_test)

    def metrics(p, y):
        return {
            "brier":   round(float(np.mean((p-y)**2)), 5),
            "std":     round(float(p.std()), 4),
            "unc%":    round(float(((p>=0.45)&(p<=0.55)).mean()*100), 1),
            "conf%":   round(float(((p<0.30)|(p>0.70)).mean()*100), 1),
            "mean":    round(float(p.mean()), 4),
        }
    return metrics(raw_test, y_te), metrics(cal_test, y_te), m

print("\nTraining models…")
b_raw, b_cal, m_base = train_and_eval(X_train_base, X_val_base, X_test_base,
                                       y_train, y_val, y_test, "Baseline Death")
e_raw, e_cal, m_exp  = train_and_eval(X_train_exp,  X_val_exp,  X_test_exp,
                                       y_train, y_val, y_test, "Expanded Death")

# ── uncertain zone analysis ───────────────────────────────────────────────────
X_test_exp_arr  = safe_feats(test, EXPANDED_FEATS).values
X_test_base_arr = safe_feats(test, BASE_FEATS).values
raw_base = m_base.predict_proba(X_test_base_arr)[:, 1]
raw_exp  = m_exp.predict_proba(X_test_exp_arr)[:,  1]

iso_base = IsotonicRegression(out_of_bounds="clip")
iso_base.fit(m_base.predict_proba(safe_feats(val, BASE_FEATS).values)[:,1], y_val)
cal_base = iso_base.transform(raw_base)

iso_exp = IsotonicRegression(out_of_bounds="clip")
iso_exp.fit(m_exp.predict_proba(safe_feats(val, EXPANDED_FEATS).values)[:,1], y_val)
cal_exp  = iso_exp.transform(raw_exp)

unc_mask_base = (cal_base>=0.45)&(cal_base<=0.55)
unc_mask_exp  = (cal_exp >=0.45)&(cal_exp <=0.55)

# also close-alive subset (wickets>=5 AND RRR<13)
if "wickets_lost" in test.columns and "required_run_rate" in test.columns:
    close_alive = ((test["wickets_lost"].values >= 5) &
                   (test["required_run_rate"].values < 13))
else:
    close_alive = np.zeros(len(test), dtype=bool)

print("\n")
print("=" * 90)
print("EXPERIMENT B: DEATH LIVE-CHASE FEATURE BLOCK  |  Test: 2025+2026")
print(f"  New features: {NEW_FEATS}")
print("=" * 90)

print(f"\n{'Metric':<25}  {'Baseline raw':>12} {'Baseline cal':>13} | {'Expanded raw':>12} {'Expanded cal':>13}")
print("-" * 80)
for key in ["brier", "std", "unc%", "conf%", "mean"]:
    print(f"  {key:<23} {b_raw[key]:>12} {b_cal[key]:>13} | {e_raw[key]:>12} {e_cal[key]:>13}")

print(f"\n  Uncertain zone (0.45-0.55):")
print(f"    Baseline: {unc_mask_base.sum()} balls ({unc_mask_base.mean()*100:.1f}%), actual win rate {y_test[unc_mask_base].mean():.3f}")
print(f"    Expanded: {unc_mask_exp.sum()} balls ({unc_mask_exp.mean()*100:.1f}%), actual win rate {y_test[unc_mask_exp].mean():.3f}")

print(f"\n  Close-alive subset (wickets>=5, RRR<13): {close_alive.sum()} balls")
if close_alive.sum() > 0:
    print(f"    Baseline cal mean: {cal_base[close_alive].mean():.4f}, actual: {y_test[close_alive].mean():.4f}, bias: {cal_base[close_alive].mean()-y_test[close_alive].mean():+.4f}")
    print(f"    Expanded  cal mean: {cal_exp[close_alive].mean():.4f}, actual: {y_test[close_alive].mean():.4f}, bias: {cal_exp[close_alive].mean()-y_test[close_alive].mean():+.4f}")

# Bucket by RRR bins
print(f"\n  Expanded vs Baseline by RRR bucket (calibrated):")
rrr = test["required_run_rate"].fillna(0).values
for lo, hi in [(0,8), (8,12), (12,16), (16,25), (25,100)]:
    mask = (rrr >= lo) & (rrr < hi)
    if mask.sum() < 20: continue
    b_m = cal_base[mask].mean()
    e_m = cal_exp[mask].mean()
    actual = y_test[mask].mean()
    print(f"    RRR {lo:>2}-{hi:<3}: base={b_m:.4f} exp={e_m:.4f} actual={actual:.4f} | base_bias={b_m-actual:+.4f} exp_bias={e_m-actual:+.4f} (n={mask.sum()})")

# Feature importance
print("\n--- Feature importance (XGB, sklearn) for expanded model ---")
fi_arr = m_exp.xgb.feature_importances_
sorted_fi = sorted(zip(EXPANDED_FEATS, fi_arr), key=lambda x: x[1], reverse=True)
for feat, gain in sorted_fi[:15]:
    flag = " *** NEW" if feat in NEW_FEATS else ""
    print(f"  {feat:<40} {gain:>8.5f}{flag}")

import json as js
results = {
    "baseline": {"raw": b_raw, "cal": b_cal},
    "expanded":  {"raw": e_raw, "cal": e_cal},
    "new_feats": NEW_FEATS,
    "uncertain_baseline": int(unc_mask_base.sum()),
    "uncertain_expanded":  int(unc_mask_exp.sum()),
}
with open("data/exp_b_death_results.json", "w") as f:
    js.dump(results, f, default=str)
print("\nSaved: data/exp_b_death_results.json")
