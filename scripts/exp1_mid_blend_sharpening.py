"""
Experiment 1 — MID blend sharpening
Train MID model with 6 blend configs on pre-2024 data, evaluate on 2025+2026.
For each config: Brier, LogLoss, std, uncertain%, confident%
Calibration: fit isotonic on 2024 val set → apply to 2025+2026 test.

Blend configs:
  A) 50/50 XGB+LR (current champion)
  B) 70% XGB + 30% LR
  C) 80% XGB + 20% LR
  D) 100% XGB only
  E) LR only with C=0.1
  F) LR only with C=1.0
"""
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, joblib, json
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import log_loss

from bbl_pipeline.training.blend_model import XGBLRBlend

# ── data ─────────────────────────────────────────────────────────────────────
print("Loading data…")
df = pd.read_parquet("data/ipl_inn2_features_v1/training.parquet")
df["phase"] = df["over"].apply(lambda o: "PP" if 1<=o<=6 else ("MID" if 7<=o<=15 else "DEATH"))
mid = df[df["phase"] == "MID"].copy()

with open("models/ipl_inn2_v1/phase_features.json") as f:
    FEATS = json.load(f)["mid"]

TRAIN_SEASONS = {s for s in mid["season"].unique() if s < "2024"}
VAL_SEASONS   = {"2024"}
TEST_SEASONS  = {"2025", "2026"}

train = mid[mid["season"].isin(TRAIN_SEASONS)]
val   = mid[mid["season"].isin(VAL_SEASONS)]
test  = mid[mid["season"].isin(TEST_SEASONS)]
print(f"  Train: {len(train):,}  Val: {len(val):,}  Test: {len(test):,}")

X_train = train[FEATS].fillna(0).values
y_train = train["is_winner"].values
X_val   = val[FEATS].fillna(0).values
y_val   = val["is_winner"].values
X_test  = test[FEATS].fillna(0).values
y_test  = test["is_winner"].values

# ── blend helper ──────────────────────────────────────────────────────────────
def build_lr_only(c):
    pipe = Pipeline([
        ("imp", SimpleImputer(strategy="mean")),
        ("sc",  StandardScaler()),
        ("clf", LogisticRegression(C=c, max_iter=1000, random_state=42)),
    ])
    return pipe

def stats(p, y=None):
    p = np.clip(p, 0, 1)
    d = {
        "mean":    round(float(p.mean()), 4),
        "std":     round(float(p.std()),  4),
        "unc%":    round(float(((p>=0.45)&(p<=0.55)).mean()*100), 1),
        "conf%":   round(float(((p<0.30)|(p>0.70)).mean()*100), 1),
    }
    if y is not None:
        d["brier"] = round(float(np.mean((p - y)**2)), 5)
        d["logloss"] = round(float(log_loss(y, np.clip(p, 1e-7, 1-1e-7))), 5)
    return d

# ── experiment configs ────────────────────────────────────────────────────────
configs = [
    ("A  50/50 (current)",   "blend", 0.50, 0.01),
    ("B  70/30 XGB:LR",      "blend", 0.70, 0.01),
    ("C  80/20 XGB:LR",      "blend", 0.80, 0.01),
    ("D  XGB only",          "blend", 1.00, 0.01),
    ("E  LR C=0.1",          "lr",    0.00, 0.10),
    ("F  LR C=1.0",          "lr",    0.00, 1.00),
]

market_std  = 0.3947   # from distribution audit
market_unc  = 3.0
market_conf = 84.8

