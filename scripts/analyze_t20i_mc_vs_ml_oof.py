import argparse
import joblib
import numpy as np
import pandas as pd
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).parent.parent))

from bbl_pipeline.calibration.mc_calibrator import InningsMCCalibrators, InningsPhaseCalibrators, over_to_phase
from bbl_pipeline.simulation.engine import simulate
from bbl_pipeline.simulation.state import MatchState as SimMatchState


def logloss(p, y, eps=1e-7):
    p = np.clip(p, eps, 1 - eps)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def brier(p, y):
    return (p - y) ** 2


def ece(p, y, n_bins=10):
    p = np.asarray(p)
    y = np.asarray(y)
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    idx = np.digitize(p, bins) - 1
    idx = np.clip(idx, 0, n_bins - 1)

    ece_val = 0.0
    n = len(p)
    for b in range(n_bins):
        mask = idx == b
        if not np.any(mask):
            continue
        conf = p[mask].mean()
        acc = y[mask].mean()
        ece_val += (mask.sum() / n) * abs(acc - conf)
    return ece_val


def get_phase(over):
    if over <= 6:
        return "Powerplay (1-6)"
    if over <= 15:
        return "Middle (7-15)"
    return "Death (16-20)"


def run_mc_raw_for_state(row_dict, n_simulations=300, horizon=6):
    innings = int(row_dict.get("innings", 2))

    if "overs_remaining" in row_dict:
        overs_bowled = 20 - row_dict["overs_remaining"]
        over = int(overs_bowled)
        ball = int((overs_bowled - over) * 6) + 1
    else:
        over = int(row_dict.get("over", 10))
        ball = int(row_dict.get("ball", 1))

    balls_remaining = (20 - over) * 6 - ball + 1
    balls_remaining = max(1, min(120, balls_remaining))

    overs_remaining = row_dict.get("overs_remaining", balls_remaining / 6)
    overs_bowled = 20 - overs_remaining

    if "current_score" in row_dict:
        score = int(row_dict["current_score"])
    elif "score" in row_dict:
        score = int(row_dict["score"])
    elif "total_score" in row_dict:
        score = int(row_dict["total_score"])
    elif "current_run_rate" in row_dict and overs_bowled > 0:
        score = int(row_dict["current_run_rate"] * overs_bowled)
    else:
        score = 100

    wickets = int(row_dict.get("wickets_lost", row_dict.get("wickets", row_dict.get("total_wickets", 3))))

    target = None
    if innings == 2:
        if "target_runs" in row_dict:
            target = int(row_dict["target_runs"])
        elif "target" in row_dict:
            target = int(row_dict["target"])
        elif "target_score" in row_dict:
            target = int(row_dict["target_score"])
        elif "required_run_rate" in row_dict and overs_remaining > 0:
            runs_needed = row_dict["required_run_rate"] * overs_remaining
            target = int(score + runs_needed)
        else:
            target = 160

    state = SimMatchState(
        innings=innings,
        score=score,
        wickets_lost=wickets,
        balls_remaining=balls_remaining,
        target_runs=target,
        league="t20i",
        batting_team="Team A",
        bowling_team="Team B",
    )

    result = simulate(state=state, horizon=horizon, n_simulations=n_simulations, predictor=None, apply_temp=False)
    return float(result.mean_prob)


def print_ml_oof_by_segment(results_csv):
    oof_df = pd.read_csv(results_csv)
    ml_df = oof_df[oof_df["method"] == "raw"].copy()
    seg_order = [
        "inn1_powerplay",
        "inn1_middle",
        "inn1_death",
        "inn2_powerplay",
        "inn2_middle",
        "inn2_death",
    ]
    ml_df = ml_df[ml_df["segment"].isin(seg_order)].copy()
    ml_df["segment"] = pd.Categorical(ml_df["segment"], categories=seg_order, ordered=True)
    ml_df = ml_df.sort_values("segment")

    print("\n" + "=" * 84)
    print("ML OOF (RAW) - INNINGS + PHASE")
    print("=" * 84)
    print(f"{'Segment':<18} | {'LogLoss':<10} | {'Brier':<10} | {'ECE':<10} | {'N':<9}")
    print("-" * 84)
    for _, row in ml_df.iterrows():
        print(
            f"{row['segment']:<18} | {row['logloss']:.4f}     | {row['brier']:.4f}     | "
            f"{row['ece']:.4f}     | {int(row['n_samples']):<9}"
        )


