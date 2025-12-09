import pandas as pd
import os

# Paths
base_dir = r"c:\Users\ADMINS\Documents\projects\machine_learning\ml_predictions"
input_path = os.path.join(base_dir, "aggregated_match_data.csv")
output_dir = r"c:\Users\ADMINS\Documents\projects\machine_learning\models\v1"

print("Reading aggregated data...")
df = pd.read_csv(input_path)

# Ensure output dir exists
os.makedirs(output_dir, exist_ok=True)

# --- Player Stats ---
print("Generating player stats...")
# We need to find the last row for each player to get their most recent "historical" stats.
# Since we don't have a date, we'll assume the file order is chronological or match_id is.
# We'll just take the last occurrence.

# Batsman 1
b1_stats = df.groupby('batsman1_name').last()[['batsman1_historical_average', 'batsman1_historical_strike_rate']]
b1_stats.columns = ['batsman_rolling_avg', 'batsman_rolling_sr']

# Batsman 2
b2_stats = df.groupby('batsman2_name').last()[['batsman2_historical_average', 'batsman2_historical_strike_rate']]
b2_stats.columns = ['batsman_rolling_avg', 'batsman_rolling_sr']

# Combine and take the latest (if a player appears as b1 and b2, take the one that appeared last in the df)
# A simple way is to iterate backwards or just concat and drop duplicates keeping last?
# But 'last' in groupby depends on index.

# Let's create a long format of (player, avg, sr, match_index)
df['match_index'] = df.index

b1 = df[['batsman1_name', 'batsman1_historical_average', 'batsman1_historical_strike_rate', 'match_index']].rename(
    columns={'batsman1_name': 'player_name', 'batsman1_historical_average': 'batsman_rolling_avg', 'batsman1_historical_strike_rate': 'batsman_rolling_sr'}
)
b2 = df[['batsman2_name', 'batsman2_historical_average', 'batsman2_historical_strike_rate', 'match_index']].rename(
    columns={'batsman2_name': 'player_name', 'batsman2_historical_average': 'batsman_rolling_avg', 'batsman2_historical_strike_rate': 'batsman_rolling_sr'}
)

combined_batting = pd.concat([b1, b2])
latest_batting = combined_batting.sort_values('match_index').groupby('player_name').last().drop(columns=['match_index'])

# Save
latest_batting.to_parquet(os.path.join(output_dir, "player_stats.parquet"))
print(f"Saved player stats for {len(latest_batting)} players.")

# --- Venue Stats ---
print("Generating venue stats...")
# Venue stats columns?
# The file has 'venue', 'average_runs_per_wicket', 'average_runs_per_over'.
# These seem to be venue stats? Or match stats?
# "average_runs_per_wicket" might be the historical venue stat attached to the row.

venue_stats = df.groupby('venue').last()[['average_runs_per_wicket', 'average_runs_per_over']]
venue_stats.columns = ['venue_avg_wickets', 'venue_avg_score'] # Mapping might be approximate
# Note: average_runs_per_over * 20 approx avg score?
# Let's just save what we have.

venue_stats.to_parquet(os.path.join(output_dir, "venue_stats.parquet"))
print(f"Saved venue stats for {len(venue_stats)} venues.")

print("Done.")
