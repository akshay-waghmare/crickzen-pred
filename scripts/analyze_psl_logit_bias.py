"""
PSL Logit-Space Bias Correction Analysis
=========================================
Tests multiple LOMO-CV bias correction strategies on PSL betx21 data
to evaluate how much of the market gap can be closed post-hoc.

Methods compared (all use Leave-One-Match-Out CV):
  1. Raw              — no correction
  2. Additive phase   — add mean(market − model) per inn×phase segment
  3. Logit phase      — same in logit space (respects [0,1] bounds)
  4. Logit fine phase — inn × {powerplay, early_middle, late_middle, death}
  5. Logit per-over   — fine-grained; falls back to phase for sparse overs
  6. Scale phase      — multiplicative correction per inn×phase

Loads: data/psl_betx21_model_vs_market.parquet
"""
import sys, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, "src")

import numpy as np
import pandas as pd
from scipy.special import logit, expit
from sklearn.model_selection import LeaveOneGroupOut
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PARQUET_PATH = PROJECT_ROOT / "data" / "psl_betx21_model_vs_market.parquet"

# ── helpers ────────────────────────────────────────────────────────────────

def brier(p, y):
    return float(np.mean((p - y) ** 2))


def ece(p, y, n_bins=10):
    edges = np.linspace(0, 1, n_bins + 1)
    total = len(p)
    acc = 0.0
    for i in range(n_bins):
        lo, hi = edges[i], edges[i + 1]
        mask = (p >= lo) & (p < hi) if i < n_bins - 1 else (p >= lo) & (p <= hi)
        n = mask.sum()
        if n:
            acc += (n / total) * abs(p[mask].mean() - y[mask].mean())
    return float(acc)


def assign_phase(over):
    if over <= 6:   return "powerplay"
    elif over <= 15: return "middle"
    else:            return "death"


def assign_phase_fine(over):
    if over <= 6:   return "powerplay"
    elif over <= 10: return "early_middle"
    elif over <= 15: return "late_middle"
    else:            return "death"


# ── LOMO correction kernels ────────────────────────────────────────────────

def lomo_logit_bias(model_p, market_p, actual, groups, seg_labels, min_obs=5, min_groups=3):
    """LOMO additive bias correction in logit space."""
    cal = model_p.copy()
    logo = LeaveOneGroupOut()
    for seg in np.unique(seg_labels):
        mask = seg_labels == seg
        if mask.sum() < min_obs:
            continue
        g, mp, mkt, a = groups[mask], model_p[mask], market_p[mask], actual[mask]
        if len(np.unique(g)) < min_groups:
            continue
        seg_cal = np.full(mask.sum(), np.nan)
        mp_l  = logit(np.clip(mp,  0.01, 0.99))
        mkt_l = logit(np.clip(mkt, 0.01, 0.99))
        for tr, te in logo.split(mp_l.reshape(-1, 1), a, g):
            bias = float(np.mean(mkt_l[tr] - mp_l[tr]))
            seg_cal[te] = expit(mp_l[te] + bias)
        valid = ~np.isnan(seg_cal)
        cal[np.where(mask)[0][valid]] = np.clip(seg_cal[valid], 0.01, 0.99)
    return cal


def lomo_additive_bias(model_p, market_p, actual, groups, seg_labels, min_obs=5, min_groups=3):
    """LOMO additive bias correction in probability space."""
    cal = model_p.copy()
    logo = LeaveOneGroupOut()
    for seg in np.unique(seg_labels):
        mask = seg_labels == seg
        if mask.sum() < min_obs:
            continue
        g, mp, mkt, a = groups[mask], model_p[mask], market_p[mask], actual[mask]
        if len(np.unique(g)) < min_groups:
            continue
        seg_cal = np.full(mask.sum(), np.nan)
        for tr, te in logo.split(mp.reshape(-1, 1), a, g):
            bias = float(np.mean(mkt[tr] - mp[tr]))
            seg_cal[te] = np.clip(mp[te] + bias, 0.01, 0.99)
        valid = ~np.isnan(seg_cal)
        cal[np.where(mask)[0][valid]] = seg_cal[valid]
    return cal


