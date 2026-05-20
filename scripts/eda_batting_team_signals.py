"""
EDA: Batting team + defendability + venue averages + score bands + NRR
Explores which combinations best predict match outcome for IPL v9 feature ideas.
"""
import pandas as pd
import numpy as np
import warnings
from sklearn.metrics import brier_score_loss

warnings.filterwarnings("ignore")

# ── Build match-level dataset ──────────────────────────────────────────────
raw = pd.read_parquet("data/ipl_raw/matches")

inn1 = (
    raw[raw["innings"] == 1]
    .groupby("match_id")
    .agg(
        date=("date", "first"),
        season=("season", "first"),
        venue=("venue_id", "first"),
        team1=("batting_team", "first"),
        winner=("winner", "first"),
        inn1_score=("runs_total", "sum"),
        inn1_overs=("over", "max"),
        inn1_wkts=("wicket_type", lambda x: x.notna().sum()),
    )
    .reset_index()
)
inn2 = (
    raw[raw["innings"] == 2]
    .groupby("match_id")
    .agg(
        team2=("batting_team", "first"),
        inn2_score=("runs_total", "sum"),
        inn2_overs=("over", "max"),
        inn2_wkts=("wicket_type", lambda x: x.notna().sum()),
    )
    .reset_index()
)

m = inn1.merge(inn2, on="match_id").sort_values("date").reset_index(drop=True)
m["date"] = pd.to_datetime(m["date"])
m["inn1_overs"] += 1
m["inn2_overs"] += 1
m["team1_won"] = (m["winner"] == m["team1"]).astype(float)
m = m[~m["winner"].isna()].copy()

# NRR for team1 perspective (positive = team1 scored faster)
m["nrr"] = m["inn1_score"] / m["inn1_overs"] - m["inn2_score"] / m["inn2_overs"]

print(f"Total matches: {len(m)}  | Seasons: {sorted(m.season.unique())}")
print(f"Venues: {m.venue.nunique()}  Teams: {pd.concat([m.team1, m.team2]).nunique()}")


# ── 1. VENUE AVERAGES ────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("1. VENUE AVERAGES — Inn1 score distribution")
print("=" * 60)

venue_stats = (
    m.groupby("venue")["inn1_score"]
    .agg(n="count", mean="mean", med="median", std="std",
         p25=lambda x: x.quantile(0.25), p75=lambda x: x.quantile(0.75))
    .reset_index()
    .sort_values("mean", ascending=False)
)
print(venue_stats[venue_stats["n"] >= 15].to_string(index=False))

# Team-specific venue average vs overall venue average
m["venue_avg"] = m.groupby("venue")["inn1_score"].transform("mean")
m["score_vs_venue"] = m["inn1_score"] - m["venue_avg"]  # above/below venue par
m["venue_chase_pct"] = m.groupby("venue")["team1_won"].transform("mean")


# ── 2. DEFENDABILITY ANALYSIS ─────────────────────────────────────────────────
print("\n" + "=" * 60)
print("2. DEFENDABILITY — Does scoring above venue par predict win?")
print("=" * 60)

# Bin score_vs_venue into buckets
bins = [-999, -30, -15, 0, 15, 30, 999]
labels = ["<-30", "-30 to -15", "-15 to 0", "0 to +15", "+15 to +30", ">+30"]
m["vs_venue_bin"] = pd.cut(m["score_vs_venue"], bins=bins, labels=labels)
defend = (
    m.groupby("vs_venue_bin", observed=True)["team1_won"]
    .agg(n="count", win_rate="mean")
    .reset_index()
)
print("\n Inn1 score vs venue par → win rate:")
print(defend.to_string(index=False))

# Correlation: score_vs_venue with outcome
r_defend = m[["score_vs_venue", "team1_won"]].corr().iloc[0, 1]
print(f"\n  r(score_vs_venue, outcome) = {r_defend:.4f}")


# ── 3. SCORE BANDS (low / mid / high) ─────────────────────────────────────────
print("\n" + "=" * 60)
print("3. SCORE BANDS — Does batting team matter more in low/high scoring games?")
print("=" * 60)

