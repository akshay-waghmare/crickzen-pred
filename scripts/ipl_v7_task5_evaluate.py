"""Task 5: Evaluate v7 vs v6 vs Market"""
import pickle, numpy as np, pandas as pd
from sklearn.metrics import brier_score_loss, log_loss

mkt = pd.read_parquet('data/ipl_latest_market_vs_model.parquet')
matches = mkt.groupby('cs_match_id')['date'].first().sort_values()
train_matches = matches.index[:-10]
test_matches = matches.index[-10:]

# Load inn2 recalibrator
with open('models/ipl_v7/inn2_isotonic_calibrator.pkl', 'rb') as f:
    cal_data = pickle.load(f)
ir = cal_data['calibrator']

# Inn2 evaluation
inn2_test = mkt[(mkt['innings'] == 2) & (mkt['cs_match_id'].isin(test_matches))]
y_test = inn2_test['actual_inn1_wins'].values
p_v6 = np.clip(inn2_test['iso_p_inn1'].values, 1e-7, 1-1e-7)
p_v7 = np.clip(ir.predict(inn2_test['raw_p_inn1'].values), 1e-7, 1-1e-7)
p_mkt = np.clip(inn2_test['market_p_inn1'].values, 1e-7, 1-1e-7)

print('=== INN2 EVALUATION (holdout last 10 matches) ===')
print(f'n={len(inn2_test)} rows')
print(f'V6: Brier={brier_score_loss(y_test, p_v6):.4f}, LL={log_loss(y_test, p_v6):.4f}')
print(f'V7: Brier={brier_score_loss(y_test, p_v7):.4f}, LL={log_loss(y_test, p_v7):.4f}')
print(f'Mkt: Brier={brier_score_loss(y_test, p_mkt):.4f}, LL={log_loss(y_test, p_mkt):.4f}')

# Inn1 evaluation
inn1_test = mkt[(mkt['innings'] == 1) & (mkt['cs_match_id'].isin(test_matches))]
y_inn1 = inn1_test['actual_inn1_wins'].values
p_v6_inn1 = np.clip(inn1_test['iso_p_inn1'].values, 1e-7, 1-1e-7)
p_mkt_inn1 = np.clip(inn1_test['market_p_inn1'].values, 1e-7, 1-1e-7)
print('\n=== INN1 EVALUATION (holdout) ===')
print(f'n={len(inn1_test)} rows')
print(f'V6: Brier={brier_score_loss(y_inn1, p_v6_inn1):.4f}')
print(f'Mkt: Brier={brier_score_loss(y_inn1, p_mkt_inn1):.4f}')
unique_inn1 = np.unique(y_inn1)
if len(unique_inn1) > 1:
    print(f'V6: LL={log_loss(y_inn1, p_v6_inn1):.4f}')
    print(f'Mkt: LL={log_loss(y_inn1, p_mkt_inn1):.4f}')
else:
    print(f'Inn1 LL: skipped (only one class in test set: {unique_inn1})')

# Calibration curve v7 by bucket
print('\n=== V7 INN2 CALIBRATION CURVE (all data) ===')
inn2_all = mkt[mkt['innings'] == 2].copy()
inn2_all['p_v7'] = np.clip(ir.predict(inn2_all['raw_p_inn1'].values), 0, 1)
inn2_all['bucket'] = pd.cut(inn2_all['p_v7'], bins=[0,.1,.2,.3,.4,.5,.6,.7,.8,.9,1.0])
calib = inn2_all.groupby('bucket', observed=True).agg(
    n=('actual_inn1_wins','count'),
    model_mean=('p_v7','mean'),
    actual_mean=('actual_inn1_wins','mean')
)
calib['bias'] = calib['model_mean'] - calib['actual_mean']
print(calib.to_string())

# Also show v6 calibration for comparison
print('\n=== V6 INN2 CALIBRATION CURVE (all data, for comparison) ===')
inn2_all['bucket_v6'] = pd.cut(inn2_all['iso_p_inn1'], bins=[0,.1,.2,.3,.4,.5,.6,.7,.8,.9,1.0])
calib_v6 = inn2_all.groupby('bucket_v6', observed=True).agg(
    n=('actual_inn1_wins','count'),
    model_mean=('iso_p_inn1','mean'),
    actual_mean=('actual_inn1_wins','mean')
)
calib_v6['bias'] = calib_v6['model_mean'] - calib_v6['actual_mean']
print(calib_v6.to_string())
