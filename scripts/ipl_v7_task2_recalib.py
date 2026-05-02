"""Task 2: Inn2 Isotonic Recalibrator evaluation"""
import pickle, numpy as np, pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import brier_score_loss, log_loss

mkt = pd.read_parquet('data/ipl_latest_market_vs_model.parquet')
inn2 = mkt[mkt['innings'] == 2].copy()

# Chronological split
matches = mkt.groupby('cs_match_id')['date'].first().sort_values()
train_matches = matches.index[:-10]
test_matches = matches.index[-10:]

print(f'Train matches: {len(train_matches)}, Test matches: {len(test_matches)}')
train_inn2 = inn2[inn2['cs_match_id'].isin(train_matches)]
test_inn2 = inn2[inn2['cs_match_id'].isin(test_matches)]
print(f'Train inn2 rows: {len(train_inn2)}')
print(f'Test inn2 rows: {len(test_inn2)}')

train = train_inn2
test = test_inn2

# Fit isotonic on train
ir = IsotonicRegression(out_of_bounds='clip')
ir.fit(train['raw_p_inn1'], train['actual_inn1_wins'])

# Eval on test
y_test = test['actual_inn1_wins'].values
p_v6 = np.clip(test['iso_p_inn1'].values, 1e-7, 1-1e-7)
p_v7 = np.clip(ir.predict(test['raw_p_inn1'].values), 1e-7, 1-1e-7)
p_mkt = np.clip(test['market_p_inn1'].values, 1e-7, 1-1e-7)

print(f'V6: Brier={brier_score_loss(y_test, p_v6):.4f}, LL={log_loss(y_test, p_v6):.4f}')
print(f'V7: Brier={brier_score_loss(y_test, p_v7):.4f}, LL={log_loss(y_test, p_v7):.4f}')
print(f'Mkt: Brier={brier_score_loss(y_test, p_mkt):.4f}, LL={log_loss(y_test, p_mkt):.4f}')

# Also check inn1
inn1_test = mkt[(mkt['innings'] == 1) & (mkt['cs_match_id'].isin(test_matches))]
y_inn1 = inn1_test['actual_inn1_wins'].values
p_v6_inn1 = np.clip(inn1_test['iso_p_inn1'].values, 1e-7, 1-1e-7)
p_mkt_inn1 = np.clip(inn1_test['market_p_inn1'].values, 1e-7, 1-1e-7)
print(f'\nInn1 V6: Brier={brier_score_loss(y_inn1, p_v6_inn1):.4f}')
print(f'Inn1 Mkt: Brier={brier_score_loss(y_inn1, p_mkt_inn1):.4f}')
unique_labels = np.unique(y_inn1)
if len(unique_labels) > 1:
    print(f'Inn1 V6: LL={log_loss(y_inn1, p_v6_inn1):.4f}')
    print(f'Inn1 Mkt: LL={log_loss(y_inn1, p_mkt_inn1):.4f}')
else:
    print(f'Inn1 LL: skipped (only one class {unique_labels} in test set)')