m["score_band"] = pd.cut(
    m["inn1_score"],
    bins=[0, 140, 160, 180, 999],
    labels=["Low(<140)", "Mid(140-160)", "High(160-180)", "Very High(>180)"],
)
score_band_wr = (
    m.groupby("score_band", observed=True)["team1_won"]
    .agg(n="count", win_rate="mean")
    .reset_index()
)
print("\n Score band → overall win rate (team batting first):")
print(score_band_wr.to_string(index=False))

# Team-specific win rate by score band
print("\n Top-5 team win rates by score band (n>=8):")
for band in ["Low(<140)", "High(160-180)", "Very High(>180)"]:
    sub = m[m["score_band"] == band]
    t = (
        sub.groupby("team1")["team1_won"]
        .agg(n="count", win_rate="mean")
        .reset_index()
        .query("n >= 8")
        .sort_values("win_rate", ascending=False)
        .head(5)
    )
    print(f"\n  {band} (n={len(sub)}):")
    print(t.to_string(index=False))


# ── 4. TEAM VENUE AVERAGES vs OVERALL ──────────────────────────────────────────
print("\n" + "=" * 60)
print("4. TEAM VENUE AVERAGES — Home/regular venue advantage")
print("=" * 60)

team_venue = (
    m.groupby(["team1", "venue"])
    .agg(n=("team1_won", "count"), win_rate=("team1_won", "mean"),
         avg_score=("inn1_score", "mean"))
    .reset_index()
    .query("n >= 8")
    .sort_values("win_rate", ascending=False)
)
print("\n Team + venue combos (n>=8), by win rate:")
print(team_venue.head(15).to_string(index=False))

# Does team's venue-specific WR differ from their overall WR?
team_overall = m.groupby("team1")["team1_won"].mean().reset_index()
team_overall.columns = ["team1", "overall_wr"]
tv_merged = team_venue.merge(team_overall, on="team1")
tv_merged["venue_lift"] = tv_merged["win_rate"] - tv_merged["overall_wr"]
print("\n Biggest venue lifts (team performs better at a specific venue):")
print(tv_merged.sort_values("venue_lift", ascending=False).head(10)[
    ["team1", "venue", "n", "win_rate", "overall_wr", "venue_lift"]
].to_string(index=False))


# ── 5. NRR ANALYSIS ────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("5. NRR DISTRIBUTION — Does NRR margin correlate with signal?")
print("=" * 60)

print(f"\n NRR stats: mean={m.nrr.mean():.2f}, std={m.nrr.std():.2f}")
print(f" r(nrr, team1_won) = {m[['nrr','team1_won']].corr().iloc[0,1]:.4f}  [by design: team1 won if nrr>0 essentially]")

# Rolling team NRR (from recency EDA)
mf = pd.read_parquet("data/_eda_match_form.parquet")
# Check what columns we have
print("\n Form parquet cols:", mf.columns.tolist())
m2 = m.merge(mf[["match_id", "nrr_diff_l5", "wr_diff_l5", "wr_diff_c", "nrr_diff_c"]], on="match_id", how="left")

print(f"\n r(wr_diff_l5, team1_won)    = {m2[['wr_diff_l5','team1_won']].corr().iloc[0,1]:.4f}")
print(f" r(nrr_diff_l5, team1_won)   = {m2[['nrr_diff_l5','team1_won']].corr().iloc[0,1]:.4f}")
print(f" r(wr_diff_c, team1_won)     = {m2[['wr_diff_c','team1_won']].corr().iloc[0,1]:.4f}")
print(f" r(nrr_diff_c, team1_won)    = {m2[['nrr_diff_c','team1_won']].corr().iloc[0,1]:.4f}")
print(f" r(score_vs_venue, outcome)  = {m2[['score_vs_venue','team1_won']].corr().iloc[0,1]:.4f}")


# ── 6. COMBINED: DEFENDABILITY + FORM + NRR ────────────────────────────────────
print("\n" + "=" * 60)
print("6. COMBINED SIGNAL — defendability × form × NRR at match level")
print("=" * 60)

# Composite: score_vs_venue + wr_diff_l5 + nrr_diff_l5
from sklearn.preprocessing import StandardScaler