def main():
    parser = argparse.ArgumentParser(description="T20I ML OOF vs MC raw/calibrated analysis")
    parser.add_argument("--sample-size", type=int, default=1800)
    parser.add_argument("--n-sims", type=int, default=300)
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 8) - 1))
    args = parser.parse_args()

    print("Loading T20I features and model...")
    df = pd.read_parquet("data/t20_international_male_features_v1/training.parquet")
    model = joblib.load("models/t20_international_male_v1/champion_model.joblib")
    features = model.feature_names_in_ if hasattr(model, "feature_names_in_") else model.selected_features_

    print_ml_oof_by_segment("models/t20_international_male_v1/oof_calibration_results.csv")

    calibrator_path = Path("models/t20_international_male_v1/mc_calibrators_innings.pkl")
    if not calibrator_path.exists():
        raise FileNotFoundError(f"Missing innings MC calibrator: {calibrator_path}")
    mc_calibrator = InningsMCCalibrators.load(str(calibrator_path))

    phase_calibrator_path = Path("models/t20_international_male_v1/mc_calibrators_innings_phase.pkl")
    mc_phase_calibrator = None
    if phase_calibrator_path.exists():
        mc_phase_calibrator = InningsPhaseCalibrators.load(str(phase_calibrator_path))
        print(f"Loaded innings×phase MC calibrators from {phase_calibrator_path}")
    else:
        print(f"WARNING: No innings×phase calibrator found at {phase_calibrator_path}")

    if "overs_remaining" in df.columns:
        df["over"] = 20 - df["overs_remaining"].round().astype(int)
    elif "over" not in df.columns:
        df["over"] = 10

    df["phase"] = df["over"].apply(get_phase)
    sample_per_bucket = max(1, args.sample_size // 6)
    sample_df = (
        df.groupby(["innings", "phase"], group_keys=False)
        .apply(lambda x: x.sample(min(len(x), sample_per_bucket), random_state=42))
        .copy()
    )

    X_sample = sample_df[features].fillna(0)
    sample_df["ml_prob"] = model.predict_proba(X_sample)[:, 1]

    print(f"\nRunning parallel MC for {len(sample_df)} T20I states (workers={args.workers}, n_sims={args.n_sims})...")
    start = time.time()

    row_dicts = [r.to_dict() for _, r in sample_df.iterrows()]
    mc_raw = np.zeros(len(sample_df), dtype=float)

    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(run_mc_raw_for_state, row, args.n_sims, 6): i for i, row in enumerate(row_dicts)}
        done = 0
        for future in as_completed(futures):
            i = futures[future]
            try:
                mc_raw[i] = future.result()
            except Exception:
                mc_raw[i] = sample_df.iloc[i]["ml_prob"]
            done += 1
            if done % 100 == 0:
                elapsed = time.time() - start
                rate = done / max(elapsed, 1e-9)
                eta = (len(sample_df) - done) / max(rate, 1e-9)
                print(f"  [{done}/{len(sample_df)}] {rate:.1f} states/s, ETA {eta:.0f}s")

    sample_df["mc_raw_prob"] = mc_raw
    sample_df["mc_cal_prob"] = sample_df.apply(
        lambda r: mc_calibrator.calibrate(r["mc_raw_prob"], innings=int(r["innings"])),
        axis=1,
    )

    # Apply innings×phase calibrators if available
    if mc_phase_calibrator is not None:
        sample_df["mc_phase_cal_prob"] = sample_df.apply(
            lambda r: mc_phase_calibrator.calibrate(
                r["mc_raw_prob"],
                innings=int(r["innings"]),
                phase=over_to_phase(int(r["over"])),
            ),
            axis=1,
        )

    print("\n" + "=" * 84)
    print("MC RAW vs MC INNINGS-CALIBRATED (ACTUAL OUTCOME METRICS)")
    print("=" * 84)

    phase_order = ["Powerplay (1-6)", "Middle (7-15)", "Death (16-20)"]
    for innings in [1, 2]:
        for phase in phase_order:
            sub = sample_df[(sample_df["innings"] == innings) & (sample_df["phase"] == phase)]
            if len(sub) < 10:
                continue
            y_true = sub["is_winner"].values
            raw_p = sub["mc_raw_prob"].values
            cal_p = sub["mc_cal_prob"].values

            print(f"\nInnings {innings} - {phase} (N={len(sub)})")
            print(f"{'Metric':<10} | {'MC Raw':<10} | {'MC Inn-Cal':<12} | {'Delta':<10}")
            print("-" * 56)
            raw_ll = logloss(raw_p, y_true).mean()
            cal_ll = logloss(cal_p, y_true).mean()
            raw_br = brier(raw_p, y_true).mean()
            cal_br = brier(cal_p, y_true).mean()
            raw_ec = ece(raw_p, y_true)
            cal_ec = ece(cal_p, y_true)
            print(f"{'LogLoss':<10} | {raw_ll:.4f}     | {cal_ll:.4f}       | {cal_ll - raw_ll:+.4f}")
            print(f"{'Brier':<10} | {raw_br:.4f}     | {cal_br:.4f}       | {cal_br - raw_br:+.4f}")
            print(f"{'ECE':<10} | {raw_ec:.4f}     | {cal_ec:.4f}       | {cal_ec - raw_ec:+.4f}")

    print("\n" + "=" * 84)
    print("ML RAW vs MC INNINGS-CALIBRATED (ACTUAL OUTCOME METRICS)")
    print("=" * 84)

    for innings in [1, 2]:
        for phase in phase_order:
            sub = sample_df[(sample_df["innings"] == innings) & (sample_df["phase"] == phase)]
            if len(sub) < 10:
                continue
            y_true = sub["is_winner"].values
            ml_p = sub["ml_prob"].values
            mc_cal_p = sub["mc_cal_prob"].values

            print(f"\nInnings {innings} - {phase} (N={len(sub)})")
            print(f"{'Metric':<10} | {'ML Raw':<10} | {'MC Inn-Cal':<12} | {'Delta':<10}")
            print("-" * 56)
            ml_ll = logloss(ml_p, y_true).mean()
            mc_cal_ll = logloss(mc_cal_p, y_true).mean()
            ml_br = brier(ml_p, y_true).mean()
            mc_cal_br = brier(mc_cal_p, y_true).mean()
            ml_ec = ece(ml_p, y_true)
            mc_cal_ec = ece(mc_cal_p, y_true)
            print(f"{'LogLoss':<10} | {ml_ll:.4f}     | {mc_cal_ll:.4f}       | {mc_cal_ll - ml_ll:+.4f}")
            print(f"{'Brier':<10} | {ml_br:.4f}     | {mc_cal_br:.4f}       | {mc_cal_br - ml_br:+.4f}")
            print(f"{'ECE':<10} | {ml_ec:.4f}     | {mc_cal_ec:.4f}       | {mc_cal_ec - ml_ec:+.4f}")

    # ── MC Inn-Cal vs MC Phase-Cal ─────────────────────────────────────
    if mc_phase_calibrator is not None and "mc_phase_cal_prob" in sample_df.columns:
        print("\n" + "=" * 84)
        print("MC INNINGS-CAL vs MC PHASE-CAL  (ACTUAL OUTCOME METRICS)")
        print("=" * 84)

        for innings in [1, 2]:
            for phase in phase_order:
                sub = sample_df[(sample_df["innings"] == innings) & (sample_df["phase"] == phase)]
                if len(sub) < 10:
                    continue
                y_true = sub["is_winner"].values
                inn_p = sub["mc_cal_prob"].values
                ph_p = sub["mc_phase_cal_prob"].values

                print(f"\nInnings {innings} - {phase} (N={len(sub)})")
                print(f"{'Metric':<10} | {'MC Inn-Cal':<12} | {'MC Phase-Cal':<14} | {'Delta':<10}")
                print("-" * 60)
                inn_ll = logloss(inn_p, y_true).mean()
                ph_ll = logloss(ph_p, y_true).mean()
                inn_br = brier(inn_p, y_true).mean()
                ph_br = brier(ph_p, y_true).mean()
                inn_ec = ece(inn_p, y_true)
                ph_ec = ece(ph_p, y_true)
                print(f"{'LogLoss':<10} | {inn_ll:.4f}       | {ph_ll:.4f}         | {ph_ll - inn_ll:+.4f}")
                print(f"{'Brier':<10} | {inn_br:.4f}       | {ph_br:.4f}         | {ph_br - inn_br:+.4f}")
                print(f"{'ECE':<10} | {inn_ec:.4f}       | {ph_ec:.4f}         | {ph_ec - inn_ec:+.4f}")

    # ── ML RAW vs MC PHASE-CAL ─────────────────────────────────────────
    if mc_phase_calibrator is not None and "mc_phase_cal_prob" in sample_df.columns:
        print("\n" + "=" * 84)
        print("ML RAW vs MC PHASE-CALIBRATED  (ACTUAL OUTCOME METRICS)")
        print("=" * 84)

        for innings in [1, 2]:
            for phase in phase_order:
                sub = sample_df[(sample_df["innings"] == innings) & (sample_df["phase"] == phase)]
                if len(sub) < 10:
                    continue
                y_true = sub["is_winner"].values
                ml_p = sub["ml_prob"].values
                ph_p = sub["mc_phase_cal_prob"].values

                print(f"\nInnings {innings} - {phase} (N={len(sub)})")
                print(f"{'Metric':<10} | {'ML Raw':<10} | {'MC Phase-Cal':<14} | {'Delta':<10}")
                print("-" * 60)
                ml_ll = logloss(ml_p, y_true).mean()
                ph_ll = logloss(ph_p, y_true).mean()
                ml_br = brier(ml_p, y_true).mean()
                ph_br = brier(ph_p, y_true).mean()
                ml_ec = ece(ml_p, y_true)
                ph_ec = ece(ph_p, y_true)
                print(f"{'LogLoss':<10} | {ml_ll:.4f}     | {ph_ll:.4f}         | {ph_ll - ml_ll:+.4f}")
                print(f"{'Brier':<10} | {ml_br:.4f}     | {ph_br:.4f}         | {ph_br - ml_br:+.4f}")
                print(f"{'ECE':<10} | {ml_ec:.4f}     | {ph_ec:.4f}         | {ph_ec - ml_ec:+.4f}")

    print("\n" + "=" * 84)
    print("GAP > 10% ANALYSIS (ML vs MC INNINGS-CALIBRATED)")
    print("=" * 84)

    sample_df["gap"] = np.abs(sample_df["ml_prob"] - sample_df["mc_cal_prob"])
    gap_df = sample_df[sample_df["gap"] > 0.10].copy()
    print(f"High-gap states: {len(gap_df)} / {len(sample_df)} ({len(gap_df) / len(sample_df) * 100:.1f}%)")

    if len(gap_df) > 0:
        gap_df["ml_err"] = np.abs(gap_df["ml_prob"] - gap_df["is_winner"])
        gap_df["mc_err"] = np.abs(gap_df["mc_cal_prob"] - gap_df["is_winner"])

        ml_better = int((gap_df["ml_err"] < gap_df["mc_err"]).sum())
        mc_better = int((gap_df["mc_err"] < gap_df["ml_err"]).sum())
        ties = len(gap_df) - ml_better - mc_better

        print(f"ML closer to reality: {ml_better} ({ml_better / len(gap_df) * 100:.1f}%)")
        print(f"MC closer to reality: {mc_better} ({mc_better / len(gap_df) * 100:.1f}%)")
        print(f"Ties: {ties} ({ties / len(gap_df) * 100:.1f}%)")

        print("\nHigh-gap distribution by innings + phase:")
        phase_counts = gap_df.groupby(["innings", "phase"]).size().sort_index()
        for (inn, ph), count in phase_counts.items():
            print(f"  Innings {inn} - {ph}: {count} ({count / len(gap_df) * 100:.1f}%)")

    # ══════════════════════════════════════════════════════════════════════
    #  LOGIT BLEND ANALYSIS  —  ML × MC Phase-Cal
    # ══════════════════════════════════════════════════════════════════════

    # Pick best MC: use phase-cal if available, else innings-cal
    if "mc_phase_cal_prob" in sample_df.columns:
        mc_col = "mc_phase_cal_prob"
        mc_label = "MC Phase-Cal"
    else:
        mc_col = "mc_cal_prob"
        mc_label = "MC Inn-Cal"

    _EPS = 1e-7

    def safe_logit(p):
        p = np.clip(p, _EPS, 1 - _EPS)
        return np.log(p / (1 - p))

    def sigmoid(x):
        return 1.0 / (1.0 + np.exp(-x))

    def logit_blend(ml_p, mc_p, w):
        """Blend in logit space: w * logit(ML) + (1-w) * logit(MC) → sigmoid."""
        return sigmoid(w * safe_logit(ml_p) + (1 - w) * safe_logit(mc_p))

    ml_arr = sample_df["ml_prob"].values.astype(float)
    mc_arr = sample_df[mc_col].values.astype(float)
    y_arr = sample_df["is_winner"].values.astype(float)

    # ── 1. Global sweep of static weights ──────────────────────────────
    print("\n" + "=" * 100)
    print(f"LOGIT BLEND SWEEP  —  ML × {mc_label}")
    print("=" * 100)

    static_weights = [0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95, 1.00]

    print(f"\n{'w (ML)':<8} | {'LogLoss':>9} | {'Brier':>9} | {'ECE':>9} | {'vs ML-raw LL':>14} | {'vs ML-raw Br':>14} | {'vs ML-raw ECE':>14}")
    print("-" * 100)

    ml_ll_all = logloss(ml_arr, y_arr).mean()
    ml_br_all = brier(ml_arr, y_arr).mean()
    ml_ec_all = ece(ml_arr, y_arr)

    best_ll_w, best_ll = 1.0, ml_ll_all
    best_br_w, best_br = 1.0, ml_br_all
    best_ec_w, best_ec = 1.0, ml_ec_all

    for w in static_weights:
        bp = logit_blend(ml_arr, mc_arr, w)
        bl = logloss(bp, y_arr).mean()
        bb = brier(bp, y_arr).mean()
        be = ece(bp, y_arr)
        tag = " ← ML-only" if w == 1.0 else ""
        print(
            f"{w:<8.2f} | {bl:>9.4f} | {bb:>9.4f} | {be:>9.4f} | "
            f"{bl - ml_ll_all:>+14.4f} | {bb - ml_br_all:>+14.4f} | {be - ml_ec_all:>+14.4f}{tag}"
        )
        if bl < best_ll:
            best_ll_w, best_ll = w, bl
        if bb < best_br:
            best_br_w, best_br = w, bb
        if be < best_ec:
            best_ec_w, best_ec = w, be

    print(f"\nBest LogLoss: w={best_ll_w:.2f} ({best_ll:.4f}, Δ={best_ll - ml_ll_all:+.4f})")
    print(f"Best Brier:   w={best_br_w:.2f} ({best_br:.4f}, Δ={best_br - ml_br_all:+.4f})")
    print(f"Best ECE:     w={best_ec_w:.2f} ({best_ec:.4f}, Δ={best_ec - ml_ec_all:+.4f})")

    # ── 2. Gap-adaptive weight ─────────────────────────────────────────
    print("\n" + "=" * 100)
    print("GAP-ADAPTIVE LOGIT BLEND  (w = base + α·|ML−MC|, clamped [0.55, 0.90])")
    print("=" * 100)

    gap_arr = np.abs(ml_arr - mc_arr)
    adapt_configs = [
        (0.60, 0.5),
        (0.60, 0.8),
        (0.65, 0.5),
        (0.65, 0.7),
        (0.70, 0.5),
        (0.70, 0.8),
        (0.75, 0.5),
    ]

    print(f"\n{'base':>5} {'α':>5} | {'Avg w':>7} | {'LogLoss':>9} | {'Brier':>9} | {'ECE':>9} | {'vs ML LL':>10} | {'vs ML Br':>10} | {'vs ML ECE':>10}")
    print("-" * 100)

    for base_w, alpha in adapt_configs:
        w_arr = np.clip(base_w + alpha * gap_arr, 0.55, 0.90)
        bp = sigmoid(w_arr * safe_logit(ml_arr) + (1 - w_arr) * safe_logit(mc_arr))
        bl = logloss(bp, y_arr).mean()
        bb = brier(bp, y_arr).mean()
        be = ece(bp, y_arr)
        print(
            f"{base_w:>5.2f} {alpha:>5.1f} | {w_arr.mean():>7.3f} | {bl:>9.4f} | {bb:>9.4f} | {be:>9.4f} | "
            f"{bl - ml_ll_all:>+10.4f} | {bb - ml_br_all:>+10.4f} | {be - ml_ec_all:>+10.4f}"
        )

    # ── 3. Best static weight — segment breakdown ─────────────────────
    # Use best-Brier weight for the detailed breakdown
    best_w = best_br_w
    print(f"\n{'='*100}")
    print(f"LOGIT BLEND (w={best_w:.2f}) vs ML RAW  —  BY INNINGS × PHASE")
    print(f"{'='*100}")

    bp_all = logit_blend(ml_arr, mc_arr, best_w)
    sample_df["blend_prob"] = bp_all

    print(f"\n{'Segment':<22} | {'N':>5} | {'ML LL':>8} {'Bl LL':>8} {'Δ':>8} | {'ML Br':>8} {'Bl Br':>8} {'Δ':>8} | {'ML ECE':>8} {'Bl ECE':>8} {'Δ':>8}")
    print("-" * 120)

    ml_wins_ll = 0
    blend_wins_ll = 0
    ml_wins_br = 0
    blend_wins_br = 0
    ml_wins_ec = 0
    blend_wins_ec = 0

    for innings in [1, 2]:
        for phase in phase_order:
            sub = sample_df[(sample_df["innings"] == innings) & (sample_df["phase"] == phase)]
            if len(sub) < 10:
                continue
            y_true = sub["is_winner"].values
            ml_p = sub["ml_prob"].values
            bl_p = sub["blend_prob"].values

            s_ml_ll = logloss(ml_p, y_true).mean()
            s_bl_ll = logloss(bl_p, y_true).mean()
            s_ml_br = brier(ml_p, y_true).mean()
            s_bl_br = brier(bl_p, y_true).mean()
            s_ml_ec = ece(ml_p, y_true)
            s_bl_ec = ece(bl_p, y_true)

            seg = f"Inn{innings} {phase}"
            print(
                f"{seg:<22} | {len(sub):>5} | "
                f"{s_ml_ll:>8.4f} {s_bl_ll:>8.4f} {s_bl_ll - s_ml_ll:>+8.4f} | "
                f"{s_ml_br:>8.4f} {s_bl_br:>8.4f} {s_bl_br - s_ml_br:>+8.4f} | "
                f"{s_ml_ec:>8.4f} {s_bl_ec:>8.4f} {s_bl_ec - s_ml_ec:>+8.4f}"
            )

            if s_bl_ll < s_ml_ll:
                blend_wins_ll += 1
            else:
                ml_wins_ll += 1
            if s_bl_br < s_ml_br:
                blend_wins_br += 1
            else:
                ml_wins_br += 1
            if s_bl_ec < s_ml_ec:
                blend_wins_ec += 1
            else:
                ml_wins_ec += 1

    print(f"\nSegment wins — LogLoss: ML {ml_wins_ll}, Blend {blend_wins_ll} | "
          f"Brier: ML {ml_wins_br}, Blend {blend_wins_br} | "
          f"ECE: ML {ml_wins_ec}, Blend {blend_wins_ec}")

    # ── 4. Probability-space blend comparison (sanity check) ───────────
    print(f"\n{'='*100}")
    print("PROB-SPACE vs LOGIT-SPACE BLEND (w=0.80)")
    print(f"{'='*100}")

    w_cmp = 0.80
    prob_blend = w_cmp * ml_arr + (1 - w_cmp) * mc_arr
    logit_bl = logit_blend(ml_arr, mc_arr, w_cmp)

    for label, bp in [("Prob-space ", prob_blend), ("Logit-space", logit_bl), ("ML raw     ", ml_arr)]:
        bl = logloss(bp, y_arr).mean()
        bb = brier(bp, y_arr).mean()
        be = ece(bp, y_arr)
        print(f"  {label}  LL={bl:.4f}  Brier={bb:.4f}  ECE={be:.4f}")

    # ── 5. Summary verdict ─────────────────────────────────────────────
    print(f"\n{'='*100}")
    print("VERDICT: Does blending add value over ML-raw?")
    print(f"{'='*100}")

    best_static_bp = logit_blend(ml_arr, mc_arr, best_br_w)
    best_static_ll = logloss(best_static_bp, y_arr).mean()
    best_static_br = brier(best_static_bp, y_arr).mean()
    best_static_ec = ece(best_static_bp, y_arr)

    print(f"  ML Raw:           LL={ml_ll_all:.4f}  Brier={ml_br_all:.4f}  ECE={ml_ec_all:.4f}")
    print(f"  Best Blend w={best_br_w:.2f}: LL={best_static_ll:.4f}  Brier={best_static_br:.4f}  ECE={best_static_ec:.4f}")
    print(f"  Delta:            LL={best_static_ll - ml_ll_all:+.4f}  Brier={best_static_br - ml_br_all:+.4f}  ECE={best_static_ec - ml_ec_all:+.4f}")

    if best_static_br < ml_br_all and best_static_ll < ml_ll_all:
        print("\n  ✓ Blend IMPROVES both LogLoss and Brier over ML-raw")
    elif best_static_br < ml_br_all:
        print("\n  ~ Blend improves Brier but not LogLoss — marginal value")
    elif best_static_ec < ml_ec_all:
        print("\n  ~ Blend improves ECE only — post-hoc calibration (isotonic) likely does this better")
    else:
        print("\n  ✗ Blend does NOT improve over ML-raw — MC adds no information ML doesn't have")

    # ══════════════════════════════════════════════════════════════════════
    #  AGREEMENT / DISAGREEMENT ANALYSIS  —  What happens when ML & MC
    #  are close vs far apart?
    # ══════════════════════════════════════════════════════════════════════

    print(f"\n{'='*110}")
    print(f"AGREEMENT / DISAGREEMENT ANALYSIS  —  ML vs {mc_label}")
    print(f"{'='*110}")

    gap_arr = np.abs(ml_arr - mc_arr)
    ml_err = np.abs(ml_arr - y_arr)
    mc_err = np.abs(mc_arr - y_arr)

    # ── 6a. Metrics by gap bucket ──────────────────────────────────────
    gap_thresholds = [0.05, 0.10, 0.15, 0.20, 0.30]

    print(f"\n{'Gap Bucket':<18} | {'N':>5} {'%':>6} | {'ML LL':>8} {'MC LL':>8} {'Δ':>8} | "
          f"{'ML Br':>8} {'MC Br':>8} {'Δ':>8} | {'ML ECE':>8} {'MC ECE':>8} {'Δ':>8}")
    print("-" * 120)

    edges = [0.0] + gap_thresholds + [1.0]
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (gap_arr >= lo) & (gap_arr < hi)
        n = mask.sum()
        if n < 20:
            continue
        pct = n / len(gap_arr) * 100
        s_ml_ll = logloss(ml_arr[mask], y_arr[mask]).mean()
        s_mc_ll = logloss(mc_arr[mask], y_arr[mask]).mean()
        s_ml_br = brier(ml_arr[mask], y_arr[mask]).mean()
        s_mc_br = brier(mc_arr[mask], y_arr[mask]).mean()
        s_ml_ec = ece(ml_arr[mask], y_arr[mask])
        s_mc_ec = ece(mc_arr[mask], y_arr[mask])

        label = f"|ML-MC| [{lo:.2f}, {hi:.2f})"
        print(
            f"{label:<18} | {n:>5} {pct:>5.1f}% | "
            f"{s_ml_ll:>8.4f} {s_mc_ll:>8.4f} {s_mc_ll - s_ml_ll:>+8.4f} | "
            f"{s_ml_br:>8.4f} {s_mc_br:>8.4f} {s_mc_br - s_ml_br:>+8.4f} | "
            f"{s_ml_ec:>8.4f} {s_mc_ec:>8.4f} {s_mc_ec - s_ml_ec:>+8.4f}"
        )

    # ── 6b. Who's right when they agree? ──────────────────────────────
    print(f"\n{'='*110}")
    print("WHEN THEY AGREE (|ML-MC| < 0.05):  How accurate is the consensus?")
    print(f"{'='*110}")

    close_mask = gap_arr < 0.05
    if close_mask.sum() > 20:
        close_ml = ml_arr[close_mask]
        close_mc = mc_arr[close_mask]
        close_y = y_arr[close_mask]
        close_avg = (close_ml + close_mc) / 2  # simple average when close

        print(f"\n  N = {close_mask.sum()} ({close_mask.sum()/len(gap_arr)*100:.1f}% of all states)")
        print(f"\n  {'Model':<14} | {'LogLoss':>9} | {'Brier':>9} | {'ECE':>9}")
        print(f"  {'-'*50}")
        for lbl, p in [("ML", close_ml), ("MC", close_mc), ("Average", close_avg)]:
            ll = logloss(p, close_y).mean()
            br = brier(p, close_y).mean()
            ec = ece(p, close_y)
            print(f"  {lbl:<14} | {ll:>9.4f} | {br:>9.4f} | {ec:>9.4f}")

        # Breakdown by innings*phase when close
        close_df = sample_df[close_mask].copy()
        close_df["mc_p"] = close_mc
        print(f"\n  Phase distribution when close:")
        for innings in [1, 2]:
            for phase in phase_order:
                sub = close_df[(close_df["innings"] == innings) & (close_df["phase"] == phase)]
                if len(sub) > 0:
                    pct = len(sub) / len(close_df) * 100
                    print(f"    Inn{innings} {phase}: {len(sub)} ({pct:.1f}%)")

    # ── 6c. Who's right when they disagree? ───────────────────────────
    print(f"\n{'='*110}")
    print("WHEN THEY DISAGREE (|ML-MC| > 0.15):  Who should you trust?")
    print(f"{'='*110}")

    far_mask = gap_arr > 0.15
    if far_mask.sum() > 20:
        far_ml = ml_arr[far_mask]
        far_mc = mc_arr[far_mask]
        far_y = y_arr[far_mask]

        print(f"\n  N = {far_mask.sum()} ({far_mask.sum()/len(gap_arr)*100:.1f}% of all states)")

        # Who's closer per-sample?
        ml_closer = (np.abs(far_ml - far_y) < np.abs(far_mc - far_y)).sum()
        mc_closer = (np.abs(far_mc - far_y) < np.abs(far_ml - far_y)).sum()
        tied = far_mask.sum() - ml_closer - mc_closer
        print(f"  ML closer to outcome: {ml_closer} ({ml_closer/far_mask.sum()*100:.1f}%)")
        print(f"  MC closer to outcome: {mc_closer} ({mc_closer/far_mask.sum()*100:.1f}%)")

        print(f"\n  {'Model':<14} | {'LogLoss':>9} | {'Brier':>9} | {'ECE':>9}")
        print(f"  {'-'*50}")
        for lbl, p in [("ML", far_ml), ("MC", far_mc)]:
            ll = logloss(p, far_y).mean()
            br = brier(p, far_y).mean()
            ec = ece(p, far_y)
            print(f"  {lbl:<14} | {ll:>9.4f} | {br:>9.4f} | {ec:>9.4f}")

        # Directional analysis: which direction does MC err?
        # When ML > MC (ML more confident in batting team), who's right?
        ml_higher = far_ml > far_mc
        ml_lower = ~ml_higher

        for direction, mask_d, desc in [
            ("ML > MC", ml_higher, "ML more optimistic about batting team"),
            ("ML < MC", ml_lower, "MC more optimistic about batting team"),
        ]:
            d_mask = far_mask.copy()
            d_idx = np.where(far_mask)[0]
            d_sub = d_idx[mask_d[: len(d_idx)] if len(mask_d) >= len(d_idx) else mask_d]

            # Recompute using original arrays
            cond = far_mask & (ml_arr > mc_arr) if direction == "ML > MC" else far_mask & (ml_arr <= mc_arr)
            n_d = cond.sum()
            if n_d < 10:
                continue
            ml_d = ml_arr[cond]
            mc_d = mc_arr[cond]
            y_d = y_arr[cond]

            ml_win = (np.abs(ml_d - y_d) < np.abs(mc_d - y_d)).sum()
            print(f"\n  {direction} ({desc}): N={n_d}")
            print(f"    ML closer: {ml_win} ({ml_win/n_d*100:.1f}%)  |  MC closer: {n_d - ml_win} ({(n_d-ml_win)/n_d*100:.1f}%)")
            print(f"    ML mean pred: {ml_d.mean():.3f}  |  MC mean pred: {mc_d.mean():.3f}  |  Actual win rate: {y_d.mean():.3f}")

        # Phase breakdown when far apart
        far_df = sample_df[far_mask].copy()
        print(f"\n  Phase distribution when far apart:")
        for innings in [1, 2]:
            for phase in phase_order:
                sub = far_df[(far_df["innings"] == innings) & (far_df["phase"] == phase)]
                if len(sub) > 0:
                    pct = len(sub) / len(far_df) * 100
                    # Who wins in this segment?
                    s_ml_err = np.abs(sub["ml_prob"].values - sub["is_winner"].values)
                    s_mc_err = np.abs(mc_arr[far_mask][(far_df["innings"] == innings).values & (far_df["phase"] == phase).values] - sub["is_winner"].values)
                    ml_w = (s_ml_err < s_mc_err).sum()
                    print(f"    Inn{innings} {phase}: {len(sub)} ({pct:.1f}%)  ML wins {ml_w}/{len(sub)} ({ml_w/len(sub)*100:.0f}%)")

    # ── 6d. Confidence-conditioned analysis ───────────────────────────
    print(f"\n{'='*110}")
    print("CONFIDENCE-CONDITIONED:  Does agreement at extremes vs near 0.5 matter?")
    print(f"{'='*110}")

    # Split by whether the consensus (average) is extreme or uncertain
    avg_p = (ml_arr + mc_arr) / 2
    confidence = np.abs(avg_p - 0.5)  # 0 = maximally uncertain, 0.5 = maximally confident

    conf_bins = [(0.0, 0.10, "Uncertain (avg ≈ 0.5)"),
                 (0.10, 0.25, "Moderate"),
                 (0.25, 0.40, "Confident"),
                 (0.40, 0.50, "Very confident (avg near 0/1)")]

    print(f"\n  {'Confidence Zone':<30} | {'N':>5} | {'|ML-MC|':>8} | {'ML LL':>8} {'MC LL':>8} {'Δ':>8} | {'ML Br':>8} {'MC Br':>8} {'Δ':>8}")
    print(f"  {'-'*110}")

    for lo, hi, label in conf_bins:
        mask = (confidence >= lo) & (confidence < hi)
        n = mask.sum()
        if n < 20:
            continue
        avg_gap = gap_arr[mask].mean()
        s_ml_ll = logloss(ml_arr[mask], y_arr[mask]).mean()
        s_mc_ll = logloss(mc_arr[mask], y_arr[mask]).mean()
        s_ml_br = brier(ml_arr[mask], y_arr[mask]).mean()
        s_mc_br = brier(mc_arr[mask], y_arr[mask]).mean()
        print(
            f"  {label:<30} | {n:>5} | {avg_gap:>8.4f} | "
            f"{s_ml_ll:>8.4f} {s_mc_ll:>8.4f} {s_mc_ll - s_ml_ll:>+8.4f} | "
            f"{s_ml_br:>8.4f} {s_mc_br:>8.4f} {s_mc_br - s_ml_br:>+8.4f}"
        )


if __name__ == "__main__":
    import os

    main()
