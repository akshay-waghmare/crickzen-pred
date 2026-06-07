import pandas as pd
import json

df = pd.read_parquet("data/ntb_raw/matches")
df = df[df["is_super_over"] == False].copy()
df["is_wicket"] = df["wicket_type"].notna() & (df["wicket_type"] != "")


def get_phase(over):
    if over <= 5:
        return "powerplay"
    elif over <= 14:
        return "middle"
    else:
        return "death"


df["phase"] = df["over"].apply(get_phase)

run_dist = {}
wicket_prob = {}
boundary_pct = {}

for phase in ["powerplay", "middle", "death"]:
    pdf = df[df["phase"] == phase]

    runs = pdf["runs_total"].value_counts(normalize=True).sort_index()
    dist = {}
    for r in range(8):
        dist[str(r)] = float(runs.get(r, 0.0))
    run_dist[phase] = dist

    wicket_prob[phase] = float(pdf["is_wicket"].mean())
    boundary_pct[phase] = float(pdf["runs_total"].isin([4, 6]).mean())

result = {
    "total_balls": int(len(df)),
    "run_dist": run_dist,
    "wicket_prob": wicket_prob,
    "boundary_pct": boundary_pct,
    "wicket_multiplier": {
        "powerplay": 1.0,
        "middle": 1.0,
        "death": 1.0,
    },
}

with open("data/phase_distributions_ntb.json", "w") as f:
    json.dump(result, f, indent=2)

pp_count = len(df[df["phase"] == "powerplay"])
mid_count = len(df[df["phase"] == "middle"])
death_count = len(df[df["phase"] == "death"])
print(f"Extracted distributions from {len(df):,} NTB balls")
print(f"Phases: PP={pp_count:,}, MID={mid_count:,}, DEATH={death_count:,}")
print(json.dumps(result, indent=2))
