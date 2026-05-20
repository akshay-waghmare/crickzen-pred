import pandas as pd

files = [
    'data/ipl_model_vs_market_v3.parquet',
    'data/ipl_market_vs_model_corrected_2026.parquet',
    'data/ipl_market_vs_model_full_2026.parquet',
    'data/match_states/ipl/cricket-live-score.parquet',
]
for f in files:
    try:
        df = pd.read_parquet(f)
        print(f'--- {f} ---')
        print(f'  shape: {df.shape}')
        print(f'  cols: {list(df.columns[:25])}')
        for col in ['season', 'date', 'match_id']:
            if col in df.columns:
                print(f'  {col}: {sorted(df[col].unique())[-5:]}')
        print()
    except Exception as e:
        print(f'{f}: ERROR {e}')
