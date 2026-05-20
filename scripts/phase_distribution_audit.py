"""
Phase-wise Prediction Distribution Audit
Compares: v7 global model  vs  v11 phase models  vs  Market
Metrics: mean, std, %[0.45-0.55], %[<0.30 or >0.70], (raw vs calibrated)
Holdout: seasons 2025 + 2026
"""

import warnings; warnings.filterwarnings("ignore")
import pandas as pd
import numpy as np
import joblib, json

# ─── allow XGBLRBlend deserialization ────────────────────────────────────────
from bbl_pipeline.training.blend_model import XGBLRBlend  # noqa: F401

HOLDOUT_SEASONS = {"2025", "2026"}
PHASE_MAP = {"PP": (1, 6), "MID": (7, 15), "DEATH": (16, 20)}

V7_FEATS = [
    "resource_win_prob","score_vs_par","dls_pressure_index","run_rate_diff",
    "venue_chase_success","score_per_wicket","expected_final_score",
    "situation_advantage","team_strength_diff","batting_team_win_rate",
    "projected_score","target_above_par","inn1_death_rr","inn1_defendability",
    "batting_team_situation_wr","required_run_rate","projected_vs_venue_avg",
    "inn1_pp_runs","bowling_team_win_rate","bowling_team_situation_wr",
    "batting_won_toss","current_run_rate","chase_difficulty","inn1_wickets_lost",
    "pressure_index","wickets_times_balls","overs_remaining","rrr_times_wickets",
    "runs_last_18","boundary_pct_last_18","wickets_last_12","balls_since_wicket",
    "set_batter_exposure","wickets_last_6","runs_last_12","dot_pct_last_12",
    "is_powerplay",
]

# ─── load data ────────────────────────────────────────────────────────────────
print("Loading inn2 features…")
df = pd.read_parquet("data/ipl_inn2_features_v1/training.parquet")
df["phase"] = df["over"].apply(
    lambda o: "PP" if 1 <= o <= 6 else ("MID" if 7 <= o <= 15 else "DEATH")
)
holdout = df[df["season"].isin(HOLDOUT_SEASONS)].copy()
print(f"  Full: {len(df):,}  |  Holdout (2025+2026): {len(holdout):,}")

# ─── load models & calibrators ────────────────────────────────────────────────
print("Loading models…")
v7_model  = joblib.load("models/ipl_v7/champion_model.joblib")
v7_inn2_cal = joblib.load("models/ipl_v7/inn2_isotonic_calibrator.pkl")["calibrator"]

v11_models = {
    "PP":    joblib.load("models/ipl_inn2_v1/champion_model_pp.joblib"),
    "MID":   joblib.load("models/ipl_inn2_v1/champion_model_mid.joblib"),
    "DEATH": joblib.load("models/ipl_inn2_v1/champion_model_death.joblib"),
}
v11_phase_cal = joblib.load("models/ipl_inn2_v1/phase_oof_calibrators.pkl")
with open("models/ipl_inn2_v1/phase_features.json") as fh:
    phase_feats = {k.upper(): v for k, v in json.load(fh).items()}

# ─── market data ──────────────────────────────────────────────────────────────
market_df = pd.read_parquet("data/ipl_model_vs_market_v3.parquet")
# market_p_inn1 = P(inn1 team wins); for inn2 we need P(chasing team wins)
market_df["mkt_p"] = 1 - market_df["market_p_inn1"]
market_df = market_df[market_df["innings"] == 2][["match_id", "over", "mkt_p"]].dropna()
print(f"  Market rows (inn2): {len(market_df)}")

# ─── helpers ──────────────────────────────────────────────────────────────────
def dist_stats(probs: np.ndarray) -> dict:
    probs = np.clip(probs, 0, 1)
    return {
        "mean":     round(float(probs.mean()), 4),
        "std":      round(float(probs.std()),  4),
        "pct_uncertain": round(float(((probs >= 0.45) & (probs <= 0.55)).mean() * 100), 1),
        "pct_confident": round(float(((probs < 0.30) | (probs > 0.70)).mean() * 100), 1),
    }

def get_v11_cal(phase: str, over: int) -> object:
    """Return per-over calibrator with phase_iso fallback."""
    phase_data = v11_phase_cal[phase.lower()]
    per_over = phase_data["per_over"]
    if over in per_over:
        return per_over[over]
    return phase_data["phase_iso"]  # IsotonicRegression (not a dict)

