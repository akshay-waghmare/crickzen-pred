"""
IPL Resource Calculator Analysis — Identifies systematic bias and proposes improvements.

Findings:
1. resource_win_prob is systematically under-confident (ECE=0.1075 inn2, 0.1348 inn1)
2. Wicket penalties and rate adjustments HURT inn2 Brier by +6.7%
3. Per-over linear midpoint reduces ECE by 87% (0.1075 → 0.0123)
4. Optimal midpoint: 8.56 + 0.134 * over_0idx (increases from 8.56 to 11.11)

Usage:
    python scripts/analyze_resource_calculator.py
"""
import pandas as pd
import numpy as np
import sys
import warnings
from scipy.optimize import minimize

warnings.filterwarnings('ignore')
sys.path.insert(0, 'src')

print("Loading data...")
raw = pd.read_parquet('data/ipl_raw/matches')
raw = raw.drop_duplicates(subset=['match_id', 'innings', 'over', 'ball'], keep='first')
raw = raw.sort_values(['match_id', 'innings', 'over', 'ball']).reset_index(drop=True)
feat = pd.read_parquet('data/ipl_features_v3/training.parquet')
n = len(feat)
for c in ['innings', 'over', 'ball', 'season', 'match_id', 'batting_team', 'winner']:
    feat[c] = raw[c].values[:n]

feat['actual_wins'] = (feat.batting_team == feat.winner).astype(float)

# ── Helper functions ──
def brier(y, p): return np.mean((y - p) ** 2)

def ece(y, p, bins=10):
    edges = np.linspace(0, 1, bins + 1)
    total = 0
    for i in range(bins):
        mask = (p >= edges[i]) & (p < edges[i + 1])
        if mask.sum() == 0:
            continue
        total += mask.sum() * abs(p[mask].mean() - y[mask].mean())
    return total / len(y)


# ═══════════════════════════════════════════════════════════
# INNINGS 2 ANALYSIS
# ═══════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("INNINGS 2: resource_win_prob CALIBRATION ANALYSIS")
print("=" * 80)

inn2 = feat[feat.innings == 2].copy()
last = inn2.groupby(['match_id', 'over']).tail(1).copy()

rrr_all = last.required_run_rate.values
y_all = last.actual_wins.values
rwp_all = last.resource_win_prob.values
ov_all = last['over'].values
mask = (rrr_all > 0) & (rrr_all < 30) & np.isfinite(rrr_all)
rrr, y, rwp, ov = rrr_all[mask], y_all[mask], rwp_all[mask], ov_all[mask]

print(f"\nFitting on {len(y)} per-over observations (all IPL historical)")

# ── 1. Calibration by probability bin ──
print("\n── resource_win_prob Calibration (10 bins) ──")
print(f"{'Bin':>15s}  {'N':>5s}  {'Pred':>6s}  {'Actual':>6s}  {'Bias':>7s}")
bins_edges = np.linspace(0, 1, 11)
for i in range(10):
    m = (rwp >= bins_edges[i]) & (rwp < bins_edges[i + 1])
    if m.sum() == 0:
        continue
    pred = rwp[m].mean()
    act = y[m].mean()
    print(f"  ({bins_edges[i]:.1f}, {bins_edges[i+1]:.1f}]  {m.sum():5d}  {pred:.3f}   {act:.3f}  {pred - act:+.3f}")

ece_rwp = ece(y, rwp)
brier_rwp = brier(y, rwp)
print(f"\n  resource_win_prob ECE:   {ece_rwp:.4f}")
print(f"  resource_win_prob Brier: {brier_rwp:.4f}")

# ── 2. Pure RRR sigmoid (no wicket penalty, no rate adj) ──
p_pure = 1.0 / (1.0 + np.exp(np.clip(0.57 * (rrr - 9.5), -700, 700)))
brier_pure = brier(y, p_pure)
ece_pure = ece(y, p_pure)
print(f"\n── Pure RRR Sigmoid (beta=0.57, mid=9.5) ──")
print(f"  Brier: {brier_pure:.4f}  ({(brier_pure / brier_rwp - 1) * 100:+.1f}% vs rwp)")
print(f"  ECE:   {ece_pure:.4f}")
print(f"  → Wicket penalty + rate adj HURT Brier by {(brier_rwp / brier_pure - 1) * 100:+.1f}%")

# ── 3. Per-over linear midpoint optimization ──
def perover_brier(params, rrr, ov, y):
    beta, m0, m1 = params
    mid = m0 + m1 * ov
    p = 1.0 / (1.0 + np.exp(np.clip(beta * (rrr - mid), -700, 700)))
    return np.mean((y - p) ** 2)

res = minimize(perover_brier, [0.57, 9.0, 0.1], args=(rrr, ov, y), method='Nelder-Mead')
opt_beta, opt_m0, opt_m1 = res.x
opt_brier = res.fun
p_opt = 1.0 / (1.0 + np.exp(np.clip(opt_beta * (rrr - (opt_m0 + opt_m1 * ov)), -700, 700)))
ece_opt = ece(y, p_opt)

