"""
PSL Temperature & Platt Scaling Analysis
==========================================
Tests temperature scaling and Platt scaling on PSL betx21 data.

Two targets evaluated:
  A) Fit to actuals  — NLL minimization against outcomes (standard calibration)
  B) Fit to market   — find T that moves model probs closest to market prices

Methods:
  1. global_T          — single T, in-sample (ceiling)
  2. global_T_inn      — per-innings T, in-sample
  3. lomo_T_overall    — single T, LOMO-CV (honest estimate)
  4. lomo_T_inn        — per-innings T, LOMO-CV
  5. lomo_T_phase      — per inn×phase T (6 params), LOMO-CV
  6. lomo_platt_inn    — Platt scaling per innings, LOMO-CV (2 params each)
  7. lomo_T_mkt_inn    — per-innings T fitted to MATCH MARKET prices, LOMO-CV

Loads: data/psl_betx21_model_vs_market.parquet
"""
import sys, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, "src")

import numpy as np
import pandas as pd
from scipy.optimize import minimize, minimize_scalar
from scipy.special import logit, expit
from sklearn.model_selection import LeaveOneGroupOut
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PARQUET = PROJECT_ROOT / "data" / "psl_betx21_model_vs_market.parquet"

# ── metrics ───────────────────────────────────────────────────────────────

def brier(p, y): return float(np.mean((p - y) ** 2))

def ece(p, y, n=10):
    edges = np.linspace(0, 1, n + 1); t = len(p); acc = 0.0
    for i in range(n):
        m = (p >= edges[i]) & (p < edges[i + 1] if i < n - 1 else p <= edges[i + 1])
        if m.sum(): acc += (m.sum() / t) * abs(p[m].mean() - y[m].mean())
    return acc

def phase(o):
    if o <= 6:    return "powerplay"
    elif o <= 15: return "middle"
    else:         return "death"

# ── temperature core ──────────────────────────────────────────────────────

def apply_temperature(p, T):
    p = np.clip(p, 1e-7, 1 - 1e-7)
    return expit(logit(p) / T)

def fit_temp_to_actuals(p, y, T_init=1.0):
    """NLL-minimizing T against binary outcomes."""
    p = np.clip(p, 1e-7, 1 - 1e-7)
    lgt = logit(p)
    def nll(T):
        pr = expit(lgt / T[0])
        pr = np.clip(pr, 1e-7, 1 - 1e-7)
        return -np.mean(y * np.log(pr) + (1 - y) * np.log(1 - pr))
    res = minimize(nll, [T_init], bounds=[(0.1, 10.0)], method="L-BFGS-B")
    return float(res.x[0])

def fit_temp_to_market(p, market_p):
    """Find T that minimises MSE between apply_temperature(p, T) and market_p."""
    p = np.clip(p, 1e-7, 1 - 1e-7)
    market_p = np.clip(market_p, 1e-7, 1 - 1e-7)
    lgt = logit(p)
    def mse(T):
        pr = expit(lgt / T[0])
        return float(np.mean((pr - market_p) ** 2))
    res = minimize(mse, [1.0], bounds=[(0.1, 10.0)], method="L-BFGS-B")
    return float(res.x[0])

def fit_platt(p, y):
    """Platt scaling: sigmoid(a*logit(p) + b), returns (a, b)."""
    p = np.clip(p, 1e-7, 1 - 1e-7)
    lgt = logit(p)
    def nll(params):
        a, b = params
        pr = expit(a * lgt + b)
        pr = np.clip(pr, 1e-7, 1 - 1e-7)
        return -np.mean(y * np.log(pr) + (1 - y) * np.log(1 - pr))
    res = minimize(nll, [1.0, 0.0], method="L-BFGS-B",
                   bounds=[(0.1, 10.0), (-5.0, 5.0)])
    return float(res.x[0]), float(res.x[1])

def apply_platt(p, a, b):
    p = np.clip(p, 1e-7, 1 - 1e-7)
    return expit(a * logit(p) + b)

# ── LOMO helpers ──────────────────────────────────────────────────────────