rows = []
for name, kind, xgb_w, lr_c in configs:
    print(f"\nTraining {name}…")

    if kind == "blend":
        m = XGBLRBlend(lr_c=lr_c)
        m.fit(X_train, y_train)
        p_xgb_val   = m.xgb.predict_proba(X_val)[:, 1]
        p_lr_val    = m.lr.predict_proba(X_val)[:, 1]
        p_xgb_test  = m.xgb.predict_proba(X_test)[:, 1]
        p_lr_test   = m.lr.predict_proba(X_test)[:, 1]
        raw_val  = xgb_w * p_xgb_val  + (1-xgb_w) * p_lr_val
        raw_test = xgb_w * p_xgb_test + (1-xgb_w) * p_lr_test
    else:  # LR-only
        pipe = build_lr_only(lr_c)
        pipe.fit(X_train, y_train)
        raw_val  = pipe.predict_proba(X_val)[:, 1]
        raw_test = pipe.predict_proba(X_test)[:, 1]

    # fit isotonic on val set
    iso = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
    iso.fit(raw_val, y_val)
    cal_test = iso.transform(raw_test)

    s_raw = stats(raw_test, y_test)
    s_cal = stats(cal_test, y_test)
    rows.append({
        "config": name,
        "raw_std": s_raw["std"],
        "cal_std": s_cal["std"],
        "raw_unc": s_raw["unc%"],
        "cal_unc": s_cal["unc%"],
        "raw_conf": s_raw["conf%"],
        "cal_conf": s_cal["conf%"],
        "raw_brier": s_raw["brier"],
        "cal_brier": s_cal["brier"],
        "raw_ll": s_raw["logloss"],
        "cal_ll": s_cal["logloss"],
    })

result = pd.DataFrame(rows)

print("\n")
print("=" * 100)
print("EXPERIMENT 1: MID BLEND SHARPENING  |  Test: 2025+2026")
print(f"  Market baseline: std={market_std}  unc={market_unc}%  conf={market_conf}%")
print("=" * 100)
print(f"\n{'Config':<22} {'raw_std':>8} {'cal_std':>8} | {'raw_unc':>8} {'cal_unc':>8} | {'raw_conf':>9} {'cal_conf':>9} | {'raw_brier':>10} {'cal_brier':>10} | {'raw_ll':>8} {'cal_ll':>8}")
print("-" * 120)
for _, r in result.iterrows():
    # highlight std vs market
    std_gap = r['cal_std'] - market_std
    std_flag = "<<" if abs(std_gap) < 0.005 else ("+" if std_gap > 0 else "-")
    print(f"{r['config']:<22} {r['raw_std']:>8.4f} {r['cal_std']:>8.4f}{std_flag}| {r['raw_unc']:>7.1f}% {r['cal_unc']:>7.1f}% | {r['raw_conf']:>8.1f}% {r['cal_conf']:>8.1f}% | {r['raw_brier']:>10.5f} {r['cal_brier']:>10.5f} | {r['raw_ll']:>8.5f} {r['cal_ll']:>8.5f}")

print("\nMarket ref:          " + " " * 8 + f"  {market_std}  " + " " * 8 + f"| {market_unc:>7.1f}% " + " " * 8 + f"| {market_conf:>8.1f}%")

# champion model on same test set for reference
champ = joblib.load("models/ipl_inn2_v1/champion_model_mid.joblib")
phase_cal_all = joblib.load("models/ipl_inn2_v1/phase_oof_calibrators.pkl")
raw_champ = champ.predict_proba(test[FEATS].fillna(0))[:, 1]
cal_champ = np.empty_like(raw_champ)
pc = phase_cal_all["mid"]
for ov in test["over"].unique():
    mask = (test["over"] == ov).values
    c = pc["per_over"].get(ov, pc["phase_iso"])
    cal_champ[mask] = c.transform(raw_champ[mask])
s_champ_r = stats(raw_champ, y_test)
s_champ_c = stats(cal_champ, y_test)
print(f"\n{'Champion (v11)' :<22} {s_champ_r['std']:>8.4f} {s_champ_c['std']:>8.4f} | {s_champ_r['unc%']:>7.1f}% {s_champ_c['unc%']:>7.1f}% | {s_champ_r['conf%']:>8.1f}% {s_champ_c['conf%']:>8.1f}% | {s_champ_r['brier']:>10.5f} {s_champ_c['brier']:>10.5f} | {s_champ_r['logloss']:>8.5f} {s_champ_c['logloss']:>8.5f}")

result.to_csv("data/exp1_mid_blend_results.csv", index=False)
print("\nSaved: data/exp1_mid_blend_results.csv")
