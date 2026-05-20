import pandas as pd
import numpy as np
import joblib, sys
sys.path.insert(0, 'src')
from scipy.special import expit
from scipy.optimize import minimize_scalar
from sklearn.metrics import brier_score_loss, log_loss

df = pd.read_parquet('data/ipl_features_v7/training.parquet')
m7 = joblib.load('models/ipl_v7/champion_model.joblib')
cal7 = joblib.load('models/ipl_v7/isotonic_calibrator.pkl')

# Holdout: 2025 + 2026 (most recent, unseen during training calibration)
holdout = df[df['season'].isin(['2025', '2026'])].copy()
print(f"Holdout: {len(holdout)} rows, seasons={sorted(holdout['season'].unique())}, matches={holdout['match_id'].nunique()}")

feats = [f for f in m7.selected_features_ if f in holdout.columns]
X = holdout[feats].fillna(0)
y = holdout['is_winner'].values
inn = holdout['innings'].values
over = holdout['over'].values

raw = m7.predict_proba(X)[:, 1]

# Apply per-over calibrators
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

def apply_temp(p, T):
    logits = np.log(p / (1 - p + 1e-9))
    return np.clip(expit(logits / T), 0.01, 0.99)

def brier_at_T(T):
    return brier_score_loss(y, apply_temp(cal_p, T))

# Fine-grained grid search
Ts = np.arange(0.50, 1.51, 0.01)
briers = [brier_at_T(T) for T in Ts]
best_idx = np.argmin(briers)
best_T = Ts[best_idx]
best_brier = briers[best_idx]

# Precise optimum via scipy
res = minimize_scalar(brier_at_T, bounds=(0.4, 1.5), method='bounded')
opt_T = res.x
opt_brier = res.fun

print(f"\n=== OPTIMAL TEMPERATURE (2025/2026 holdout) ===")
print(f"  Grid search best T : {best_T:.2f}  Brier={best_brier:.4f}")
print(f"  Scipy optimum T    : {opt_T:.3f}  Brier={opt_brier:.4f}")
print(f"  T=1.00 (current)   : Brier={brier_at_T(1.0):.4f}")
print(f"  Improvement        : {(brier_at_T(1.0)-opt_brier)*100/brier_at_T(1.0):.2f}%")

# Show table around optimum
print(f"\n=== BRIER vs T (holdout 2025/2026) ===")
print(f"  {'T':>6}  {'Brier':>8}  {'LogLoss':>8}  {'Std(p)':>8}  {'%>70':>7}  {'%<30':>7}")
for T in [0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95, 1.00, 1.10, 1.20]:
    p_s = apply_temp(cal_p, T)
    b = brier_score_loss(y, p_s)
    ll = log_loss(y, p_s)
    marker = ' <-- optimal' if abs(T - round(opt_T, 2)) < 0.01 else (' <-- current' if T == 1.00 else '')
    print(f"  {T:.2f}  {b:.4f}  {ll:.4f}  {p_s.std():.4f}  {(p_s>0.7).mean()*100:.1f}%  {(p_s<0.3).mean()*100:.1f}%{marker}")

# Segment breakdown at optimal T
print(f"\n=== SEGMENT BREAKDOWN at T={opt_T:.2f} vs T=1.00 ===")
print(f"  {'Segment':20s}  {'T=1.0':>8}  {'T={:.2f}'.format(opt_T):>8}  {'Delta':>8}  {'n':>7}")
p_opt = apply_temp(cal_p, opt_T)

segments = {
    'Overall':      np.ones(len(y), dtype=bool),
    'Inn1':         inn == 1,
    'Inn2':         inn == 2,
    'Inn1 PP':      (inn==1) & (over <= 5),
    'Inn1 Mid':     (inn==1) & (over > 5) & (over <= 14),
    'Inn1 Death':   (inn==1) & (over > 14),
    'Inn2 PP':      (inn==2) & (over <= 5),
    'Inn2 Mid':     (inn==2) & (over > 5) & (over <= 14),
    'Inn2 Death':   (inn==2) & (over > 14),
}
for seg, mask in segments.items():
    if mask.sum() < 50:
        continue
    b_base = brier_score_loss(y[mask], cal_p[mask])
    b_opt  = brier_score_loss(y[mask], p_opt[mask])
    delta  = b_opt - b_base
    marker = ' ✅' if delta < 0 else ' ❌'
    print(f"  {seg:20s}  {b_base:.4f}  {b_opt:.4f}  {delta:+.4f}{marker}  n={mask.sum()}")