def lomo_temperature(model_p, actual, groups, seg_labels, fit_fn, min_obs=5, min_groups=3):
    """LOMO-CV temperature scaling per segment using fit_fn(p, y) -> T."""
    cal = model_p.copy()
    logo = LeaveOneGroupOut()
    T_by_seg = {}
    for seg in np.unique(seg_labels):
        mask = seg_labels == seg
        if mask.sum() < min_obs or len(np.unique(groups[mask])) < min_groups:
            continue
        g, mp, a = groups[mask], model_p[mask], actual[mask]
        seg_cal = np.full(mask.sum(), np.nan)
        Ts = []
        for tr, te in logo.split(mp.reshape(-1, 1), a, g):
            T = fit_fn(mp[tr], a[tr])
            seg_cal[te] = apply_temperature(mp[te], T)
            Ts.append(T)
        valid = ~np.isnan(seg_cal)
        cal[np.where(mask)[0][valid]] = np.clip(seg_cal[valid], 0.01, 0.99)
        T_by_seg[seg] = float(np.mean(Ts))
    return cal, T_by_seg

def lomo_temperature_mkt(model_p, market_p, actual, groups, seg_labels, min_obs=5, min_groups=3):
    """LOMO-CV T fitted to match market prices, evaluated on actuals."""
    cal = model_p.copy()
    logo = LeaveOneGroupOut()
    T_by_seg = {}
    for seg in np.unique(seg_labels):
        mask = seg_labels == seg
        if mask.sum() < min_obs or len(np.unique(groups[mask])) < min_groups:
            continue
        g, mp, mkt, a = groups[mask], model_p[mask], market_p[mask], actual[mask]
        seg_cal = np.full(mask.sum(), np.nan)
        Ts = []
        for tr, te in logo.split(mp.reshape(-1, 1), a, g):
            T = fit_temp_to_market(mp[tr], mkt[tr])
            seg_cal[te] = apply_temperature(mp[te], T)
            Ts.append(T)
        valid = ~np.isnan(seg_cal)
        cal[np.where(mask)[0][valid]] = np.clip(seg_cal[valid], 0.01, 0.99)
        T_by_seg[seg] = float(np.mean(Ts))
    return cal, T_by_seg

def lomo_platt(model_p, actual, groups, seg_labels, min_obs=5, min_groups=3):
    """LOMO-CV Platt scaling per segment."""
    cal = model_p.copy()
    logo = LeaveOneGroupOut()
    for seg in np.unique(seg_labels):
        mask = seg_labels == seg
        if mask.sum() < min_obs or len(np.unique(groups[mask])) < min_groups:
            continue
        g, mp, a = groups[mask], model_p[mask], actual[mask]
        seg_cal = np.full(mask.sum(), np.nan)
        for tr, te in logo.split(mp.reshape(-1, 1), a, g):
            try:
                a_p, b_p = fit_platt(mp[tr], a[tr])
                seg_cal[te] = apply_platt(mp[te], a_p, b_p)
            except Exception:
                seg_cal[te] = mp[te]
        valid = ~np.isnan(seg_cal)
        cal[np.where(mask)[0][valid]] = np.clip(seg_cal[valid], 0.01, 0.99)
    return cal

# ── T sweep (in-sample ceiling) ───────────────────────────────────────────

def t_sweep(model_p, actual, label="all", Ts=None):
    if Ts is None:
        Ts = np.arange(0.3, 2.1, 0.05)
    best_T, best_b = 1.0, brier(model_p, actual)
    for T in Ts:
        b = brier(apply_temperature(model_p, T), actual)
        if b < best_b:
            best_T, best_b = T, b
    return best_T, best_b

# ── main ──────────────────────────────────────────────────────────────────

