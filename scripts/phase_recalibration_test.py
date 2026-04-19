"""
Phase-specific recalibration to correct known model biases.

Known biases (model vs market):
  Inn1 middle: model 0.19 TOO HIGH
  Inn1 death:  model 0.20 TOO HIGH
  Inn2 death:  model 0.12 TOO LOW

Tests 3 methods with Leave-One-Match-Out CV:
  1. Temperature scaling per phase×innings
  2. Platt scaling per phase×innings
  3. Constant bias correction per phase×innings
"""
import sys, os, warnings
warnings.filterwarnings('ignore')
sys.path.insert(0, 'src')

import pandas as pd
import numpy as np
from scipy.special import logit, expit
from scipy.optimize import minimize_scalar, minimize
from sklearn.model_selection import LeaveOneGroupOut

mkt = pd.read_parquet('data/ipl_model_vs_market_v2.parquet')
model_p = mkt['ipl_v2_p_t1'].values
market_p = mkt['market_p_t1'].values
actual = mkt['actual_t1_wins'].values
phases = mkt['phase'].values
innings = mkt['innings'].values
groups = mkt['event_id'].values

def brier(p, y):
    return np.mean((p - y)**2)

print("=" * 70)
print("  Phase×Innings Recalibration (LOMO-CV)")
print("=" * 70)

# Define segments
segments = {}
for inn in [1, 2]:
    for ph in ['powerplay', 'middle', 'death']:
        mask = (innings == inn) & (phases == ph)
        if mask.sum() > 10:
            segments[f'inn{inn}_{ph}'] = mask

b_mkt_overall = brier(market_p, actual)
b_raw_overall = brier(model_p, actual)
gap_before = (b_raw_overall / b_mkt_overall - 1) * 100


# ── Method 1: Temperature Scaling ──
print("\n--- Method 1: Temperature Scaling per segment ---")
print("  logit(p_cal) = logit(p_model) / T")
print("  T > 1 = softer (toward 0.5), T < 1 = sharper\n")

cal_temp = np.copy(model_p)
for seg_name, mask in segments.items():
    logo = LeaveOneGroupOut()
    seg_groups = groups[mask]
    seg_model = model_p[mask]
    seg_actual = actual[mask]
    seg_cal = np.full(mask.sum(), np.nan)
    
    for tr, te in logo.split(seg_model.reshape(-1, 1), seg_actual, seg_groups):
        logits_tr = logit(np.clip(seg_model[tr], 0.01, 0.99))
        def obj(T):
            return brier(expit(logits_tr / T), seg_actual[tr])
        res = minimize_scalar(obj, bounds=(0.3, 5.0), method='bounded')
        logits_te = logit(np.clip(seg_model[te], 0.01, 0.99))
        seg_cal[te] = expit(logits_te / res.x)
    
    cal_temp[mask] = seg_cal
    
    # Full-segment T for reporting
    logits_all = logit(np.clip(seg_model, 0.01, 0.99))
    def obj_all(T):
        return brier(expit(logits_all / T), seg_actual)
    T_all = minimize_scalar(obj_all, bounds=(0.3, 5.0), method='bounded').x
    
    b_raw = brier(seg_model, seg_actual)
    b_cal = brier(seg_cal, seg_actual)
    b_m = brier(market_p[mask], seg_actual)
    delta = (b_cal - b_raw) / b_raw * 100
    print(f"  {seg_name:15s} T={T_all:.3f}  n={mask.sum():3d}  raw={b_raw:.4f}  cal={b_cal:.4f}  mkt={b_m:.4f}  ({delta:+.1f}%)")

b_temp = brier(cal_temp, actual)
gap_temp = (b_temp / b_mkt_overall - 1) * 100
print(f"\n  Overall: raw={b_raw_overall:.4f}  temp={b_temp:.4f}  mkt={b_mkt_overall:.4f}")
print(f"  Gap: {gap_before:+.1f}% -> {gap_temp:+.1f}%")


# ── Method 2: Platt Scaling ──
print("\n--- Method 2: Platt Scaling per segment ---")
print("  logit(p_cal) = a * logit(p_model) + b\n")

