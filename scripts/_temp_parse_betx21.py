import pandas as pd, numpy as np, gzip, json, os
from pathlib import Path

# ── 1. Get 2026 Cricsheet match info ──────────────────────────────────────────
raw = pd.read_parquet('data/ipl_raw/matches')
raw2026 = raw[raw['season'] == '2026']
matches_cs = (raw2026.sort_values(['match_id','innings','over','ball'])
              .groupby('match_id').first().reset_index()
              [['match_id','date','batting_team','bowling_team','winner']])
matches_cs['date_str'] = pd.to_datetime(matches_cs['date']).dt.strftime('%Y-%m-%d')
print(f"Cricsheet 2026 matches: {len(matches_cs)}")
print(matches_cs[['match_id','date_str','batting_team','bowling_team']].sort_values('date_str').to_string())

# ── 2. Parse betx21 score files → match info ──────────────────────────────────
betx21_dir = Path('C:/Users/ADMINS/Documents/projects/betx21.live/ipl_matches_download')
match_info = {}
for scores_file in sorted(betx21_dir.rglob('*_scores.jsonl.gz')):
    ev_id = scores_file.name.split('_')[0]
    folder_date = scores_file.parent.name  # e.g. 2026-04-03
    records = []
    with gzip.open(scores_file, 'rt') as f:
        for line in f:
            try: records.append(json.loads(line))
            except: pass
    if not records: continue

    t1 = records[0].get('t1', '')
    t2 = records[0].get('t2', '')
    # Get final state (last record with both scores)
    final = None
    for r in reversed(records):
        if r.get('s1') and r.get('s2') and '(' in r.get('s1','') and '(' in r.get('s2',''):
            final = r
            break
    if not final: continue

    match_info[ev_id] = {
        'ev_id': ev_id,
        'date_str': folder_date,
        't1': t1, 't2': t2,
        'final_s1': final.get('s1',''),
        'final_s2': final.get('s2',''),
        'winner': final.get('st',''),
    }

betx21_df = pd.DataFrame(list(match_info.values()))
print(f"\nbetx21 matches parsed: {len(betx21_df)}")
print(betx21_df[['ev_id','date_str','t1','t2','final_s1','final_s2']].to_string())
