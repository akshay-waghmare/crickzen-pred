"""Detailed T-analysis report for ipl_betx21_full_market_2026.parquet"""
import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar
from scipy.special import expit, logit

df = pd.read_parquet("data/ipl_betx21_full_market_2026.parquet")

def apply_T(p, T):
    return np.clip(expit(logit(np.clip(p, 0.01, 0.99)) / T), 0.01, 0.99)

def phase_label(over, innings):
    if innings == 1:
        if over <= 6:  return "Inn1 PP"
        if over <= 15: return "Inn1 Mid"
        return "Inn1 Death"
    else:
        if over <= 6:  return "Inn2 PP"
        if over <= 15: return "Inn2 Mid"
        return "Inn2 Death"

df["phase"] = df.apply(lambda r: phase_label(r["over"], r["innings"]), axis=1)

p = df["cal_p_inn1"].values
y = df["actual_inn1_wins"].values
m = df["market_p_inn1"].values

def opt_T(pv, yv, lo=0.20, hi=3.0):
    r = minimize_scalar(lambda T: np.mean((apply_T(pv, T) - yv)**2),
                        bounds=(lo, hi), method="bounded")
    return r.x, r.fun

# ── 0. KEY BASELINES ──────────────────────────────────────────────────────────
market_brier_actual = float(np.mean((m - y)**2))
model_brier_actual  = float(np.mean((p - y)**2))
model_brier_market  = float(np.mean((p - m)**2))

print("=" * 70)
print("0. KEY BASELINES (T=1.0, 580 rows, 16 CS matches)")
print("=" * 70)
print(f"  Market Brier vs ACTUAL  : {market_brier_actual:.4f}")
print(f"  Model  Brier vs ACTUAL  : {model_brier_actual:.4f}  (diff: {model_brier_actual - market_brier_actual:+.4f})")
print(f"  Model  Brier vs MARKET  : {model_brier_market:.4f}")
print()
print("  Interpretation:")
print(f"  The MARKET is {abs(model_brier_actual - market_brier_actual):.4f} Brier points "
      f"{'BETTER' if market_brier_actual < model_brier_actual else 'WORSE'} than the model at T=1.")
print("  T_opt_market > 1 means: to MATCH market prices the model must be SOFTENED")
print("  (market is less extreme / more cautious than the calibrated model)")

# ── 1. OVERALL T SWEEP 0.30-1.50 ─────────────────────────────────────────────
T_vals = np.round(np.concatenate([np.arange(0.30, 1.01, 0.05),
                                   np.arange(1.10, 1.51, 0.10)]), 2)
print()
print("=" * 70)
print("1. OVERALL T SWEEP (0.30 to 1.50)")
print("=" * 70)
print(f"{'T':>6} | {'Brier_vs_ACTUAL':>15} | {'delta_vs_T1':>12} | {'Brier_vs_MARKET':>15} | {'mkt_delta':>10}")
print("-" * 70)
base_act = float(np.mean((p - y)**2))
for T in T_vals:
    pT = apply_T(p, T)
    ba = float(np.mean((pT - y)**2))
    bm = float(np.mean((pT - m)**2))
    mark = " <-- T=1.0" if abs(T - 1.0) < 0.001 else ""
    print(f"  {T:4.2f} | {ba:15.4f} | {ba - base_act:+12.4f} | {bm:15.4f} |{mark}")
T_opt_all, brier_opt_all = opt_T(p, y)
T_opt_mkt, brier_opt_mkt = opt_T(p, m, lo=0.5, hi=5.0)
print(f"\n  Optimal T vs actual  : T={T_opt_all:.3f}  Brier={brier_opt_all:.4f}")
print(f"  Optimal T vs market  : T={T_opt_mkt:.3f}  Brier={brier_opt_mkt:.4f}")
print(f"  Market Brier vs actual (fixed baseline): {market_brier_actual:.4f}")

# ── 2. PER-SEGMENT FULL TABLE ─────────────────────────────────────────────────
print()
print("=" * 70)
print("2. PER-SEGMENT FULL TABLE")
print("=" * 70)
segments = ["Overall"] + sorted(df["phase"].unique().tolist())
hdr = (f"{'Segment':<12} {'n':>5} | "
       f"{'Act@T1':>8} {'MktAct':>8} {'diff':>7} | "
       f"{'T_opt':>6} {'Act@opt':>8} {'gain':>7} | "
       f"{'Mkt@T1':>8} {'T_opt_m':>7} {'Mkt@opt':>8}")