def lomo_scale_bias(model_p, market_p, actual, groups, seg_labels, min_obs=5, min_groups=3):
    """LOMO multiplicative scale correction per segment."""
    cal = model_p.copy()
    logo = LeaveOneGroupOut()
    for seg in np.unique(seg_labels):
        mask = seg_labels == seg
        if mask.sum() < min_obs:
            continue
        g, mp, mkt, a = groups[mask], model_p[mask], market_p[mask], actual[mask]
        if len(np.unique(g)) < min_groups:
            continue
        seg_cal = np.full(mask.sum(), np.nan)
        for tr, te in logo.split(mp.reshape(-1, 1), a, g):
            mean_mkt = np.mean(mkt[tr])
            mean_mp  = np.mean(mp[tr])
            scale = mean_mkt / mean_mp if mean_mp > 0.01 else 1.0
            seg_cal[te] = np.clip(mp[te] * scale, 0.01, 0.99)
        valid = ~np.isnan(seg_cal)
        cal[np.where(mask)[0][valid]] = seg_cal[valid]
    return cal


def hierarchical_logit(model_p, market_p, actual, groups, over_labels, phase_labels,
                        min_over_obs=12, min_groups=3):
    """Per-over logit bias with phase-level fallback for sparse overs."""
    phase_cal = lomo_logit_bias(model_p, market_p, actual, groups, phase_labels)
    cal = model_p.copy()
    logo = LeaveOneGroupOut()
    for ov in np.unique(over_labels):
        mask = over_labels == ov
        if mask.sum() < min_over_obs or len(np.unique(groups[mask])) < min_groups:
            cal[mask] = phase_cal[mask]
            continue
        g, mp, mkt, a = groups[mask], model_p[mask], market_p[mask], actual[mask]
        seg_cal = np.full(mask.sum(), np.nan)
        mp_l  = logit(np.clip(mp,  0.01, 0.99))
        mkt_l = logit(np.clip(mkt, 0.01, 0.99))
        for tr, te in logo.split(mp_l.reshape(-1, 1), a, g):
            bias = float(np.mean(mkt_l[tr] - mp_l[tr]))
            seg_cal[te] = expit(mp_l[te] + bias)
        valid = ~np.isnan(seg_cal)
        cal_idx = np.where(mask)[0]
        cal[cal_idx[valid]]   = np.clip(seg_cal[valid], 0.01, 0.99)
        cal[cal_idx[~valid]]  = phase_cal[mask][~valid]
    return cal


# ── main ──────────────────────────────────────────────────────────────────

