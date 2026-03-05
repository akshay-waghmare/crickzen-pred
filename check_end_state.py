import pandas as pd

df = pd.read_parquet('data/match_states/t20i/ind-vs-sa-43rd-t20i--super-8-group-1st-match-t20-world-cup-2026.parquet')

print('Last 5 ball states from Innings 1:')
print(df[['over_number', 'ball_in_over', 'total_runs', 'wickets', 'batting_team', 'match_phase']].tail(5).to_string())

print('\n\nFinal Innings 1 state:')
last_row = df.iloc[-1]
print(f'  Batting team: {last_row["batting_team"]}')
print(f'  Total runs: {last_row["total_runs"]}')
print(f'  Wickets: {last_row["wickets"]}')
print(f'  Over: {last_row["over_number"]}.{last_row["ball_in_over"]}')
print(f'  Match phase: {last_row["match_phase"]}')
print(f'  Timestamp: {last_row["timestamp"]}')

# Check metadata
metadata = pd.read_parquet('data/match_states/t20i/match_metadata.parquet')
ind_sa = metadata[metadata['match_id'] == 'ind-vs-sa-43rd-t20i--super-8-group-1st-match-t20-world-cup-2026']
if len(ind_sa) > 0:
    print('\n\nRecording metadata:')
    print(f'  Result type: {ind_sa["result_type"].values[0]}')
    print(f'  Recording start: {ind_sa["recording_start"].values[0]}')
    print(f'  Recording end: {ind_sa["recording_end"].values[0]}')
    print(f'  Total balls recorded: {ind_sa["total_balls_recorded"].values[0]}')