print(hdr)
print("-" * len(hdr))
seg_results = []
for seg in segments:
    sub = df if seg == "Overall" else df[df["phase"] == seg]
    pv = sub["cal_p_inn1"].values
    yv = sub["actual_inn1_wins"].values
    mv = sub["market_p_inn1"].values
    n  = len(pv)
    act_t1 = float(np.mean((pv - yv)**2))
    mkt_t1 = float(np.mean((pv - mv)**2))
    mkt_act= float(np.mean((mv - yv)**2))  # market vs actual (baseline)
    T_oa, b_oa = opt_T(pv, yv)
    T_om, b_om = opt_T(pv, mv, lo=0.5, hi=5.0)
    seg_results.append(dict(seg=seg, n=n,
                            act_t1=act_t1, mkt_act=mkt_act, diff=act_t1 - mkt_act,
                            T_oa=T_oa, b_oa=b_oa,
                            mkt_t1=mkt_t1, T_om=T_om, b_om=b_om))
    print(f"{seg:<12} {n:>5} | "
          f"{act_t1:8.4f} {mkt_act:8.4f} {act_t1 - mkt_act:+7.4f} | "
          f"{T_oa:6.3f} {b_oa:8.4f} {b_oa - act_t1:+7.4f} | "
          f"{mkt_t1:8.4f} {T_om:7.3f} {b_om:8.4f}")

# ── 3. COMBINED SEGMENT-SPECIFIC T ───────────────────────────────────────────
print()
print("=" * 70)
print("3. COMBINED SEGMENT-SPECIFIC T (apply each segment's T_opt independently)")
print("=" * 70)
# Build per-row calibrated p using each segment's optimal T
p_combined = df["cal_p_inn1"].copy().values.astype(float)
for r in seg_results:
    if r["seg"] == "Overall":
        continue
    mask = df["phase"] == r["seg"]
    p_combined[mask.values] = apply_T(df.loc[mask, "cal_p_inn1"].values, r["T_oa"])

brier_combined_act = float(np.mean((p_combined - y)**2))
brier_combined_mkt = float(np.mean((p_combined - m)**2))

print(f"  Combined segment T_opt -> Overall Brier vs ACTUAL : {brier_combined_act:.4f}")
print(f"  Combined segment T_opt -> Overall Brier vs MARKET : {brier_combined_mkt:.4f}")
print(f"  Baseline T=1.0          -> Overall Brier vs ACTUAL : {model_brier_actual:.4f}")
print(f"  Optimal single T        -> Overall Brier vs ACTUAL : {brier_opt_all:.4f}")
print(f"  Market Brier vs ACTUAL  -> {market_brier_actual:.4f}")
print()
print("  Per-segment T used:")
for r in seg_results:
    if r["seg"] != "Overall":
        print(f"    {r['seg']:<12} T={r['T_oa']:.3f}")

# ── 4. PER-MATCH BREAKDOWN ────────────────────────────────────────────────────
print()
print("=" * 70)
print("4. PER-MATCH BREAKDOWN — model vs market (T=1.0 and T_opt=0.767)")
print("=" * 70)

T_overall_opt = T_opt_all
matches = df.groupby("cs_match_id")

mkt_beats_model = 0
model_beats_mkt = 0
mkt_beats_model_opt = 0
model_beats_mkt_opt = 0

print(f"{'CS_match':<10} {'Inn1_team':<28} {'Inn2_team':<28} {'W':<1} | "
      f"{'n':>4} | "
      f"{'Mkt_act':>8} {'Mdl_act':>8} {'Mdl-Mkt':>8} | "
      f"{'MdlOpt_act':>10} {'MdlO-Mkt':>9}")
print("-" * 115)
for mid, grp in sorted(matches, key=lambda x: x[0]):
    pv = grp["cal_p_inn1"].values
    yv = grp["actual_inn1_wins"].values
    mv = grp["market_p_inn1"].values
    inn1 = grp["inn1_team"].iloc[0][:26]
    inn2 = grp["inn2_team"].iloc[0][:26]
    w = "1" if grp["actual_inn1_wins"].iloc[0] > 0.5 else "2"
    n = len(pv)
    mkt_b  = float(np.mean((mv - yv)**2))
    mdl_b  = float(np.mean((pv - yv)**2))
    pT_opt = apply_T(pv, T_overall_opt)
    mdl_bopt = float(np.mean((pT_opt - yv)**2))
    diff   = mdl_b  - mkt_b
    diff_o = mdl_bopt - mkt_b
    beat = "MODEL" if mdl_b < mkt_b else "MKT"
    beat_o= "MODEL" if mdl_bopt < mkt_b else "MKT"
    if mdl_b < mkt_b:   model_beats_mkt += 1
    else:                mkt_beats_model += 1
    if mdl_bopt < mkt_b: model_beats_mkt_opt += 1
    else:                mkt_beats_model_opt += 1
    print(f"{mid:<10} {inn1:<28} {inn2:<28} {w} | "
          f"{n:>4} | "
          f"{mkt_b:8.4f} {mdl_b:8.4f} {diff:+8.4f} | "
          f"{mdl_bopt:10.4f} {diff_o:+9.4f}  [{beat_o}]")

print()
print(f"  At T=1.0:  Model beats market in {model_beats_mkt}/16 matches  "
      f"  Market beats model in {mkt_beats_model}/16")
print(f"  At T_opt:  Model beats market in {model_beats_mkt_opt}/16 matches  "
      f"  Market beats model in {mkt_beats_model_opt}/16")
print()
print("DONE")
