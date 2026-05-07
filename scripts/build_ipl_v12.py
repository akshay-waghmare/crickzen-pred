"""
IPL v12 Champion Build Script
==============================
Changes vs v11:
  1. PP model: +5 easy-chase features (pp_ease_score, pp_rrr_ease,
     chase_ease_x_venue, low_target_strong_venue, pp_resources_adj_ease)
  2. MID calibration: Platt scaling (LogReg on logit space)
     instead of per-over isotonic (which collapses std on small val sets)
  3. Death: unchanged

Strategy:
  - Train champion models on ALL data (max data for champion)
  - OOF calibrators from 5-fold season CV (same OOF used for cal fitting)
  - True OOS eval: pre-2025 train/cal, 2025+2026 test — must beat v11 to promote

Output: models/ipl_v12/
  champion_model_pp.joblib
  champion_model_mid.joblib
  champion_model_death.joblib
  phase_oof_calibrators.pkl   (same structure as v11 — drop-in compatible)
  phase_features.json
  oof_results.csv
  OOS_COMPARISON.md
"""
import warnings; warnings.filterwarnings("ignore")
import json, pickle
import numpy as np
import pandas as pd
import joblib
from pathlib import Path
from scipy.special import logit, expit
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss

from bbl_pipeline.training.blend_model import XGBLRBlend

# ── paths ─────────────────────────────────────────────────────────────────────
DATA_DIR = Path("data/ipl_inn2_features_v1")
V11_DIR  = Path("models/ipl_inn2_v1")
OUT_DIR  = Path("models/ipl_v12")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── PlattCalibrator: API-compatible with IsotonicRegression ───────────────────
class PlattCalibrator:
    """Logistic regression in logit space. Preserves spread better than isotonic
    on small datasets. Use .transform(p) to apply — same API as IsotonicRegression."""

    def __init__(self, C: float = 1.0):
        self.C = C
        self._eps = 1e-6

    def fit(self, raw: np.ndarray, y: np.ndarray):
        X = logit(np.clip(raw, self._eps, 1 - self._eps)).reshape(-1, 1)
        self._lr = LogisticRegression(C=self.C, max_iter=2000, random_state=42)
        self._lr.fit(X, y.astype(int))
        return self

    def transform(self, raw: np.ndarray) -> np.ndarray:
        X = logit(np.clip(raw, self._eps, 1 - self._eps)).reshape(-1, 1)
        return self._lr.predict_proba(X)[:, 1]

    # sklearn-compat alias
    def predict(self, raw: np.ndarray) -> np.ndarray:
        return self.transform(raw)