# ─── compute predictions ──────────────────────────────────────────────────────
rows = []
for phase, (ov_lo, ov_hi) in PHASE_MAP.items():
    sub = holdout[(holdout["over"] >= ov_lo) & (holdout["over"] <= ov_hi)].copy()
    n = len(sub)
    print(f"\n{phase}: {n:,} rows  |  seasons={sub['season'].unique().tolist()}")

    # ── v7 raw ────────────────────────────────────────────────────────────────
    X7 = sub[V7_FEATS].fillna(0)          # keep as DataFrame — model uses col names
    v7_raw = v7_model.predict_proba(X7)[:, 1]

    # ── v7 calibrated (inn2 isotonic) ─────────────────────────────────────────
    v7_cal = v7_inn2_cal.transform(v7_raw)

    # ── v11 raw + calibrated ──────────────────────────────────────────────────
    X11 = sub[phase_feats[phase]].fillna(0).values
    v11_raw = v11_models[phase].predict_proba(X11)[:, 1]

    # per-row calibration (use over-specific calibrator)
    v11_cal_arr = np.empty_like(v11_raw)
    for over_val in sub["over"].unique():
        mask = (sub["over"] == over_val).values
        cal = get_v11_cal(phase, over_val)
        if cal is not None:
            v11_cal_arr[mask] = cal.transform(v11_raw[mask])
        else:
            v11_cal_arr[mask] = v11_raw[mask]

    # ── market (only where available) ─────────────────────────────────────────
    merged = sub[["match_id", "over"]].merge(market_df, on=["match_id", "over"], how="left")
    mkt_probs = merged["mkt_p"].values
    mkt_mask  = ~np.isnan(mkt_probs)
    n_mkt = int(mkt_mask.sum())

    # outcome for Brier
    y = sub["is_winner"].values
    def brier(p): return float(np.mean((p - y) ** 2))

    # ── collect stats ─────────────────────────────────────────────────────────
    def add_row(label, probs, n_pts):
        s = dist_stats(probs)
        rows.append({"phase": phase, "model": label, "n": n_pts, **s})

    add_row(f"v7 raw",   v7_raw, n)
    add_row(f"v7 cal",   v7_cal, n)
    add_row(f"v11 raw",  v11_raw, n)
    add_row(f"v11 cal",  v11_cal_arr, n)

    if n_mkt > 0:
        add_row("market", mkt_probs[mkt_mask], n_mkt)

    # ── print phase table inline ──────────────────────────────────────────────
    print(f"  ┌{'─'*22}┬{'─'*6}┬{'─'*8}┬{'─'*6}┬{'─'*11}┬{'─'*11}┐")
    print(f"  │{'Model':<22}│{'n':>6}│{'mean':>8}│{'std':>6}│{'%[0.45-0.55]':>11}│{'%[<.30|>.70]':>11}│")
    print(f"  ├{'─'*22}┼{'─'*6}┼{'─'*8}┼{'─'*6}┼{'─'*11}┼{'─'*11}┤")
    for r in rows[-max(5, (2 + (1 if n_mkt > 0 else 0)) * 2):]:
        if r["phase"] != phase: continue
        print(f"  │{r['model']:<22}│{r['n']:>6,}│{r['mean']:>8.4f}│{r['std']:>6.4f}│{r['pct_uncertain']:>10.1f}%│{r['pct_confident']:>10.1f}%│")
    print(f"  └{'─'*22}┴{'─'*6}┴{'─'*8}┴{'─'*6}┴{'─'*11}┴{'─'*11}┘")

# ─── combined inn2 table ──────────────────────────────────────────────────────
result = pd.DataFrame(rows)
print("\n\n========= COMBINED INN2 SUMMARY =========")
for model_label in ["v7 raw", "v7 cal", "v11 raw", "v11 cal", "market"]:
    sub = result[result["model"] == model_label]
    if sub.empty: continue
    n_tot = sub["n"].sum()
    # weighted average for distribution stats
    w_mean     = (sub["mean"] * sub["n"]).sum() / n_tot
    w_std      = (sub["std"]  * sub["n"]).sum() / n_tot
    w_unc      = (sub["pct_uncertain"] * sub["n"]).sum() / n_tot
    w_conf     = (sub["pct_confident"] * sub["n"]).sum() / n_tot
    phases_str = " | ".join([f"{r['phase']} std={r['std']:.4f} unc={r['pct_uncertain']:.1f}% conf={r['pct_confident']:.1f}%"
                              for _, r in sub.iterrows()])
    print(f"\n{model_label:12s}  n={n_tot:,}  mean={w_mean:.4f}  std={w_std:.4f}  "
          f"uncertain={w_unc:.1f}%  confident={w_conf:.1f}%")
    print(f"  [{phases_str}]")

print("\n\nDone.")
