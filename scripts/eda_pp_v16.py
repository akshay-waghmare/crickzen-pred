"""EDA for IPL inn2 PP v16 feature analysis."""
import pandas as pd
import numpy as np
import sys
sys.path.insert(0, "src")
from sklearn.metrics import brier_score_loss

df = pd.read_parquet("data/ipl_features_v10/training.parquet")
pp2 = df[(df["innings"] == 2) & (df["is_powerplay"] == 1)].copy()
pp2["cat_label"] = pp2["chase_category"].map({-1: "below_par", 0: "on_par", 1: "above_par"})

print("=== Win rate & wicket stats by chase_category ===")
for cat, g in pp2.groupby("cat_label"):
    wr = g["is_winner"].mean()
    wk = g["wickets_lost"].mean()
    rrr = g["required_run_rate"].mean()
    print(f"  {cat:<12}: n={len(g):>6}  win_rate={wr:.3f}  avg_wkts={wk:.2f}  avg_rrr={rrr:.2f}")

print()
new_cands = [
    "balls_since_wicket", "set_batter_exposure", "chase_difficulty",
    "acceleration_potential", "boundary_pct_last_18", "runs_last_12",
    "wickets_last_12", "dot_pct_last_12", "recovery_momentum",
    "momentum_acceleration", "score_per_wicket", "batting_recent_nrr_l5",
    "wickets_times_balls", "wickets_last_30",
]
print("=== Correlations of NEW candidate features by chase_category ===")
for cat, g in pp2.groupby("cat_label"):
    print(f"  {cat}:")
    corrs = {}
    for c in new_cands:
        if c in g.columns:
            v = abs(g[c].fillna(0).corr(g["is_winner"]))
            if not np.isnan(v):
                corrs[c] = v
    for f, v in sorted(corrs.items(), key=lambda x: -x[1])[:8]:
        print(f"    {f:<35} {v:.4f}")

print()
print("=== Brier by over (resource_win_prob proxy) ===")
for ov in range(6):
    g = pp2[pp2["over"] == ov]
    rwp = g["resource_win_prob"].clip(1e-6, 1 - 1e-6).fillna(0.5)
    b = brier_score_loss(g["is_winner"], rwp)
    print(f"  Over {ov}: n={len(g):>4}  brier_rwp={b:.4f}  win_rate={g['is_winner'].mean():.3f}")

print()
print("=== Brier by over × chase_category ===")
for cat, grp in pp2.groupby("cat_label"):
    print(f"  {cat}:")
    for ov in range(6):
        g = grp[grp["over"] == ov]
        if len(g) < 20:
            continue
        rwp = g["resource_win_prob"].clip(1e-6, 1 - 1e-6).fillna(0.5)
        b = brier_score_loss(g["is_winner"], rwp)
        print(f"    over {ov}: n={len(g):>4}  brier={b:.4f}  win_rate={g['is_winner'].mean():.3f}")

print()
print("=== Inn1 feature correlations with is_winner in PP ===")
inn1_feats = ["inn1_pp_runs", "inn1_wickets_lost", "inn1_death_rr",
              "inn1_quality_index", "inn1_defendability"]
for f in inn1_feats:
    if f in pp2.columns:
        v = abs(pp2[f].fillna(0).corr(pp2["is_winner"]))
        print(f"  {f:<35} {v:.4f}")

print()
print("=== Sample stats for new high-signal features ===")
for f in ["balls_since_wicket", "set_batter_exposure", "chase_difficulty",
          "dot_pct_last_12", "recovery_momentum", "momentum_acceleration",
          "score_per_wicket"]:
    if f in pp2.columns:
        s = pp2[f].describe()
        print(f"  {f}: mean={s['mean']:.3f}  std={s['std']:.3f}  min={s['min']:.3f}  max={s['max']:.3f}")