print(f"\n── Per-Over Linear Midpoint (OPTIMAL) ──")
print(f"  Formula: midpoint = {opt_m0:.2f} + {opt_m1:.3f} * over_0idx")
print(f"  Beta: {opt_beta:.3f}")
print(f"  Brier: {opt_brier:.4f}  ({(opt_brier / brier_rwp - 1) * 100:+.1f}% vs rwp, {(opt_brier / brier_pure - 1) * 100:+.1f}% vs pure)")
print(f"  ECE:   {ece_opt:.4f}  ({(ece_opt / ece_rwp - 1) * 100:+.1f}% vs rwp)")

print(f"\n── Per-Over Midpoint Values ──")
for o in range(0, 20):
    mid = opt_m0 + opt_m1 * o
    print(f"  Over {o + 1:2d}: midpoint = {mid:.2f}")

# ── 4. Actual win rate by RRR bin ──
print(f"\n── Win Rate by RRR Bin ──")
print(f"{'RRR':>8s}  {'N':>5s}  {'Actual':>6s}  {'RWP':>6s}  {'Pure':>6s}  {'PerOv':>6s}")
rrr_bins = np.arange(0, 18, 1)
for i in range(len(rrr_bins) - 1):
    m = (rrr >= rrr_bins[i]) & (rrr < rrr_bins[i + 1])
    if m.sum() < 20:
        continue
    act = y[m].mean()
    rw = rwp[m].mean()
    pp = p_pure[m].mean()
    po = p_opt[m].mean()
    print(f"  {rrr_bins[i]:2d}-{rrr_bins[i+1]:2d}  {m.sum():5d}  {act:.3f}   {rw:.3f}   {pp:.3f}   {po:.3f}")

# ── 5. Per-over Brier comparison ──
print(f"\n── Per-Over Brier Score Comparison ──")
print(f"{'Over':>4s}  {'N':>5s}  {'RWP':>8s}  {'Pure':>8s}  {'PerOv':>8s}  {'PerOv vs RWP':>12s}")
for o in range(0, 20):
    m = ov == o
    if m.sum() < 30:
        continue
    b_rwp = brier(y[m], rwp[m])
    b_pure = brier(y[m], p_pure[m])
    b_opt = brier(y[m], p_opt[m])
    delta = (b_opt / b_rwp - 1) * 100
    print(f"  {o + 1:2d}  {m.sum():5d}  {b_rwp:.4f}   {b_pure:.4f}   {b_opt:.4f}   {delta:+.1f}%")

# ═══════════════════════════════════════════════════════════
# INNINGS 1 ANALYSIS (brief)
# ═══════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("INNINGS 1: resource_win_prob CALIBRATION (brief)")
print("=" * 80)

inn1 = feat[feat.innings == 1].copy()
last1 = inn1.groupby(['match_id', 'over']).tail(1).copy()
y1 = last1.actual_wins.values
rwp1 = last1.resource_win_prob.values

ece1 = ece(y1, rwp1)
brier1 = brier(y1, rwp1)
print(f"  resource_win_prob ECE:   {ece1:.4f}")
print(f"  resource_win_prob Brier: {brier1:.4f}")
print(f"  Observations: {len(y1)}")

# Calibration bins
print(f"\n  {'Bin':>15s}  {'N':>5s}  {'Pred':>6s}  {'Actual':>6s}  {'Bias':>7s}")
for i in range(10):
    m = (rwp1 >= bins_edges[i]) & (rwp1 < bins_edges[i + 1])
    if m.sum() == 0:
        continue
    pred = rwp1[m].mean()
    act = y1[m].mean()
    print(f"  ({bins_edges[i]:.1f}, {bins_edges[i+1]:.1f}]  {m.sum():5d}  {pred:.3f}   {act:.3f}  {pred - act:+.3f}")

# ═══════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("SUMMARY: RESOURCE CALCULATOR IMPROVEMENT POTENTIAL (INN2)")
print("=" * 80)
print(f"""
  Current resource_win_prob:        Brier={brier_rwp:.4f}  ECE={ece_rwp:.4f}
  Pure RRR sigmoid (no adjustments): Brier={brier_pure:.4f}  ECE={ece_pure:.4f}  [{(brier_pure / brier_rwp - 1) * 100:+.1f}% Brier]
  Per-over linear midpoint:         Brier={opt_brier:.4f}  ECE={ece_opt:.4f}  [{(opt_brier / brier_rwp - 1) * 100:+.1f}% Brier, {(ece_opt / ece_rwp - 1) * 100:+.0f}% ECE]

  ROOT CAUSE: Wicket penalty + rate adj hurt Brier by {(brier_rwp / brier_pure - 1) * 100:+.1f}%
  SOLUTION:   Per-over midpoint = {opt_m0:.2f} + {opt_m1:.3f} * over_0idx (beta={opt_beta:.3f})
  
  Midpoint increase reflects: IPL teams accelerate in death overs,
  sustaining higher RRR with fewer wickets. The sigmoid should be 
  MORE generous (higher midpoint) in later overs.

  RECOMMENDED CHANGES to format_config.py (IPL):
    rrr_midpoint_intercept = {opt_m0:.2f}  # replaces fixed rrr_midpoint=9.5
    rrr_midpoint_slope = {opt_m1:.3f}       # NEW: per-over shift
    rrr_beta = {opt_beta:.3f}               # slight increase from 0.57
    
  ALSO: Consider removing or reducing wicket_mult and rate_factor in
  calculator.py for inn2 — they add noise rather than signal.
""")