cal_platt = np.copy(model_p)
for seg_name, mask in segments.items():
    logo = LeaveOneGroupOut()
    seg_groups = groups[mask]
    seg_model = model_p[mask]
    seg_actual = actual[mask]
    seg_cal = np.full(mask.sum(), np.nan)
    
    for tr, te in logo.split(seg_model.reshape(-1, 1), seg_actual, seg_groups):
        logits_tr = logit(np.clip(seg_model[tr], 0.01, 0.99))
        logits_te = logit(np.clip(seg_model[te], 0.01, 0.99))
        def obj(params):
            a, b = params
            return brier(expit(a * logits_tr + b), seg_actual[tr])
        res = minimize(obj, x0=[1.0, 0.0], method='Nelder-Mead')
        a, b = res.x
        seg_cal[te] = expit(a * logits_te + b)
    
    cal_platt[mask] = np.clip(seg_cal, 0.01, 0.99)
    
    # Full-segment params
    logits_all = logit(np.clip(seg_model, 0.01, 0.99))
    def obj_all(params):
        a, b = params
        return brier(expit(a * logits_all + b), seg_actual)
    res_all = minimize(obj_all, x0=[1.0, 0.0], method='Nelder-Mead')
    a_all, b_all = res_all.x
    
    b_raw = brier(seg_model, seg_actual)
    b_cal = brier(seg_cal, seg_actual)
    b_m = brier(market_p[mask], seg_actual)
    delta = (b_cal - b_raw) / b_raw * 100
    print(f"  {seg_name:15s} a={a_all:.3f} b={b_all:+.3f}  n={mask.sum():3d}  raw={b_raw:.4f}  cal={b_cal:.4f}  mkt={b_m:.4f}  ({delta:+.1f}%)")

b_platt = brier(cal_platt, actual)
gap_platt = (b_platt / b_mkt_overall - 1) * 100
print(f"\n  Overall: raw={b_raw_overall:.4f}  platt={b_platt:.4f}  mkt={b_mkt_overall:.4f}")
print(f"  Gap: {gap_before:+.1f}% -> {gap_platt:+.1f}%")


# ── Method 3: Bias Correction (learn from market directly) ──
print("\n--- Method 3: Market-informed bias correction ---")
print("  p_cal = p_model + E[market - model]  (per segment, LOMO-CV)\n")

cal_bias = np.copy(model_p)
for seg_name, mask in segments.items():
    logo = LeaveOneGroupOut()
    seg_groups = groups[mask]
    seg_model = model_p[mask]
    seg_market = market_p[mask]
    seg_actual = actual[mask]
    seg_cal = np.full(mask.sum(), np.nan)
    
    for tr, te in logo.split(seg_model.reshape(-1, 1), seg_actual, seg_groups):
        bias = np.mean(seg_market[tr] - seg_model[tr])
        seg_cal[te] = np.clip(seg_model[te] + bias, 0.01, 0.99)
    
    cal_bias[mask] = seg_cal
    avg_bias = np.mean(seg_market - seg_model)
    
    b_raw = brier(seg_model, seg_actual)
    b_cal = brier(seg_cal, seg_actual)
    b_m = brier(market_p[mask], seg_actual)
    delta = (b_cal - b_raw) / b_raw * 100
    print(f"  {seg_name:15s} bias={avg_bias:+.4f}  n={mask.sum():3d}  raw={b_raw:.4f}  cal={b_cal:.4f}  mkt={b_m:.4f}  ({delta:+.1f}%)")

b_bias = brier(cal_bias, actual)
gap_bias = (b_bias / b_mkt_overall - 1) * 100
print(f"\n  Overall: raw={b_raw_overall:.4f}  bias={b_bias:.4f}  mkt={b_mkt_overall:.4f}")
print(f"  Gap: {gap_before:+.1f}% -> {gap_bias:+.1f}%")