def main():
    if not PARQUET.exists():
        print(f"ERROR: {PARQUET} not found. Run analyze_psl_betx21_market.py first.")
        sys.exit(1)

    df = pd.read_parquet(PARQUET)
    df["phase"] = df["over"].apply(phase)
    print(f"Loaded {len(df)} obs, {df['event_id'].nunique()} matches")

    model_p  = df["model_p_t1"].values.astype(float)
    market_p = df["market_p_t1"].values.astype(float)
    actual   = df["actual_t1_wins"].values.astype(float)
    groups   = df["event_id"].values

    seg_inn   = np.array([f"inn{i}"         for i in df["innings"]])
    seg_phase = np.array([f"inn{i}_{p}"     for i, p in zip(df["innings"], df["phase"])])

    b_mkt = brier(market_p, actual)
    b_raw = brier(model_p, actual)
    gap   = b_raw - b_mkt

    print(f"\n{'='*74}")
    print(f"  PSL TEMPERATURE & PLATT SCALING  ({len(df)} obs, {df['event_id'].nunique()} matches)")
    print(f"  Market Brier: {b_mkt:.4f}   |   Raw Brier: {b_raw:.4f}   (+{(b_raw/b_mkt-1)*100:.1f}%)")
    print(f"{'='*74}")

    # ── 1. In-sample T sweep (ceiling) ────────────────────────────────────
    methods = {}
    T_summary = {}

    # Global
    T_global, _ = t_sweep(model_p, actual)
    methods["1a_global_T_insampl"] = apply_temperature(model_p, T_global)
    T_summary["global"] = T_global

    # Per-innings in-sample
    pi = model_p.copy()
    T_inn = {}
    for inn in [1, 2]:
        m = df["innings"].values == inn
        T, _ = t_sweep(model_p[m], actual[m])
        pi[m] = apply_temperature(model_p[m], T)
        T_inn[inn] = T
    methods["1b_per_inn_T_insampl"] = pi
    T_summary["inn1_insampl"] = T_inn[1]
    T_summary["inn2_insampl"] = T_inn[2]

    # ── 2. LOMO T fitted to actuals ───────────────────────────────────────
    cal_lomo_T_all, _ = lomo_temperature(
        model_p, actual, groups,
        np.array(["all"] * len(df)),
        fit_fn=lambda p, y: fit_temp_to_actuals(p, y)
    )
    methods["2a_lomo_T_overall"] = cal_lomo_T_all

    cal_lomo_T_inn, T_inn_lomo = lomo_temperature(
        model_p, actual, groups, seg_inn,
        fit_fn=lambda p, y: fit_temp_to_actuals(p, y)
    )
    methods["2b_lomo_T_inn"] = cal_lomo_T_inn
    T_summary.update({f"{k}_lomo": v for k, v in T_inn_lomo.items()})

    cal_lomo_T_phase, T_phase_lomo = lomo_temperature(
        model_p, actual, groups, seg_phase,
        fit_fn=lambda p, y: fit_temp_to_actuals(p, y)
    )
    methods["2c_lomo_T_phase"] = cal_lomo_T_phase

    # ── 3. LOMO Platt per innings ─────────────────────────────────────────
    cal_platt = lomo_platt(model_p, actual, groups, seg_inn)
    methods["3a_lomo_platt_inn"] = cal_platt

    cal_platt_ph = lomo_platt(model_p, actual, groups, seg_phase)
    methods["3b_lomo_platt_phase"] = cal_platt_ph

    # ── 4. LOMO T fitted to MARKET prices ─────────────────────────────────
    cal_mkt_T_inn, T_mkt_inn = lomo_temperature_mkt(
        model_p, market_p, actual, groups, seg_inn
    )
    methods["4a_lomo_T_mkt_inn"] = cal_mkt_T_inn
    T_summary.update({f"{k}_mkt": v for k, v in T_mkt_inn.items()})

    cal_mkt_T_ph, T_mkt_ph = lomo_temperature_mkt(
        model_p, market_p, actual, groups, seg_phase
    )
    methods["4b_lomo_T_mkt_phase"] = cal_mkt_T_ph

    # ── Summary table ─────────────────────────────────────────────────────
    print(f"\n  {'Method':<28s} {'Brier':>8s} {'vs Mkt':>8s} {'Gap Closed':>11s} {'ECE':>8s}")
    print(f"  {'-'*67}")
    print(f"  {'Market (target)':<28s} {b_mkt:8.4f} {'—':>8s} {'—':>11s} {ece(market_p,actual):8.4f}")
    print(f"  {'Raw (no correction)':<28s} {b_raw:8.4f} {(b_raw/b_mkt-1)*100:+7.1f}% {'0.0%':>11s} {ece(model_p,actual):8.4f}")
    print()

    sorted_methods = sorted(methods.items(), key=lambda x: brier(x[1], actual))
    for name, cal in sorted_methods:
        bc = brier(cal, actual)
        gc = (1 - (bc - b_mkt) / gap) * 100 if gap > 0 else 0
        win = "  ◄BEATS MKT" if bc < b_mkt else ""
        print(f"  {name:<28s} {bc:8.4f} {(bc/b_mkt-1)*100:+7.1f}% {gc:+10.1f}%{win}   ECE={ece(cal,actual):.4f}")

    # ── T values fitted ────────────────────────────────────────────────────
    print(f"\n  Fitted Temperature values:")
    print(f"  {'Segment':<25s} {'T (in-sample)':>14s}  note")
    print(f"  {'-'*58}")
    print(f"  {'global':<25s} {T_global:>14.3f}  (T>1=softer, T<1=sharper)")
    print(f"  {'inn1 in-sample':<25s} {T_inn[1]:>14.3f}")
    print(f"  {'inn2 in-sample':<25s} {T_inn[2]:>14.3f}")
    for k, v in sorted(T_inn_lomo.items()):
        print(f"  {k+' LOMO (actuals)':<25s} {v:>14.3f}")
    for k, v in sorted(T_mkt_inn.items()):
        print(f"  {k+' LOMO (market)':<25s} {v:>14.3f}")
    for k, v in sorted(T_mkt_ph.items()):
        print(f"  {k+' LOMO (market)':<25s} {v:>14.3f}")

    # ── Best method per-segment breakdown ─────────────────────────────────
    best_name = sorted_methods[0][0]
    best_cal  = sorted_methods[0][1]
    best_b    = brier(best_cal, actual)

    print(f"\n  Per-segment breakdown — best: {best_name} (Brier={best_b:.4f})")
    print(f"  {'Segment':<22s} {'n':>4s} {'Market':>8s} {'Raw':>8s} {'Best':>8s} {'vs Mkt':>8s}")
    print(f"  {'-'*62}")
    for inn in [1, 2]:
        for ph in ["powerplay", "middle", "death"]:
            mask = (df["innings"].values == inn) & (df["phase"].values == ph)
            if mask.sum() < 3: continue
            seg = f"inn{inn}_{ph}"
            bm = brier(market_p[mask], actual[mask])
            br = brier(model_p[mask], actual[mask])
            bc = brier(best_cal[mask], actual[mask])
            win = "  ◄" if bc < bm else ""
            print(f"  {seg:<22s} {mask.sum():4d} {bm:8.4f} {br:8.4f} {bc:8.4f} {(bc/bm-1)*100:+7.1f}%{win}")
        mask_inn = df["innings"].values == inn
        bm = brier(market_p[mask_inn], actual[mask_inn])
        bc = brier(best_cal[mask_inn], actual[mask_inn])
        br = brier(model_p[mask_inn], actual[mask_inn])
        print(f"  {'INN'+str(inn)+' TOTAL':<22s} {mask_inn.sum():4d} {bm:8.4f} {br:8.4f} {bc:8.4f} {(bc/bm-1)*100:+7.1f}%")
        print()

    # ── Inn2 comparison across all methods ────────────────────────────────
    mask2 = df["innings"].values == 2
    b_mkt2 = brier(market_p[mask2], actual[mask2])
    print(f"  Inn2 comparison (main gap):")
    print(f"  {'Method':<28s} {'Brier':>8s} {'vs Mkt':>8s}")
    print(f"  {'-'*48}")
    for name, cal in sorted(methods.items(), key=lambda x: brier(x[1][mask2], actual[mask2])):
        bc2 = brier(cal[mask2], actual[mask2])
        win = "  ◄" if bc2 < b_mkt2 else ""
        print(f"  {name:<28s} {bc2:8.4f} {(bc2/b_mkt2-1)*100:+7.1f}%{win}")
    print(f"  {'Market':<28s} {b_mkt2:8.4f}")
    print(f"  {'Raw':<28s} {brier(model_p[mask2], actual[mask2]):8.4f}")

    # ── Market-fitted T interpretation ────────────────────────────────────
    print(f"\n  Interpretation:")
    T_inn1_mkt = T_mkt_inn.get("inn1", 1.0)
    T_inn2_mkt = T_mkt_inn.get("inn2", 1.0)
    for inn, T in [(1, T_inn1_mkt), (2, T_inn2_mkt)]:
        if T > 1.05:
            direction = f"soften toward 0.5 (model is too extreme, T={T:.3f})"
        elif T < 0.95:
            direction = f"sharpen toward 0/1 (model is too conservative, T={T:.3f})"
        else:
            direction = f"no correction needed (T={T:.3f} ≈ 1.0)"
        print(f"  Inn{inn}: {direction}")


if __name__ == "__main__":
    main()
