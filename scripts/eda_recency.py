"""EDA: Recency signals (ELO, NRR, rolling win rate) correlation with IPL match outcomes."""
import pandas as pd
import numpy as np
import warnings
from sklearn.metrics import brier_score_loss

warnings.filterwarnings("ignore")

raw = pd.read_parquet("data/ipl_raw/matches")
inn1 = (
    raw[raw["innings"] == 1]
    .groupby("match_id")
    .agg(date=("date", "first"), season=("season", "first"),
         team1=("batting_team", "first"), winner=("winner", "first"),
         inn1_runs=("runs_total", "sum"), inn1_overs=("over", "max"))
    .reset_index()
)
inn2 = (
    raw[raw["innings"] == 2]
    .groupby("match_id")
    .agg(team2=("batting_team", "first"), inn2_runs=("runs_total", "sum"),
         inn2_overs=("over", "max"))
    .reset_index()
)
matches = inn1.merge(inn2, on="match_id").sort_values("date").reset_index(drop=True)
matches["date"] = pd.to_datetime(matches["date"])
matches["team1_nrr"] = (
    matches["inn1_runs"] / (matches["inn1_overs"] + 1)
    - matches["inn2_runs"] / (matches["inn2_overs"] + 1)
)
matches["t1_won"] = (matches["winner"] == matches["team1"]).astype(float)

# ELO ratings (NRR-adjusted K)
elo = {}
ecols = []
for _, r in matches.iterrows():
    e1 = elo.get(r.team1, 1500)
    e2 = elo.get(r.team2, 1500)
    p1 = 1 / (1 + 10 ** ((e2 - e1) / 400))
    k = 32 * (1 + min(abs(r.team1_nrr), 3) / 3)
    s1 = float(r.winner == r.team1)
    ecols.append({"match_id": r.match_id, "p1_elo": p1})
    elo[r.team1] = e1 + k * (s1 - p1)
    elo[r.team2] = e2 + k * ((1 - s1) - (1 - p1))

matches = matches.merge(pd.DataFrame(ecols), on="match_id")
print(f"ELO standalone Brier: {brier_score_loss(matches.t1_won, matches.p1_elo):.4f}")

# Rolling form (per team, leakage-free shift)
rows = []
for tc, ns in [("team1", 1), ("team2", -1)]:
    s = matches[["match_id", "date", "season", tc, "winner", "team1_nrr"]].copy()
    s.columns = ["match_id", "date", "season", "team", "winner", "nrr"]
    s["nrr"] *= ns
    s["won"] = (s["team"] == s["winner"]).astype(int)
    rows.append(s)

tm = pd.concat(rows).sort_values(["team", "date"]).reset_index(drop=True)
for N in [3, 5, 10]:
    tm[f"wrl{N}"] = tm.groupby("team")["won"].transform(
        lambda x: x.shift(1).rolling(N, min_periods=1).mean()
    )
    tm[f"nrrl{N}"] = tm.groupby("team")["nrr"].transform(
        lambda x: x.shift(1).rolling(N, min_periods=1).mean()
    )
tm["wr_c"] = tm.groupby("team")["won"].transform(
    lambda x: x.shift(1).expanding().mean()
)
tm["nrr_c"] = tm.groupby("team")["nrr"].transform(
    lambda x: x.shift(1).expanding().mean()
)

# Merge form to match-level (team1 = batting, team2 = bowling)
bat_cols = ["match_id", "team1", "wrl3", "wrl5", "wrl10", "nrrl3", "nrrl5", "nrrl10", "wr_c", "nrr_c"]
bowl_rename = {c: c + "2" for c in ["wrl3", "wrl5", "wrl10", "nrrl3", "nrrl5", "nrrl10", "wr_c", "nrr_c"]}