feats = m2[["score_vs_venue", "wr_diff_l5", "nrr_diff_l5", "wr_diff_c"]].fillna(0)
scaler = StandardScaler()
X = scaler.fit_transform(feats)
y = m2["team1_won"].values

# Multiple regression correlation
from numpy.linalg import lstsq
coef, _, _, _ = lstsq(np.c_[X, np.ones(len(X))], y, rcond=None)
y_hat = np.c_[X, np.ones(len(X))] @ coef
y_hat_clipped = np.clip(y_hat, 0.01, 0.99)
brier_combined = brier_score_loss(y, y_hat_clipped)
corr_combined = np.corrcoef(y_hat, y)[0, 1]

print(f"\n  Linear combo of [score_vs_venue, wr_l5, nrr_l5, wr_cumul]:")
print(f"  r = {corr_combined:.4f}  |  Brier = {brier_combined:.4f}")
print(f"\n  Coefficients: score_vs_venue={coef[0]:.4f}, wr_diff_l5={coef[1]:.4f}, "
      f"nrr_diff_l5={coef[2]:.4f}, wr_diff_cumul={coef[3]:.4f}")

# What improves the model's existing features?
# The model already has team win_rate (≈wr_cumul). 
# The INCREMENTAL gain is from: score_vs_venue (inn1 context) + nrr_diff_l5 (form)
print("\n  ── Incremental value over baseline (cumulative WR) ──")
for name, extra_feat in [
    ("+ score_vs_venue", "score_vs_venue"),
    ("+ nrr_diff_l5", "nrr_diff_l5"),
    ("+ wr_diff_l5", "wr_diff_l5"),
]:
    base = m2[["wr_diff_c", extra_feat]].fillna(0).values
    base = scaler.fit_transform(base)
    c, _, _, _ = lstsq(np.c_[base, np.ones(len(base))], y, rcond=None)
    yh = np.c_[base, np.ones(len(base))] @ c
    r = np.corrcoef(yh, y)[0, 1]
    print(f"  {name:<25} r = {r:.4f}")


# ── 7. TEAM-SPECIFIC DEFENDABILITY ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("7. TEAM DEFENDABILITY RATING — which teams defend best?")
print("=" * 60)

# For games where team1 scored above venue par, what's their win rate?
above_par = m[m["score_vs_venue"] > 0]
defend_above = (
    above_par.groupby("team1")["team1_won"]
    .agg(n="count", win_rate="mean")
    .reset_index()
    .query("n >= 10")
    .sort_values("win_rate", ascending=False)
)
print("\n Teams that best defend above-par scores (n>=10 above-par games):")
print(defend_above.to_string(index=False))

# For games where team1 scored below venue par
below_par = m[m["score_vs_venue"] < 0]
defend_below = (
    below_par.groupby("team1")["team1_won"]
    .agg(n="count", win_rate="mean")
    .reset_index()
    .query("n >= 10")
    .sort_values("win_rate", ascending=False)
)
print("\n Teams that best defend below-par scores (n>=10 below-par games):")
print(defend_below.to_string(index=False))


print("\n" + "=" * 60)
print("SUMMARY: Feature candidates for v9")
print("=" * 60)
print("""
Based on this EDA, the most actionable features to add:

1. score_vs_venue_par  (score minus venue avg for that over count)
   → r=0.XX at match level but HUGE within-game signal (already partially captured by score_vs_par)
   → Key insight: TEAM-SPECIFIC venue avg may add signal over generic venue avg

2. batting_team_nrr_l5  (batting team's rolling NRR last 5 matches)
   → Encodes recent momentum / form quality beyond just win/loss
   → Can be derived from existing processor form data

3. bat_first_wr (already in model) — but team+venue specific version adds ~+0.017 venue lift
   → Low score games: batting team WR less predictive (toss luck, pitch variability)
   → High score (>180): batting team WR much more predictive (execution dependent)

4. Inn1 wickets as proxy for bowling team quality
   → Wickets remaining for team batting second (already in features)
   
Action: Add batting_team_nrr_l5 (from form data) + possibly team-venue WR as two new features.
""")
