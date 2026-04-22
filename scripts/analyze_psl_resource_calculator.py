"""
PSL Resource Calculator Analysis — Find optimal rrr_midpoint and rrr_midpoint_slope.

Mirrors the IPL analysis from scripts/analyze_resource_calculator.py but for PSL data.

IPL finding: Per-over adaptive midpoint reduced inn2 ECE by -89% (0.1075 → 0.0123).
PSL currently uses fixed midpoint (9.5, slope=0.0) — this script finds the optimal values.

Usage:
    python scripts/analyze_psl_resource_calculator.py
"""
import sys
import warnings
import numpy as np
import pandas as pd
from scipy.optimize import minimize

warnings.filterwarnings("ignore")
sys.path.insert(0, "src")

# ── Load PSL features (already has all needed columns) ──────────────────────
print("Loading PSL features...")
feat = pd.read_parquet("data/psl_features_v1/training.parquet")
feat["actual_wins"] = feat["is_winner"].astype(float)
print(f"  {len(feat):,} rows, {feat['match_id'].nunique()} matches")


# ── Helper functions ─────────────────────────────────────────────────────────
def brier(y, p):
    return np.mean((y - p) ** 2)


def ece(y, p, bins=10):
    edges = np.linspace(0, 1, bins + 1)
    total = 0
    for i in range(bins):
        mask = (p >= edges[i]) & (p < edges[i + 1])
        if mask.sum() == 0:
            continue
        total += mask.sum() * abs(p[mask].mean() - y[mask].mean())
    return total / len(y)


def perover_brier(params, rrr, ov, y):
    beta, m0, m1 = params
    mid = m0 + m1 * ov
    p = 1.0 / (1.0 + np.exp(np.clip(beta * (rrr - mid), -700, 700)))
    return np.mean((y - p) ** 2)


# ═══════════════════════════════════════════════════════════════════════════
# INNINGS 2 ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("INNINGS 2: resource_win_prob PSL CALIBRATION ANALYSIS")
print("=" * 80)

inn2 = feat[feat["innings"] == 2].copy()
last = inn2.groupby(["match_id", "over"]).tail(1).copy()

rrr_all = last["required_run_rate"].values
y_all = last["actual_wins"].values
rwp_all = last["resource_win_prob"].values
ov_all = last["over"].values - 1  # Convert to 0-indexed

mask = (rrr_all > 0) & (rrr_all < 30) & np.isfinite(rrr_all)
rrr, y, rwp, ov = rrr_all[mask], y_all[mask], rwp_all[mask], ov_all[mask]

print(f"\nFitting on {len(y)} per-over observations ({last['match_id'].nunique()} PSL matches)")

# ── 1. Current resource_win_prob calibration ─────────────────────────────
print("\n── Current resource_win_prob Calibration (10 probability bins) ──")
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

# ── 2. Pure RRR sigmoid with current PSL params (beta=0.7, mid=9.5) ──────
p_current = 1.0 / (1.0 + np.exp(np.clip(0.7 * (rrr - 9.5), -700, 700)))
brier_current = brier(y, p_current)
ece_current = ece(y, p_current)
print(f"\n── Pure RRR Sigmoid (PSL current: beta=0.7, mid=9.5, slope=0.0) ──")
print(f"  Brier: {brier_current:.4f}  ({(brier_current / brier_rwp - 1) * 100:+.1f}% vs rwp)")
print(f"  ECE:   {ece_current:.4f}")

# ── 3. Per-over linear midpoint optimization ──────────────────────────────
print(f"\n── Optimizing Per-Over Linear Midpoint ──")

# Use PSL current params as starting point
res = minimize(
    perover_brier,
    [0.7, 9.0, 0.1],
    args=(rrr, ov, y),
    method="Nelder-Mead",
    options={"maxiter": 10000, "xatol": 1e-6, "fatol": 1e-8},
)
opt_beta, opt_m0, opt_m1 = res.x
opt_brier = res.fun
p_opt = 1.0 / (1.0 + np.exp(np.clip(opt_beta * (rrr - (opt_m0 + opt_m1 * ov)), -700, 700)))
ece_opt = ece(y, p_opt)

print(f"  Optimal formula: midpoint = {opt_m0:.3f} + {opt_m1:.4f} * over_0idx")
print(f"  Optimal beta: {opt_beta:.4f}")
print(f"  Brier: {opt_brier:.4f}  ({(opt_brier / brier_rwp - 1) * 100:+.1f}% vs rwp, {(opt_brier / brier_current - 1) * 100:+.1f}% vs current)")
print(f"  ECE:   {ece_opt:.4f}  ({(ece_opt / ece_rwp - 1) * 100:+.1f}% vs rwp)")

# ── Per-over midpoint table ───────────────────────────────────────────────
print(f"\n── Per-Over Midpoint Values (PSL optimal) ──")
for o in range(0, 20):
    mid = opt_m0 + opt_m1 * o
    print(f"  Over {o + 1:2d}: midpoint = {mid:.2f}")

