"""
Experiment 2 — PP bias investigation
Where does the +0.078 mean bias (v11 vs market) come from?
Segment PP predictions by: target range, venue, toss, score vs par, team WR, wickets, overs 0-3 vs 4-6.
"""
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, joblib, json
from bbl_pipeline.training.blend_model import XGBLRBlend  # noqa

HOLDOUT = {"2025", "2026"}
df = pd.read_parquet("data/ipl_inn2_features_v1/training.parquet")
holdout = df[df["season"].isin(HOLDOUT)].copy()
pp = holdout[(holdout["over"] >= 1) & (holdout["over"] <= 6)].copy()

with open("models/ipl_inn2_v1/phase_features.json") as f:
    FEATS = json.load(f)["pp"]

m_pp = joblib.load("models/ipl_inn2_v1/champion_model_pp.joblib")
phase_cal = joblib.load("models/ipl_inn2_v1/phase_oof_calibrators.pkl")

# get v11 PP raw + calibrated predictions
raw = m_pp.predict_proba(pp[FEATS].fillna(0))[:, 1]
cal = np.empty_like(raw)
pc = phase_cal["pp"]
for ov in pp["over"].unique():
    mask = (pp["over"] == ov).values
    c = pc["per_over"].get(ov, pc["phase_iso"])
    cal[mask] = c.transform(raw[mask])

pp = pp.copy()
pp["v11_raw"]   = raw
pp["v11_cal"]   = cal
pp["outcome"]   = pp["is_winner"].values

# market join
mkt = pd.read_parquet("data/ipl_model_vs_market_v3.parquet")
mkt = mkt[mkt["innings"] == 2][["match_id", "over", "market_p_inn1"]].copy()
mkt["mkt_p"] = 1 - mkt["market_p_inn1"]
pp = pp.merge(mkt[["match_id", "over", "mkt_p"]], on=["match_id", "over"], how="left")

has_mkt = pp["mkt_p"].notna()
n_mkt = has_mkt.sum()

def seg_report(name, mask, df=pp):
    sub = df[mask]
    n = len(sub)
    if n < 10:
        return None
    mkt_sub = sub[sub["mkt_p"].notna()]
    row = {
        "segment": name,
        "n": n,
        "v11_mean": round(sub["v11_cal"].mean(), 4),
        "outcome_rate": round(sub["outcome"].mean(), 4),
        "mkt_mean": round(mkt_sub["mkt_p"].mean(), 4) if len(mkt_sub) > 5 else None,
        "n_mkt": len(mkt_sub),
        "model_bias": round(sub["v11_cal"].mean() - sub["outcome"].mean(), 4),
    }
    return row

rows = []

# ── segment 1: over band ──────────────────────────────────────────────────────
rows.append(seg_report("PP ov 1-3", (pp["over"] <= 3)))
rows.append(seg_report("PP ov 4-6", (pp["over"] >= 4) & (pp["over"] <= 6)))

# ── segment 2: target range ───────────────────────────────────────────────────
# target = projected_score for inn1 roughly, or score_vs_par
# We need to derive target from the data — use the required_run_rate × balls_remaining
# Or: use `target_above_par` which is in features
if "target_above_par" in pp.columns:
    tq = pp["target_above_par"].quantile([0.33, 0.67])
    rows.append(seg_report("Target: Low", (pp["target_above_par"] <= tq[0.33])))
    rows.append(seg_report("Target: Par", (pp["target_above_par"] > tq[0.33]) & (pp["target_above_par"] <= tq[0.67])))
    rows.append(seg_report("Target: High", (pp["target_above_par"] > tq[0.67])))

# ── segment 3: chase category ─────────────────────────────────────────────────
if "chase_category" in pp.columns:
    for cat in pp["chase_category"].dropna().unique():
        r = seg_report(f"Chase cat: {cat}", (pp["chase_category"] == cat))
        if r: rows.append(r)

# ── segment 4: toss decision ──────────────────────────────────────────────────
if "batting_won_toss" in pp.columns:
    rows.append(seg_report("Toss: chaser won", (pp["batting_won_toss"] == 1)))
    rows.append(seg_report("Toss: chaser lost", (pp["batting_won_toss"] == 0)))

# ── segment 5: batting team WR (team strength) ────────────────────────────────
if "batting_team_win_rate" in pp.columns:
    wq = pp["batting_team_win_rate"].quantile([0.33, 0.67])
    rows.append(seg_report("Bat WR: weak", (pp["batting_team_win_rate"] <= wq[0.33])))
    rows.append(seg_report("Bat WR: mid", (pp["batting_team_win_rate"] > wq[0.33]) & (pp["batting_team_win_rate"] <= wq[0.67])))
    rows.append(seg_report("Bat WR: strong", (pp["batting_team_win_rate"] > wq[0.67])))

# ── segment 6: wickets lost ───────────────────────────────────────────────────
if "wickets_lost" in pp.columns:
    rows.append(seg_report("Wkts lost: 0", (pp["wickets_lost"] == 0)))
    rows.append(seg_report("Wkts lost: 1-2", (pp["wickets_lost"] >= 1) & (pp["wickets_lost"] <= 2)))
    rows.append(seg_report("Wkts lost: 3+", (pp["wickets_lost"] >= 3)))

# ── segment 7: venue chase success ───────────────────────────────────────────
if "venue_chase_success" in pp.columns:
    vq = pp["venue_chase_success"].quantile([0.33, 0.67])
    rows.append(seg_report("Venue chase: low", (pp["venue_chase_success"] <= vq[0.33])))
    rows.append(seg_report("Venue chase: high", (pp["venue_chase_success"] > vq[0.67])))

# ── segment 8: score vs par ───────────────────────────────────────────────────
if "score_vs_par" in pp.columns:
    sq = pp["score_vs_par"].quantile([0.33, 0.67])
    rows.append(seg_report("ScoreVsPar: behind", (pp["score_vs_par"] <= sq[0.33])))
    rows.append(seg_report("ScoreVsPar: ahead", (pp["score_vs_par"] > sq[0.67])))

result = pd.DataFrame([r for r in rows if r is not None])

print("=" * 95)
print("EXPERIMENT 2: PP BIAS INVESTIGATION  |  Holdout 2025+2026")
print(f"  Overall PP: v11_mean={pp['v11_cal'].mean():.4f}  outcome_rate={pp['outcome'].mean():.4f}  "
      f"mkt_mean={pp[pp['mkt_p'].notna()]['mkt_p'].mean():.4f}  n={len(pp):,}  n_mkt={n_mkt}")
print("  model_bias = v11_cal_mean - actual_outcome_rate")
print("=" * 95)
print(f"\n{'Segment':<25} {'n':>6} {'v11_mean':>10} {'outcome':>10} {'mkt_mean':>10} {'model_bias':>12} {'n_mkt':>7}")
print("-" * 90)
for _, r in result.iterrows():
    bias_flag = "  *** LARGE" if abs(r["model_bias"]) > 0.08 else ("  ** notable" if abs(r["model_bias"]) > 0.04 else "")
    mkt_str = f"{r['mkt_mean']:.4f}" if r["mkt_mean"] is not None else "    N/A"
    print(f"{r['segment']:<25} {r['n']:>6,} {r['v11_mean']:>10.4f} {r['outcome_rate']:>10.4f} {mkt_str:>10} {r['model_bias']:>+12.4f}{bias_flag}   mkt_n={r['n_mkt']}")

result.to_csv("data/exp2_pp_bias_segments.csv", index=False)
print("\nSaved: data/exp2_pp_bias_segments.csv")
