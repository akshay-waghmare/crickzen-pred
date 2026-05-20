"""
OOS Chase Analysis — Inn2 Phase × Chase-Type
Shows model predicted win prob vs actual win rate for the batting team.
"""
import pandas as pd
import numpy as np

df = pd.read_parquet("data/match_states/ipl/cricket-live-score.parquet")
inn2 = df[df["innings"] == 2].copy()
inn2["date"] = pd.to_datetime(inn2["timestamp"]).dt.date

# ── 1. Determine winner per match ─────────────────────────────────────────────
final = inn2.sort_values("timestamp").groupby("date").last().reset_index()
final["batting_won"] = (final["total_runs"] >= final["target"]).astype(int)
winner_map = final.set_index("date")["batting_won"].to_dict()

print("=" * 72)
print("MATCH OUTCOMES (batting team perspective)")
print("=" * 72)
for _, row in final.sort_values("date").iterrows():
    status = "WON" if row["batting_won"] else "LOST"
    tag = "HIGH" if (row["target"] - row["venue_avg_score"]) > 20 else \
          "LOW"  if (row["target"] - row["venue_avg_score"]) < -20 else "PAR"
    print(f"  {row['date']}  {row['batting_team'][:22]:<22}  "
          f"target={int(row['target'])}  venue_avg={int(row['venue_avg_score'])}  "
          f"[{tag}]  {status}")

inn2["batting_won"] = inn2["date"].map(winner_map)

# ── 2. Chase classification: HIGH / PAR / LOW ─────────────────────────────────
# target_above_par = target − venue_avg_score at start of inn2
inn2["target_above_par"] = inn2["target"] - inn2["venue_avg_score"]
inn2["chase_type"] = pd.cut(
    inn2["target_above_par"],
    bins=[-999, -20, 20, 999],
    labels=["LOW", "PAR", "HIGH"]
)

# ── 3. Phase label ─────────────────────────────────────────────────────────────
inn2["phase"] = inn2["match_phase"].str.upper()  # POWERPLAY / MIDDLE / DEATH

# ── 4. Model prob column — use final calibrated prob ─────────────────────────
prob_col = "model_final_prob"
inn2 = inn2.dropna(subset=[prob_col, "batting_won"])

# ── 5. Analysis ──────────────────────────────────────────────────────────────
phase_order  = ["POWERPLAY", "MIDDLE", "DEATH"]
chase_order  = ["LOW", "PAR", "HIGH"]

print("\n" + "=" * 72)
print("OOS ANALYSIS: Model Pred vs Actual Win Rate  (Inn2, Batting Team)")
print("=" * 72)

rows = []
for chase in chase_order:
    for phase in phase_order:
        seg = inn2[(inn2["chase_type"] == chase) & (inn2["phase"] == phase)]
        if len(seg) < 5:
            continue
        n_balls   = len(seg)
        n_matches = seg["date"].nunique()
        pred_mean = seg[prob_col].mean()
        act_mean  = seg["batting_won"].mean()
        gap       = pred_mean - act_mean
        rows.append({
            "Chase": chase, "Phase": phase,
            "Matches": n_matches, "Balls": n_balls,
            "Model%": round(pred_mean * 100, 1),
            "Actual%": round(act_mean * 100, 1),
            "Gap(pp)": round(gap * 100, 1)
        })

result = pd.DataFrame(rows)
print(result.to_string(index=False))

# ── 6. Chase-type summary (all phases) ────────────────────────────────────────
print("\n" + "=" * 72)
print("CHASE-TYPE SUMMARY (all phases combined)")
print("=" * 72)
rows2 = []
for chase in chase_order:
    seg = inn2[inn2["chase_type"] == chase]
    if len(seg) < 5:
        continue
    n_matches = seg["date"].nunique()
    pred_mean = seg[prob_col].mean()
    act_mean  = seg["batting_won"].mean()
    gap       = pred_mean - act_mean
    rows2.append({
        "Chase": chase, "Matches": n_matches, "Balls": len(seg),
        "Model%": round(pred_mean * 100, 1),
        "Actual%": round(act_mean * 100, 1),
        "Gap(pp)": round(gap * 100, 1)
    })
print(pd.DataFrame(rows2).to_string(index=False))

# ── 7. Per-match summary ──────────────────────────────────────────────────────
print("\n" + "=" * 72)
print("PER-MATCH: Avg Model Prob vs Outcome")
print("=" * 72)
pm = (inn2.groupby("date").agg(
    batting_team=("batting_team", "first"),
    target=("target", "first"),
    chase_type=("chase_type", "first"),
    model_avg=(prob_col, "mean"),
    batting_won=("batting_won", "first")
).reset_index().sort_values("date"))
pm["model_avg%"] = (pm["model_avg"] * 100).round(1)
pm["result"] = pm["batting_won"].map({1: "WON", 0: "LOST"})
print(pm[["date","batting_team","target","chase_type","model_avg%","result"]].to_string(index=False))
