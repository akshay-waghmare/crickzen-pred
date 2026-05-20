import pandas as pd
import numpy as np
import joblib, sys
sys.path.insert(0, 'src')
from scipy.special import expit
from sklearn.metrics import brier_score_loss, log_loss

df = pd.read_parquet('data/ipl_features_v7/training.parquet')
m7 = joblib.load('models/ipl_v7/champion_model.joblib')
cal7 = joblib.load('models/ipl_v7/isotonic_calibrator.pkl')

feats = [f for f in m7.selected_features_ if f in df.columns]
X = df[feats].fillna(0)
y = df['is_winner'].values
raw = m7.predict_proba(X)[:, 1]

inn = df['innings'].values
over = df['over'].values
# Use per-over calibrators (brier_optimized method) — same as production
per_over = cal7.get('per_over_calibrators', {})
cal_p = np.zeros_like(raw)
for i in range(len(raw)):
    key = f"inn{int(inn[i])}_over{int(over[i])}"
    if key in per_over:
        cal_p[i] = per_over[key].predict([raw[i]])[0]
    elif int(inn[i]) == 1:
        cal_p[i] = cal7['calibrator_innings1'].predict([raw[i]])[0]
    else:
        cal_p[i] = cal7['calibrator_innings2'].predict([raw[i]])[0]

print("=== PREDICTION DISTRIBUTION (calibrated, v7) ===")
bins = [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.01]
labels = ['0-10', '10-20', '20-30', '30-40', '40-50', '50-60', '60-70', '70-80', '80-90', '90-100']
for i, lbl in enumerate(labels):
    mask = (cal_p >= bins[i]) & (cal_p < bins[i+1])
    print(f"  {lbl}%: {mask.sum():6d} ({100*mask.sum()/len(cal_p):.1f}%)")

print(f"\n  Min={cal_p.min():.3f}  Max={cal_p.max():.3f}  Std={cal_p.std():.3f}")
print(f"  40-60% band : {((cal_p > 0.4) & (cal_p < 0.6)).mean()*100:.1f}%")
print(f"  outside 30-70%: {((cal_p < 0.3) | (cal_p > 0.7)).mean()*100:.1f}%")

print("\n=== TEMPERATURE SHARPENING EFFECT ===")
print(f"  {'T':>5}  {'Brier':>8}  {'LogLoss':>8}  {'Std(p)':>8}  {'%>70':>7}  {'%<30':>7}")
for T in [1.0, 0.95, 0.90, 0.85, 0.80, 0.75, 0.70]:
    logits = np.log(cal_p / (1 - cal_p + 1e-9))
    p_s = np.clip(expit(logits / T), 0.01, 0.99)
    b = brier_score_loss(y, p_s)
    ll = log_loss(y, p_s)
    hi = (p_s > 0.7).mean() * 100
    lo = (p_s < 0.3).mean() * 100
    marker = ' <-- current' if T == 1.0 else ''
    print(f"  {T:.2f}  {b:.4f}  {ll:.4f}  {p_s.std():.4f}  {hi:.1f}%  {lo:.1f}%{marker}")