t1f = tm.rename(columns={"team": "team1"})[bat_cols]
t2f = (
    tm.rename(columns={"team": "team2"})[
        ["match_id", "team2", "wrl3", "wrl5", "wrl10", "nrrl3", "nrrl5", "nrrl10", "wr_c", "nrr_c"]
    ].rename(columns=bowl_rename)
)

m = (
    matches.merge(t1f, on=["match_id", "team1"])
    .merge(t2f, on=["match_id", "team2"])
)
m = m[~m["winner"].isna()].copy()

# Diff features
for sfx, ac, bc in [
    ("l3", "wrl3", "wrl32"), ("l5", "wrl5", "wrl52"), ("l10", "wrl10", "wrl102"),
    ("c", "wr_c", "wr_c2"),
]:
    m[f"wr_diff_{sfx}"] = m[ac] - m[bc]

for sfx, ac, bc in [
    ("l3", "nrrl3", "nrrl32"), ("l5", "nrrl5", "nrrl52"), ("l10", "nrrl10", "nrrl102"),
    ("c", "nrr_c", "nrr_c2"),
]:
    m[f"nrr_diff_{sfx}"] = m[ac] - m[bc]

# ============================================================
print(f"\nMatches with form data: {len(m)}")
print(f"\n{'Signal':<28} {'r':>8}")
print("-" * 40)

for name, col in [
    ("ELO probability", "p1_elo"),
    ("WR diff (cumulative)", "wr_diff_c"),
    ("WR diff (last 10)", "wr_diff_l10"),
    ("WR diff (last 5)", "wr_diff_l5"),
    ("WR diff (last 3)", "wr_diff_l3"),
    ("NRR diff (cumulative)", "nrr_diff_c"),
    ("NRR diff (last 5)", "nrr_diff_l5"),
    ("NRR diff (last 3)", "nrr_diff_l3"),
]:
    r = m[[col, "t1_won"]].dropna().corr().iloc[0, 1]
    print(f"  {name:<28} {r:>8.4f}")

# By season
print(f"\n{'Season':>8}  {'n':>4}  {'WR_l5':>8}  {'NRR_l5':>8}  {'ELO':>8}")
print("-" * 50)
for seas in ["2018", "2019", "2020/21", "2021", "2022", "2023", "2024", "2025"]:
    sub = m[m["season"] == seas]
    if len(sub) < 10:
        continue
    r_wr = sub[["wr_diff_l5", "t1_won"]].dropna().corr().iloc[0, 1]
    r_nrr = sub[["nrr_diff_l5", "t1_won"]].dropna().corr().iloc[0, 1]
    r_elo = sub[["p1_elo", "t1_won"]].dropna().corr().iloc[0, 1]
    print(f"  {seas:>8}  {len(sub):>4}  {r_wr:>8.3f}  {r_nrr:>8.3f}  {r_elo:>8.3f}")

# Best recent (2022+)
rec = m[m["season"].isin(["2022", "2023", "2024", "2025"])]
print(f"\n=== Recent seasons 2022+ (n={len(rec)}) ===")
for name, col in [
    ("WR diff (last 5)", "wr_diff_l5"),
    ("NRR diff (last 5)", "nrr_diff_l5"),
    ("ELO", "p1_elo"),
    ("WR diff (cumul)", "wr_diff_c"),
]:
    r = rec[[col, "t1_won"]].dropna().corr().iloc[0, 1]
    print(f"  {name:<25}: r={r:.4f}")

# Save for v9 planning
m[["match_id","season","team1","team2","t1_won","p1_elo",
   "wr_diff_l3","wr_diff_l5","wr_diff_l10","wr_diff_c",
   "nrr_diff_l3","nrr_diff_l5","nrr_diff_l10","nrr_diff_c",
   "wrl3","wrl5","wrl10","wr_c","nrrl3","nrrl5","nrrl10","nrr_c"]
].to_parquet("data/_eda_match_form.parquet", index=False)
print("\nSaved data/_eda_match_form.parquet")
