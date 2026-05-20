"""
Experiment A — PP Easy-Chase Feature Block
Add 5 new features capturing easy-chase situations in PP.
Train/Val/Test: pre-2024 / 2024 / 2025+2026
Compare: overall Brier + by target bucket (Low/Par/High)
Goal: easy chases (target_low) should push to 0.90+
"""
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, joblib, json
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import log_loss
from bbl_pipeline.training.blend_model import XGBLRBlend

# ── data ─────────────────────────────────────────────────────────────────────
print("Loading data…")
df = pd.read_parquet("data/ipl_inn2_features_v1/training.parquet")
df["phase_label"] = df["over"].apply(
    lambda o: "PP" if 1<=o<=6 else ("MID" if 7<=o<=15 else "DEATH"))
pp = df[df["phase_label"] == "PP"].copy()

with open("models/ipl_inn2_v1/phase_features.json") as f:
    BASE_FEATS = json.load(f)["pp"]

TRAIN_SEASONS = {s for s in pp["season"].unique() if s < "2024"}
VAL_SEASONS   = {"2024"}
TEST_SEASONS  = {"2025", "2026"}

# ── NEW FEATURE ENGINEERING ───────────────────────────────────────────────────
def add_pp_easy_chase_features(df_in):
    d = df_in.copy()

    # 1. continuous chase ease: low target + low RRR = easy chase
    d["pp_ease_score"] = (-d["target_above_par"]) / (d["required_run_rate"].clip(lower=0.1))

    # 2. PP RRR normalized to par (8 rpo is roughly par in powerplay)
    d["pp_rrr_ease"] = 10.0 - d["required_run_rate"]   # positive = below par RRR

    # 3. easy target × chase-friendly venue
    d["chase_ease_x_venue"] = (-d["target_above_par"].clip(upper=0)) * d["venue_chase_success"]

    # 4. threshold flag: target well below par at a strong chasing venue
    d["low_target_strong_venue"] = (
        (d["target_above_par"] < -15).astype(float) * d["venue_chase_success"]
    )

    # 5. resources × target ease (more resources + lower target = bigger edge)
    d["pp_resources_adj_ease"] = (-d["target_above_par"]) * d["resources_remaining"]

    return d

pp = add_pp_easy_chase_features(pp)
NEW_FEATS = ["pp_ease_score", "pp_rrr_ease", "chase_ease_x_venue",
             "low_target_strong_venue", "pp_resources_adj_ease"]
EXPANDED_FEATS = BASE_FEATS + NEW_FEATS

train = pp[pp["season"].isin(TRAIN_SEASONS)]
val   = pp[pp["season"].isin(VAL_SEASONS)]
test  = pp[pp["season"].isin(TEST_SEASONS)]
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

# ── train baseline vs expanded ────────────────────────────────────────────────
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
            "logloss": round(float(log_loss(y, np.clip(p,1e-7,1-1e-7))), 5),
            "std":     round(float(p.std()), 4),
            "unc%":    round(float(((p>=0.45)&(p<=0.55)).mean()*100), 1),
            "conf%":   round(float(((p<0.30)|(p>0.70)).mean()*100), 1),
            "mean":    round(float(p.mean()), 4),
        }

    # bucket analysis by target_above_par
    tq = np.quantile(test["target_above_par"].fillna(0), [0.33, 0.67])
    masks = {
        "Target: Low":  (test["target_above_par"].fillna(0) <= tq[0]).values,
        "Target: Par":  ((test["target_above_par"].fillna(0) > tq[0]) & (test["target_above_par"].fillna(0) <= tq[1])).values,
        "Target: High": (test["target_above_par"].fillna(0) > tq[1]).values,
    }

    rows = {}
    rows["Overall"] = {**metrics(raw_test, y_te), "cal": metrics(cal_test, y_te)}
    for bucket_name, mask in masks.items():
        rows[bucket_name] = {
            **metrics(raw_test[mask], y_te[mask]),
            "cal": metrics(cal_test[mask], y_te[mask]),
            "outcome_rate": round(float(y_te[mask].mean()), 4),
        }
    return rows, m

print("\nTraining models…")
base_rows, m_base = train_and_eval(
    X_train_base, X_val_base, X_test_base, y_train, y_val, y_test, "Baseline PP")
exp_rows, m_exp = train_and_eval(
    X_train_exp, X_val_exp, X_test_exp, y_train, y_val, y_test, "Expanded PP")

# ── print comparison ──────────────────────────────────────────────────────────
print("\n")
print("=" * 110)
print("EXPERIMENT A: PP EASY-CHASE FEATURE BLOCK  |  Test: 2025+2026")
print(f"  New features: {NEW_FEATS}")
print("=" * 110)

segments = ["Overall", "Target: Low", "Target: Par", "Target: High"]
print(f"\n{'Segment':<18} {'Baseline raw_brier':>18} {'Baseline cal_brier':>18} | {'Expanded raw_brier':>18} {'Expanded cal_brier':>18} | {'outcome_rate':>13} | {'Change cal_brier':>17}")
print("-" * 115)
for seg in segments:
    b = base_rows[seg]
    e = exp_rows[seg]
    b_cal = b["cal"]
    e_cal = e["cal"]
    change = e_cal["brier"] - b_cal["brier"]
    outcome = b.get("outcome_rate", "")
    flag = " ***BETTER" if change < -0.001 else (" --worse" if change > 0.001 else " ~same")
    print(f"{seg:<18} {b['brier']:>18.5f} {b_cal['brier']:>18.5f} | {e['brier']:>18.5f} {e_cal['brier']:>18.5f} | {str(outcome):>13} | {change:>+17.5f}{flag}")

print(f"\n{'Segment':<18} {'Base cal_mean':>13} {'Base cal_std':>12} | {'Exp cal_mean':>12} {'Exp cal_std':>11} | {'Base conf%':>10} {'Exp conf%':>9}")
print("-" * 95)
for seg in segments:
    b_cal = base_rows[seg]["cal"]
    e_cal = exp_rows[seg]["cal"]
    print(f"{seg:<18} {b_cal['mean']:>13.4f} {b_cal['std']:>12.4f} | {e_cal['mean']:>12.4f} {e_cal['std']:>11.4f} | {b_cal['conf%']:>9.1f}% {e_cal['conf%']:>8.1f}%")

# Feature importance for new features
print("\n--- Feature importance (XGB, sklearn) for expanded model ---")
fi_arr = m_exp.xgb.feature_importances_
sorted_fi = sorted(zip(EXPANDED_FEATS, fi_arr), key=lambda x: x[1], reverse=True)
for feat, gain in sorted_fi[:15]:
    flag = " *** NEW" if feat in NEW_FEATS else ""
    print(f"  {feat:<40} {gain:>8.5f}{flag}")

# save experiment results
import json as js
results = {"base": base_rows, "expanded": exp_rows, "new_feats": NEW_FEATS}
with open("data/exp_a_pp_results.json", "w") as f:
    js.dump(results, f, default=str)
print("\nSaved: data/exp_a_pp_results.json")
