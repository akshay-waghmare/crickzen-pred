"""
Experiment 3 — Death uncertain-case review
Inspect all death-over balls where v11_cal is in [0.45, 0.55].
These are the 3% of death predictions sitting in the 'hesitant zone' that market never enters.
"""
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, joblib, json
from bbl_pipeline.training.blend_model import XGBLRBlend  # noqa

HOLDOUT = {"2025", "2026"}
df = pd.read_parquet("data/ipl_inn2_features_v1/training.parquet")
holdout = df[df["season"].isin(HOLDOUT)].copy()
death = holdout[(holdout["over"] >= 16) & (holdout["over"] <= 20)].copy()

with open("models/ipl_inn2_v1/phase_features.json") as f:
    FEATS = json.load(f)["death"]

m = joblib.load("models/ipl_inn2_v1/champion_model_death.joblib")
phase_cal = joblib.load("models/ipl_inn2_v1/phase_oof_calibrators.pkl")

raw = m.predict_proba(death[FEATS].fillna(0))[:, 1]
cal = np.empty_like(raw)
pc = phase_cal["death"]
for ov in death["over"].unique():
    mask = (death["over"] == ov).values
    c = pc["per_over"].get(ov, pc["phase_iso"])
    cal[mask] = c.transform(raw[mask])

death["v11_raw"] = raw
death["v11_cal"] = cal

uncertain = death[(death["v11_cal"] >= 0.45) & (death["v11_cal"] <= 0.55)].copy()
certain = death[~((death["v11_cal"] >= 0.45) & (death["v11_cal"] <= 0.55))].copy()

print("=" * 90)
print(f"EXPERIMENT 3: DEATH UNCERTAIN REVIEW  |  Holdout 2025+2026")
print(f"  Total death rows: {len(death):,}")
print(f"  Uncertain [0.45-0.55]: {len(uncertain):,} ({100*len(uncertain)/len(death):.1f}%)")
print(f"  Certain (<0.30 or >0.70): {(((death['v11_cal']<0.30)|(death['v11_cal']>0.70)).sum()):,} ({100*((death['v11_cal']<0.30)|(death['v11_cal']>0.70)).mean():.1f}%)")
print("=" * 90)

# ── distribution of overs in uncertain zone ────────────────────────────────
print("\n--- Over distribution (uncertain vs certain) ---")
ov_dist = pd.DataFrame({
    "n_uncertain": uncertain["over"].value_counts().sort_index(),
    "n_certain":   certain["over"].value_counts().sort_index(),
}).fillna(0).astype(int)
ov_dist["pct_uncertain"] = (ov_dist["n_uncertain"] / (ov_dist["n_uncertain"] + ov_dist["n_certain"]) * 100).round(1)
print(ov_dist.to_string())

# ── key numeric features for uncertain vs certain ──────────────────────────
key_cols = ["over", "wickets_lost", "score_vs_par", "required_run_rate", "current_run_rate",
            "resources_remaining", "overs_remaining", "balls_remaining", "v11_raw", "v11_cal"]
key_cols = [c for c in key_cols if c in death.columns]

print("\n--- Mean values: uncertain vs certain ---")
comp = pd.DataFrame({
    "uncertain": uncertain[key_cols].mean(),
    "certain":   certain[key_cols].mean(),
})
comp["diff"] = comp["uncertain"] - comp["certain"]
print(comp.round(3).to_string())

# ── chase state when uncertain ─────────────────────────────────────────────
print("\n--- Match situation for uncertain death balls ---")
print(f"  Mean over:          {uncertain['over'].mean():.1f}  (certain: {certain['over'].mean():.1f})")
print(f"  Mean wickets lost:  {uncertain['wickets_lost'].mean():.2f} (certain: {certain['wickets_lost'].mean():.2f})")
print(f"  Mean score_vs_par:  {uncertain['score_vs_par'].mean():.3f} (certain: {certain['score_vs_par'].mean():.3f})")
if "runs_remaining_approx" not in uncertain.columns and "chase_run_buffer" in uncertain.columns:
    print(f"  Mean chase_run_buf: {uncertain['chase_run_buffer'].mean():.2f} (certain: {certain['chase_run_buffer'].mean():.2f})")
if "chase_completion" in uncertain.columns:
    print(f"  Mean chase_compl:   {uncertain['chase_completion'].mean():.3f} (certain: {certain['chase_completion'].mean():.3f})")
if "rrr_times_wickets" in uncertain.columns:
    print(f"  Mean rrr×wkts:      {uncertain['rrr_times_wickets'].mean():.3f} (certain: {certain['rrr_times_wickets'].mean():.3f})")

# ── outcome distribution ───────────────────────────────────────────────────
print(f"\n--- Outcomes in uncertain zone ---")
print(f"  Actual win rate (uncertain): {uncertain['is_winner'].mean():.4f}  (should be ~0.50 if well-calibrated)")
print(f"  Actual win rate (certain):   {certain['is_winner'].mean():.4f}")
print(f"  Brier (uncertain):           {np.mean((uncertain['v11_cal'].values - uncertain['is_winner'].values)**2):.5f}")
print(f"  Brier (certain):             {np.mean((certain['v11_cal'].values - certain['is_winner'].values)**2):.5f}")

# ── match examples ────────────────────────────────────────────────────────
print(f"\n--- Sample uncertain death balls (showing match state) ---")
show_cols = [c for c in ["season","match_id","over","ball","batting_team","bowling_team",
             "wickets_lost","score_vs_par","current_run_rate","required_run_rate",
             "overs_remaining","v11_raw","v11_cal","is_winner"] if c in uncertain.columns]
sample = uncertain[show_cols].sort_values(["season","match_id","over"]).head(30)
pd.set_option("display.max_columns", None)
pd.set_option("display.width", 200)
print(sample.to_string(index=False))

# ── check if it's primarily over-16 (1st death over) ─────────────────────
print(f"\n--- % uncertain by over ---")
for ov in range(16, 21):
    sub = death[death["over"] == ov]
    unc = ((sub["v11_cal"] >= 0.45) & (sub["v11_cal"] <= 0.55)).sum()
    print(f"  Over {ov}: {unc}/{len(sub)} = {100*unc/len(sub):.1f}% uncertain")

uncertain.to_csv("data/exp3_death_uncertain_cases.csv", index=False)
print("\nSaved: data/exp3_death_uncertain_cases.csv")