# ── 4. Win rate by RRR bin ────────────────────────────────────────────────
print(f"\n── Win Rate by RRR Bin ──")
print(f"{'RRR':>8s}  {'N':>5s}  {'Actual':>6s}  {'Current':>8s}  {'Optimal':>8s}  {'Bias_cur':>9s}  {'Bias_opt':>9s}")
rrr_bins = np.arange(0, 20, 1)
for i in range(len(rrr_bins) - 1):
    m = (rrr >= rrr_bins[i]) & (rrr < rrr_bins[i + 1])
    if m.sum() < 15:
        continue
    act = y[m].mean()
    pc = p_current[m].mean()
    po = p_opt[m].mean()
    print(f"  {rrr_bins[i]:2d}-{rrr_bins[i+1]:2d}  {m.sum():5d}  {act:.3f}   {pc:.3f}    {po:.3f}    {pc - act:+.3f}    {po - act:+.3f}")

# ── 5. Per-phase analysis ─────────────────────────────────────────────────
print(f"\n── Per-Phase Brier & Bias Comparison ──")
print(f"{'Phase':>15s}  {'N':>5s}  {'Actual':>6s}  {'Current_p':>9s}  {'Opt_p':>7s}  {'Brier_cur':>10s}  {'Brier_opt':>10s}")
phases = {
    "powerplay": (1, 7),
    "middle":    (7, 15),
    "death":     (15, 19),
    "final":     (19, 20),
}
for phase, (lo, hi) in phases.items():
    m = (ov >= lo - 1) & (ov < hi)
    if m.sum() < 15:
        continue
    act = y[m].mean()
    pc = p_current[m].mean()
    po = p_opt[m].mean()
    bc = brier(y[m], p_current[m])
    bo = brier(y[m], p_opt[m])
    print(f"  {phase:>15s}  {m.sum():5d}  {act:.3f}   {pc:.3f}    {po:.3f}    {bc:.4f}     {bo:.4f}")

# ── 6. Per-over Brier ─────────────────────────────────────────────────────
print(f"\n── Per-Over Brier Comparison ──")
print(f"{'Over':>4s}  {'N':>5s}  {'RWP':>8s}  {'Current':>8s}  {'Optimal':>8s}  {'Opt vs RWP':>12s}")
for o in range(0, 20):
    m = ov == o
    if m.sum() < 20:
        continue
    b_rwp = brier(y[m], rwp[m])
    b_cur = brier(y[m], p_current[m])
    b_opt = brier(y[m], p_opt[m])
    delta = (b_opt / b_rwp - 1) * 100
    print(f"  {o + 1:2d}  {m.sum():5d}  {b_rwp:.4f}   {b_cur:.4f}   {b_opt:.4f}   {delta:+.1f}%")

# ═══════════════════════════════════════════════════════════════════════════
# INNINGS 1 ANALYSIS (brief)
# ═══════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("INNINGS 1: resource_win_prob CALIBRATION (PSL, brief)")
print("=" * 80)

inn1 = feat[feat["innings"] == 1].copy()
last1 = inn1.groupby(["match_id", "over"]).tail(1).copy()
y1 = last1["actual_wins"].values
rwp1 = last1["resource_win_prob"].values

ece1 = ece(y1, rwp1)
brier1 = brier(y1, rwp1)
print(f"\n  resource_win_prob ECE:   {ece1:.4f}")
print(f"  resource_win_prob Brier: {brier1:.4f}")
print(f"  Observations: {len(y1)}")

print(f"\n── Calibration Bins (Inn1) ──")
print(f"{'Bin':>15s}  {'N':>5s}  {'Pred':>6s}  {'Actual':>6s}  {'Bias':>7s}")
for i in range(10):
    m = (rwp1 >= bins_edges[i]) & (rwp1 < bins_edges[i + 1])
    if m.sum() == 0:
        continue
    pred = rwp1[m].mean()
    act = y1[m].mean()
    print(f"  ({bins_edges[i]:.1f}, {bins_edges[i+1]:.1f}]  {m.sum():5d}  {pred:.3f}   {act:.3f}  {pred - act:+.3f}")

# ═══════════════════════════════════════════════════════════════════════════
# SUMMARY + RECOMMENDED CONFIG
# ═══════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("SUMMARY: RECOMMENDED FormatConfig.psl() CHANGES")
print("=" * 80)
print(f"""
  Current PSL config:
    rrr_beta = 0.7
    rrr_midpoint = 9.5
    rrr_midpoint_slope = 0.0  (fixed midpoint)

  Optimal PSL config (from {len(y)} per-over observations):
    rrr_beta = {opt_beta:.3f}
    rrr_midpoint = {opt_m0:.3f}        # replaces 9.5
    rrr_midpoint_slope = {opt_m1:.4f}  # NEW: per-over shift

  Inn2 resource_win_prob improvement:
    ECE:   {ece_rwp:.4f} → {ece_opt:.4f}  ({(ece_opt / ece_rwp - 1) * 100:+.1f}%)
    Brier: {brier_rwp:.4f} → {opt_brier:.4f}  ({(opt_brier / brier_rwp - 1) * 100:+.1f}%)

  IPL comparison (for context):
    IPL optimal: midpoint = 8.56 + 0.134 * over_0idx
    ECE improvement: 0.1075 → 0.0123 (-88%)

  How this fixes inn2 death bias:
    The per-over midpoint increases in later overs, making the model
    MORE generous to chasers with high RRR in death. This directly
    addresses the -0.154 avg_prob_diff seen in inn2_death for PSL.
""")