# ── Method 4: Outcome-targeted Platt (fit on actual, not market) ──
print("\n--- Method 4: Outcome-targeted Platt (fit on actual wins, not market) ---")
print("  Same as Platt but optimizes for predicting actual outcome\n")

cal_outcome = np.copy(model_p)
for seg_name, mask in segments.items():
    logo = LeaveOneGroupOut()
    seg_groups = groups[mask]
    seg_model = model_p[mask]
    seg_actual = actual[mask]
    seg_cal = np.full(mask.sum(), np.nan)
    
    for tr, te in logo.split(seg_model.reshape(-1, 1), seg_actual, seg_groups):
        logits_tr = logit(np.clip(seg_model[tr], 0.01, 0.99))
        logits_te = logit(np.clip(seg_model[te], 0.01, 0.99))
        def obj(params):
            a, b = params
            p = expit(a * logits_tr + b)
            return brier(p, seg_actual[tr])
        res = minimize(obj, x0=[1.0, 0.0], method='Nelder-Mead')
        a, b = res.x
        seg_cal[te] = expit(a * logits_te + b)
    
    cal_outcome[mask] = np.clip(seg_cal, 0.01, 0.99)
    
    b_raw = brier(seg_model, seg_actual)
    b_cal = brier(seg_cal, seg_actual)
    b_m = brier(market_p[mask], seg_actual)
    delta = (b_cal - b_raw) / b_raw * 100
    print(f"  {seg_name:15s} n={mask.sum():3d}  raw={b_raw:.4f}  cal={b_cal:.4f}  mkt={b_m:.4f}  ({delta:+.1f}%)")

b_outcome = brier(cal_outcome, actual)
gap_outcome = (b_outcome / b_mkt_overall - 1) * 100
print(f"\n  Overall: raw={b_raw_overall:.4f}  outcome={b_outcome:.4f}  mkt={b_mkt_overall:.4f}")
print(f"  Gap: {gap_before:+.1f}% -> {gap_outcome:+.1f}%")


# ── FINAL COMPARISON ──
print("\n" + "=" * 70)
print("  FINAL COMPARISON (all methods)")
print("=" * 70)

results = [
    ('Market (gold)', market_p),
    ('Raw model', model_p),
    ('Temp scaling/phase', cal_temp),
    ('Platt scaling/phase', cal_platt),
    ('Bias correction/phase', cal_bias),
    ('Outcome Platt/phase', cal_outcome),
]

header = f"  {'Method':25s} {'Brier':>8s} {'vs Mkt':>8s} {'Gap Closed':>12s}"
print(header)
print(f"  {'-'*25} {'-'*8} {'-'*8} {'-'*12}")

raw_gap = b_raw_overall - b_mkt_overall
for name, preds in results:
    b = brier(preds, actual)
    vs = (b / b_mkt_overall - 1) * 100
    if name in ('Market (gold)', 'Raw model'):
        gc = ''
    else:
        gc = f"{(1 - (b - b_mkt_overall) / raw_gap) * 100:.1f}%"
    print(f"  {name:25s} {b:8.4f} {vs:+7.1f}% {gc:>12s}")


# ── SEGMENT BREAKDOWN for best method ──
# Find best
best_name = min(results[2:], key=lambda x: brier(x[1], actual))
best_cal = best_name[1]
best_label = best_name[0]

print(f"\n  Best method: {best_label}")
print(f"\n  Segment breakdown:")
print(f"  {'Segment':20s} {'N':>5s} {'Market':>8s} {'Raw':>8s} {'Best':>8s} {'Improved':>10s}")
print(f"  {'-'*20} {'-'*5} {'-'*8} {'-'*8} {'-'*8} {'-'*10}")

for seg_name, mask in segments.items():
    b_m = brier(market_p[mask], actual[mask])
    b_r = brier(model_p[mask], actual[mask])
    b_c = brier(best_cal[mask], actual[mask])
    improved = 'YES' if b_c < b_r else 'NO'
    print(f"  {seg_name:20s} {mask.sum():5d} {b_m:8.4f} {b_r:8.4f} {b_c:8.4f} {improved:>10s}")

print("\nDone.")