def main():
    if not PARQUET_PATH.exists():
        print(f"ERROR: {PARQUET_PATH} not found. Run analyze_psl_betx21_market.py first.")
        sys.exit(1)

    df = pd.read_parquet(PARQUET_PATH)
    print(f"Loaded {len(df)} observations, {df['event_id'].nunique()} matches")

    model_p  = df["model_p_t1"].values.astype(float)
    market_p = df["market_p_t1"].values.astype(float)
    actual   = df["actual_t1_wins"].values.astype(float)
    groups   = df["event_id"].values

    df["phase"]      = df["over"].apply(assign_phase)
    df["phase_fine"] = df["over"].apply(assign_phase_fine)

    seg_phase    = np.array([f"inn{i}_{p}" for i, p in zip(df["innings"], df["phase"])])
    seg_fine     = np.array([f"inn{i}_{p}" for i, p in zip(df["innings"], df["phase_fine"])])
    seg_over     = np.array([f"inn{i}_ov{o}" for i, o in zip(df["innings"], df["over"])])

    b_mkt = brier(market_p, actual)
    b_raw = brier(model_p, actual)

    print(f"\n{'='*72}")
    print(f"  PSL LOGIT-SPACE BIAS CORRECTION  ({len(df)} obs, {df['event_id'].nunique()} matches)")
    print(f"  Market Brier: {b_mkt:.4f}   |   Model Raw: {b_raw:.4f}   (+{(b_raw/b_mkt-1)*100:.1f}%)")
    print(f"{'='*72}")

    # ── Run all methods ──────────────────────────────────────────────────
    methods = {}

    methods["1_raw"]                = model_p.copy()
    methods["2_additive_6seg"]      = lomo_additive_bias(model_p, market_p, actual, groups, seg_phase)
    methods["3_logit_6seg"]         = lomo_logit_bias(model_p, market_p, actual, groups, seg_phase)
    methods["4_logit_fine_8seg"]    = lomo_logit_bias(model_p, market_p, actual, groups, seg_fine)
    methods["5_logit_per_over"]     = hierarchical_logit(model_p, market_p, actual, groups, seg_over, seg_phase)
    methods["6_scale_6seg"]         = lomo_scale_bias(model_p, market_p, actual, groups, seg_phase)

    gap_total = b_raw - b_mkt
    print(f"\n  {'Method':<26s} {'Brier':>8s} {'vs Mkt':>8s} {'Gap Closed':>11s} {'ECE':>8s}")
    print(f"  {'-'*65}")
    print(f"  {'Market (target)':<26s} {b_mkt:8.4f} {'—':>8s} {'—':>11s} {ece(market_p, actual):8.4f}")
    for name, cal in sorted(methods.items(), key=lambda x: brier(x[1], actual)):
        bc = brier(cal, actual)
        ec = ece(cal, actual)
        pct_vs_mkt = (bc / b_mkt - 1) * 100
        gap_closed = (1 - (bc - b_mkt) / gap_total) * 100 if gap_total > 0 else 0
        win_mark = " ◄BEATS MKT" if bc < b_mkt else ""
        print(f"  {name:<26s} {bc:8.4f} {pct_vs_mkt:+7.1f}% {gap_closed:+10.1f}%{win_mark}   ECE={ec:.4f}")

    # ── Pick best and show segment breakdown ────────────────────────────
    best_name = min(methods, key=lambda k: brier(methods[k], actual))
    best_cal  = methods[best_name]
    best_b    = brier(best_cal, actual)

    print(f"\n  Best method: {best_name} (Brier={best_b:.4f})")
    print(f"\n  Per-segment breakdown ({best_name}):")
    print(f"  {'Segment':<22s} {'n':>4s} {'Market':>8s} {'Raw':>8s} {'Corrected':>10s} {'vs Mkt':>8s}")
    print(f"  {'-'*65}")
    for inn in [1, 2]:
        for ph in ["powerplay", "middle", "death"]:
            mask = (df["innings"].values == inn) & (df["phase"].values == ph)
            if mask.sum() < 3:
                continue
            seg = f"inn{inn}_{ph}"
            bm = brier(market_p[mask], actual[mask])
            br = brier(model_p[mask], actual[mask])
            bc = brier(best_cal[mask], actual[mask])
            improvement = (bc / br - 1) * 100
            vs_mkt = (bc / bm - 1) * 100
            win = "  ◄BEATS" if bc < bm else ""
            print(f"  {seg:<22s} {mask.sum():4d} {bm:8.4f} {br:8.4f} {bc:10.4f} {vs_mkt:+7.1f}%{win}")
        # subtotal
        mask_inn = df["innings"].values == inn
        bm = brier(market_p[mask_inn], actual[mask_inn])
        bc = brier(best_cal[mask_inn], actual[mask_inn])
        print(f"  {'INN'+str(inn)+' TOTAL':<22s} {mask_inn.sum():4d} {bm:8.4f} {'':>8s} {bc:10.4f} {(bc/bm-1)*100:+7.1f}%")
        print()

    # ── Inn2-focused comparison: all methods ────────────────────────────
    print(f"  Inn2 Brier comparison (key gap):")
    print(f"  {'Method':<26s} {'Brier':>8s} {'vs Mkt':>8s}")
    print(f"  {'-'*45}")
    mask2 = df["innings"].values == 2
    b_mkt2 = brier(market_p[mask2], actual[mask2])
    for name, cal in sorted(methods.items(), key=lambda x: brier(x[1][mask2], actual[mask2])):
        bc2 = brier(cal[mask2], actual[mask2])
        vm  = (bc2 / b_mkt2 - 1) * 100
        win = "  ◄BEATS" if bc2 < b_mkt2 else ""
        print(f"  {name:<26s} {bc2:8.4f} {vm:+7.1f}%{win}")
    print(f"  {'Market':<26s} {b_mkt2:8.4f}")

    # ── Market blend analysis ────────────────────────────────────────────
    print(f"\n  Optimal blend: alpha*corrected + (1−alpha)*market")
    print(f"  {'Method':<26s} {'best_alpha':>10s} {'blend_brier':>12s} {'vs pure mkt':>12s}")
    print(f"  {'-'*65}")
    for name, cal in sorted(methods.items(), key=lambda x: x[0]):
        if name == "1_raw":
            continue
        best_alpha, best_blend = 0.0, 9999.0
        for alpha in np.arange(0.0, 1.01, 0.05):
            blend = alpha * cal + (1.0 - alpha) * market_p
            bv = brier(blend, actual)
            if bv < best_blend:
                best_alpha, best_blend = alpha, bv
        vs_mkt = (best_blend / b_mkt - 1) * 100
        win = "  ◄BEATS" if best_blend < b_mkt else ""
        print(f"  {name:<26s} {best_alpha:>10.2f} {best_blend:>12.4f} {vs_mkt:>+11.1f}%{win}")

    print(f"\n  Market Brier (pure): {b_mkt:.4f}")
    print(f"  Model Raw Brier:     {b_raw:.4f}")


if __name__ == "__main__":
    main()
