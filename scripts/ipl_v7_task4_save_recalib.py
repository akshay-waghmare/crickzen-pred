"""Task 4: Fit and save inn2 isotonic calibrator for IPL v7"""
import pickle, numpy as np, pandas as pd
from sklearn.isotonic import IsotonicRegression
import os

mkt = pd.read_parquet('data/ipl_latest_market_vs_model.parquet')
inn2 = mkt[mkt['innings'] == 2].copy()
matches = mkt.groupby('cs_match_id')['date'].first().sort_values()
train_matches = matches.index[:-10]
train = inn2[inn2['cs_match_id'].isin(train_matches)]

ir = IsotonicRegression(out_of_bounds='clip')
ir.fit(train['raw_p_inn1'], train['actual_inn1_wins'])

os.makedirs('models/ipl_v7', exist_ok=True)
with open('models/ipl_v7/inn2_isotonic_calibrator.pkl', 'wb') as f:
    pickle.dump({
        'calibrator': ir,
        'metadata': {
            'type': 'inn2_isotonic',
            'n_train': len(train),
            'created': '2026-04-22',
            'description': 'Fits isotonic regression on raw_p_inn1 for inn2 rows to correct S-curve flattening',
            'train_matches': len(train_matches),
        }
    }, f)
print(f'Saved inn2 isotonic calibrator (trained on {len(train)} inn2 rows, {len(train_matches)} matches)')
print('Path: models/ipl_v7/inn2_isotonic_calibrator.pkl')