# ── Feature engineering ───────────────────────────────────────────────────────
def add_pp_easy_chase_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute 5 PP easy-chase features. No side effects on other phases."""
    d = df.copy()
    rrr = d["required_run_rate"].clip(lower=0.1)
    tap = d["target_above_par"]
    vcs = d["venue_chase_success"]
    res = d["resources_remaining"]

    d["pp_ease_score"]          = (-tap) / rrr
    d["pp_rrr_ease"]             = 10.0 - d["required_run_rate"]
    d["chase_ease_x_venue"]      = (-tap.clip(upper=0)) * vcs
    d["low_target_strong_venue"] = (tap < -15).astype(float) * vcs
    d["pp_resources_adj_ease"]   = (-tap) * res
    return d


NEW_PP_FEATS = [
    "pp_ease_score", "pp_rrr_ease", "chase_ease_x_venue",
    "low_target_strong_venue", "pp_resources_adj_ease",
]

# ── Load v11 feature lists ────────────────────────────────────────────────────
with open(V11_DIR / "phase_features.json") as f:
    V11_FEATS = json.load(f)

V12_FEATS = {
    "pp":    V11_FEATS["pp"] + NEW_PP_FEATS,
    "mid":   V11_FEATS["mid"],    # unchanged
    "death": V11_FEATS["death"],  # unchanged
}

PHASE_OVERS = {"pp": (1, 6), "mid": (7, 15), "death": (16, 20)}

# ── Data loading ──────────────────────────────────────────────────────────────
print("Loading data…")
df = pd.read_parquet(DATA_DIR / "training.parquet")
df = df.sort_values(["match_id", "innings", "over", "ball"]).reset_index(drop=True)
df = df[df["innings"] == 2].copy()
df = add_pp_easy_chase_features(df)
ALL_SEASONS = sorted(df["season"].unique())
print(f"  Inn2 rows: {len(df):,}  seasons: {ALL_SEASONS}")


def safe_X(df_s: pd.DataFrame, feats: list) -> np.ndarray:
    avail = [f for f in feats if f in df_s.columns]
    med   = df_s[avail].median()
    return df_s[avail].fillna(med).values, avail


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 1 — OOF calibrators (5-fold season CV on ALL data)
# ═══════════════════════════════════════════════════════════════════════════════
print("\nStep 1: OOF season-fold CV for calibrators…")

def oof_season_cv(phase_df: pd.DataFrame, feats: list, n_folds: int = 5):
    seasons = sorted(phase_df["season"].unique())
    fold_size = max(1, len(seasons) // n_folds)
    n = len(phase_df)
    oof_raw = np.zeros(n)
    oof_y   = phase_df["is_winner"].values.copy()
    oof_over = phase_df["over"].values.copy()

    for fold in range(n_folds):
        val_s  = seasons[fold * fold_size: (fold + 1) * fold_size] if fold < n_folds-1 else seasons[fold * fold_size:]
        tr_s   = [s for s in seasons if s not in val_s]
        tr_mask  = phase_df["season"].isin(tr_s)
        val_mask = phase_df["season"].isin(val_s)

        X_tr, avail = safe_X(phase_df[tr_mask], feats)
        X_va, _     = safe_X(phase_df[val_mask], feats)
        y_tr = phase_df.loc[tr_mask, "is_winner"].values

        m = XGBLRBlend()
        m.fit(X_tr, y_tr)
        oof_raw[val_mask.values] = m.predict_proba(X_va)[:, 1]
        fold_brier = brier_score_loss(phase_df.loc[val_mask, "is_winner"].values, oof_raw[val_mask.values])
        print(f"    fold {fold}: val={val_s}, n={val_mask.sum():,}, brier={fold_brier:.4f}")

    overall_brier = brier_score_loss(oof_y, oof_raw)
    return oof_raw, oof_y, oof_over, overall_brier

oof_data = {}
for phase, (lo, hi) in PHASE_OVERS.items():
    print(f"\n  Phase: {phase.upper()} (overs {lo}-{hi})")
    pf = df[(df["over"] >= lo) & (df["over"] <= hi)].copy().reset_index(drop=True)
    feats = V12_FEATS[phase]
    oof_raw, oof_y, oof_over, b = oof_season_cv(pf, feats)
    print(f"  OOF Brier (raw): {b:.5f}")
    oof_data[phase] = {"raw": oof_raw, "y": oof_y, "over": oof_over, "brier_raw": b}

# ── Build phase_oof_calibrators (v11-compatible structure) ────────────────────
# Structure: {phase: {"per_over": {int_over: calibrator}, "phase_iso": calibrator}}
# PP + Death: per-over isotonic (same as v11)
# MID: Platt scaling for phase_iso; per-"over" Platt for per_over

print("\nFitting calibrators on OOF predictions…")
phase_oof_cals = {}

for phase in ["pp", "mid", "death"]:
    od = oof_data[phase]
    raw, y, overs = od["raw"], od["y"], od["over"]
    phase_cals = {}

    if phase == "mid":
        # Phase-level Platt
        platt = PlattCalibrator(C=1.0)
        platt.fit(raw, y)
        phase_iso = platt
        # Per-over Platt
        per_over = {}
        for ov in sorted(np.unique(overs)):
            mask = overs == ov
            if mask.sum() >= 40:
                p2 = PlattCalibrator(C=1.0)
                p2.fit(raw[mask], y[mask])
                per_over[int(ov)] = p2
        print(f"  MID: phase Platt fitted; per-over Platt for {len(per_over)} overs")
    else:
        # Phase-level isotonic fallback
        iso_phase = IsotonicRegression(out_of_bounds="clip")
        iso_phase.fit(raw, y)
        phase_iso = iso_phase
        # Per-over isotonic
        per_over = {}
        for ov in sorted(np.unique(overs)):
            mask = overs == ov
            if mask.sum() >= 40:
                iso = IsotonicRegression(out_of_bounds="clip")
                iso.fit(raw[mask], y[mask])
                per_over[int(ov)] = iso
        print(f"  {phase.upper()}: phase_iso + {len(per_over)} per-over isotonic")

    phase_oof_cals[phase] = {"per_over": per_over, "phase_iso": phase_iso}

# save calibrators
with open(OUT_DIR / "phase_oof_calibrators.pkl", "wb") as f:
    pickle.dump(phase_oof_cals, f)
print(f"  Saved: {OUT_DIR / 'phase_oof_calibrators.pkl'}")


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 2 — Train champion models on ALL data
# ═══════════════════════════════════════════════════════════════════════════════
print("\nStep 2: Training champion models on ALL data…")
champion_models = {}

for phase, (lo, hi) in PHASE_OVERS.items():
    pf = df[(df["over"] >= lo) & (df["over"] <= hi)].copy()
    feats = V12_FEATS[phase]
    X, avail = safe_X(pf, feats)
    y = pf["is_winner"].values
    print(f"  {phase.upper()}: {len(pf):,} rows × {len(avail)} features")
    m = XGBLRBlend()
    m.fit(X, y)
    champion_models[phase] = (m, avail)
    joblib.dump(m, OUT_DIR / f"champion_model_{phase}.joblib")
    print(f"    Saved: champion_model_{phase}.joblib")

# save feature registry
feat_registry = {p: feats for p, (_, feats) in champion_models.items()}
with open(OUT_DIR / "phase_features.json", "w") as f:
    json.dump(feat_registry, f, indent=2)
print(f"  Saved: phase_features.json")


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 3 — True OOS Evaluation: pre-2025 vs 2025+2026
# ═══════════════════════════════════════════════════════════════════════════════
print("\nStep 3: True OOS evaluation (train<2025, test=2025+2026)…")

OOS_TRAIN_SEASONS = {s for s in ALL_SEASONS if s < "2025"}
OOS_TEST_SEASONS  = {s for s in ALL_SEASONS if s >= "2025"}
print(f"  OOS train seasons: {sorted(OOS_TRAIN_SEASONS)}")
print(f"  OOS test  seasons: {sorted(OOS_TEST_SEASONS)}")


def apply_oof_cals(raw: np.ndarray, overs: np.ndarray, cals: dict, phase: str) -> np.ndarray:
    """Apply per-over calibrator with phase fallback."""
    cal_out = np.empty_like(raw)
    phase_key = phase.lower()
    ph_cals = cals.get(phase_key, cals.get(phase, {}))
    per_over = ph_cals.get("per_over", {})
    phase_iso = ph_cals.get("phase_iso", None)

    for ov in np.unique(overs):
        mask = overs == ov
        if int(ov) in per_over:
            cal_out[mask] = per_over[int(ov)].transform(raw[mask])
        elif phase_iso is not None:
            cal_out[mask] = phase_iso.transform(raw[mask])
        else:
            cal_out[mask] = raw[mask]
    return cal_out


def oos_eval(model_label: str, phase_models_dict: dict, cal_dict: dict):
    """
    Evaluate model on OOS test (2025+2026).
    phase_models_dict: {phase: (model, feats)}
    cal_dict: phase_oof_calibrators dict
    Returns per-phase and overall metrics.
    """
    all_raw, all_cal, all_y = [], [], []
    phase_results = {}

    for phase, (lo, hi) in PHASE_OVERS.items():
        pf_tr = df[(df["over"] >= lo) & (df["over"] <= hi) & (df["season"].isin(OOS_TRAIN_SEASONS))].copy()
        pf_te = df[(df["over"] >= lo) & (df["over"] <= hi) & (df["season"].isin(OOS_TEST_SEASONS))].copy()

        if len(pf_te) == 0:
            continue

        m, feats = phase_models_dict[phase]
        # Train fresh on OOS_TRAIN (fair comparison — don't use champion trained on all data)
        Xtr, avail = safe_X(pf_tr, feats)
        ytr = pf_tr["is_winner"].values
        oos_m = XGBLRBlend()
        oos_m.fit(Xtr, ytr)

        Xte, _ = safe_X(pf_te, feats)
        yte    = pf_te["is_winner"].values
        overs_te = pf_te["over"].values

        raw_te = oos_m.predict_proba(Xte)[:, 1]

        # Fit phase calibrators on OOF of train data
        Xtr_oof, _ = safe_X(pf_tr, feats)
        oof_raw_tr  = np.zeros(len(Xtr))
        seasons_tr = sorted(pf_tr["season"].unique())
        fold_size = max(1, len(seasons_tr) // 5)
        for fold in range(5):
            vs = seasons_tr[fold*fold_size: (fold+1)*fold_size] if fold < 4 else seasons_tr[fold*fold_size:]
            ts = [s for s in seasons_tr if s not in vs]
            tm = pf_tr["season"].isin(ts)
            vm = pf_tr["season"].isin(vs)
            if vm.sum() < 10 or tm.sum() < 100: continue
            Xf, _ = safe_X(pf_tr[tm], feats)
            yf = pf_tr.loc[tm, "is_winner"].values
            fm = XGBLRBlend()
            fm.fit(Xf, yf)
            Xv, _ = safe_X(pf_tr[vm], feats)
            oof_raw_tr[vm.values] = fm.predict_proba(Xv)[:, 1]

        # Fit calibrators on OOF
        if phase == "mid":
            ph_cal = PlattCalibrator(C=1.0)
            ph_cal.fit(oof_raw_tr, ytr)
        else:
            ph_cal = IsotonicRegression(out_of_bounds="clip")
            ph_cal.fit(oof_raw_tr, ytr)
        cal_te = ph_cal.transform(raw_te)

        brier_raw = float(brier_score_loss(yte, raw_te))
        brier_cal = float(brier_score_loss(yte, cal_te))
        phase_results[phase] = {"brier_raw": brier_raw, "brier_cal": brier_cal, "n": len(yte)}

        all_raw.extend(raw_te.tolist())
        all_cal.extend(cal_te.tolist())
        all_y.extend(yte.tolist())

    all_raw = np.array(all_raw)
    all_cal = np.array(all_cal)
    all_y   = np.array(all_y)
    overall_raw = float(brier_score_loss(all_y, all_raw))
    overall_cal = float(brier_score_loss(all_y, all_cal))

    return {"overall_raw": overall_raw, "overall_cal": overall_cal, "phases": phase_results}


# V11 baseline (same feature sets as v11, isotonic for all phases)
print("\n  Building V11 baseline (OOS train<2025)…")
v11_phase_models = {}
for phase, (lo, hi) in PHASE_OVERS.items():
    v11_feats = V11_FEATS[phase]
    pf_tr = df[(df["over"] >= lo) & (df["over"] <= hi) & (df["season"].isin(OOS_TRAIN_SEASONS))].copy()
    Xtr, avail = safe_X(pf_tr, v11_feats)
    ytr = pf_tr["is_winner"].values
    m = XGBLRBlend()
    m.fit(Xtr, ytr)
    v11_phase_models[phase] = (m, avail)

v11_res = oos_eval("v11_baseline", v11_phase_models, None)

# V12 (expanded PP + Platt MID)
print("\n  Building V12 (OOS train<2025)…")
v12_phase_models = {}
for phase, (lo, hi) in PHASE_OVERS.items():
    v12_feats = V12_FEATS[phase]
    pf_tr = df[(df["over"] >= lo) & (df["over"] <= hi) & (df["season"].isin(OOS_TRAIN_SEASONS))].copy()
    Xtr, avail = safe_X(pf_tr, v12_feats)
    ytr = pf_tr["is_winner"].values
    m = XGBLRBlend()
    m.fit(Xtr, ytr)
    v12_phase_models[phase] = (m, avail)

v12_res = oos_eval("v12", v12_phase_models, None)


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 4 — Report
# ═══════════════════════════════════════════════════════════════════════════════
print("\n")
print("=" * 90)
print("IPL v12 BUILD — OOS COMPARISON  (train: pre-2025, test: 2025+2026)")
print("=" * 90)

def pct_change(a, b):
    return f"{(a-b)/b*100:+.1f}%"

v11_overall = v11_res["overall_cal"]
v12_overall = v12_res["overall_cal"]
win = "✅ v12 WINS" if v12_overall < v11_overall else "❌ v12 LOSES"
print(f"\n{'Phase':<12} {'v11 cal':>10} {'v12 cal':>10} {'Change':>10} {'v11 raw':>10} {'v12 raw':>10}")
print("-" * 65)
print(f"  {'Overall':<10} {v11_overall:>10.5f} {v12_overall:>10.5f} {pct_change(v12_overall, v11_overall):>10} {'':>10} {'':>10}")
for phase in ["pp", "mid", "death"]:
    v11_p = v11_res["phases"].get(phase, {})
    v12_p = v12_res["phases"].get(phase, {})
    if not v11_p or not v12_p: continue
    chg   = pct_change(v12_p["brier_cal"], v11_p["brier_cal"])
    flag  = " ✅" if v12_p["brier_cal"] < v11_p["brier_cal"] else " ❌"
    print(f"  {phase.upper():<10} {v11_p['brier_cal']:>10.5f} {v12_p['brier_cal']:>10.5f} {chg:>10}{flag}  "
          f"(n={v12_p['n']}  raw: v11={v11_p['brier_raw']:.5f} v12={v12_p['brier_raw']:.5f})")

print(f"\n  Overall: {win}  ({pct_change(v12_overall, v11_overall)} Brier)")

# Promotion decision
n_phases_won = sum(
    1 for p in ["pp", "mid", "death"]
    if v12_res["phases"].get(p, {}).get("brier_cal", 999) < v11_res["phases"].get(p, {}).get("brier_cal", 999)
)
print(f"\n  v12 wins on {n_phases_won}/3 phases")
promote = (v12_overall < v11_overall) and (n_phases_won >= 2)
print(f"  Promotion decision: {'PROMOTE v12' if promote else 'KEEP v11 as champion'}")
if not promote:
    print("  (Requires: overall v12 < v11 AND win ≥ 2 of 3 phases)")

# Save OOF Brier to csv
oof_rows = []
for phase in ["pp", "mid", "death"]:
    oof_rows.append({
        "phase": phase,
        "v12_oof_brier_raw": round(oof_data[phase]["brier_raw"], 5),
        "v11_baseline_oos_cal": round(v11_res["phases"].get(phase, {}).get("brier_cal", float("nan")), 5),
        "v12_oos_cal":          round(v12_res["phases"].get(phase, {}).get("brier_cal", float("nan")), 5),
    })
pd.DataFrame(oof_rows).to_csv(OUT_DIR / "oof_results.csv", index=False)
print(f"\n  Saved: {OUT_DIR / 'oof_results.csv'}")

# ── Write OOS comparison markdown ─────────────────────────────────────────────
lines = [
    "# IPL v12 — OOS Comparison Report\n",
    f"**Train seasons:** {sorted(OOS_TRAIN_SEASONS)}\n",
    f"**Test seasons:** {sorted(OOS_TEST_SEASONS)}\n\n",
    "## Changes vs v11\n",
    "- **PP model**: +5 easy-chase features (`pp_ease_score`, `pp_rrr_ease`, `chase_ease_x_venue`, `low_target_strong_venue`, `pp_resources_adj_ease`)\n",
    "- **MID calibration**: Platt scaling (log-loss optimal) instead of per-over isotonic (which degenerates on small val sets)\n",
    "- **Death**: unchanged\n\n",
    "## Results\n\n",
    "| Phase | v11 cal | v12 cal | Change |\n",
    "|-------|---------|---------|--------|\n",
    f"| **Overall** | {v11_overall:.5f} | {v12_overall:.5f} | **{pct_change(v12_overall, v11_overall)}** |\n",
]
for phase in ["pp", "mid", "death"]:
    v11_p = v11_res["phases"].get(phase, {})
    v12_p = v12_res["phases"].get(phase, {})
    if v11_p and v12_p:
        chg = pct_change(v12_p["brier_cal"], v11_p["brier_cal"])
        lines.append(f"| {phase.upper()} | {v11_p['brier_cal']:.5f} | {v12_p['brier_cal']:.5f} | {chg} |\n")

lines.append(f"\n**Verdict: {'PROMOTE v12' if promote else 'KEEP v11 as champion'}**\n")
(OUT_DIR / "OOS_COMPARISON.md").write_text("".join(lines), encoding="utf-8")
print(f"  Saved: {OUT_DIR / 'OOS_COMPARISON.md'}")

print("\n  v12 artifacts ready in:", OUT_DIR)
print("DONE.")
