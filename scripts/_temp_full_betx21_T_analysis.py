"""
Full pipeline: betx21 IPL 2026 - market vs model T-analysis
============================================================
Steps:
  1. Parse ALL betx21 scores files -> IPL-only match info dict
  2. Map betx21 event IDs -> Cricsheet match IDs
  3. Extract end-of-over market probabilities from odds files
  4. Train v7 model (<=2024 train, 2025 per-over isotonic cal, 2026 predict)
  5. Merge market odds + model predictions
  6. Find optimal T per segment vs market + actual outcomes
Output: data/ipl_betx21_full_market_2026.parquet
"""

import bisect
import gzip
import json
import re
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from dateutil import parser as dtparser
from scipy.optimize import minimize_scalar
from scipy.special import expit, logit
from sklearn.isotonic import IsotonicRegression

warnings.filterwarnings("ignore")

# -- Paths ---------------------------------------------------------------------
BETX21_DIR  = Path(r"C:\Users\ADMINS\Documents\projects\betx21.live\ipl_matches_download")
DATA_DIR    = Path("data")
OUTPUT_FILE = DATA_DIR / "ipl_betx21_full_market_2026.parquet"

IPL_TEAMS = {
    "Chennai Super Kings", "Mumbai Indians", "Royal Challengers Bengaluru",
    "Kolkata Knight Riders", "Delhi Capitals", "Rajasthan Royals",
    "Punjab Kings", "Sunrisers Hyderabad", "Gujarat Titans",
    "Lucknow Super Giants",
}

# Betx21 uses shortened names for some teams -> map to canonical
TEAM_ALIASES = {
    "RC Bengaluru":           "Royal Challengers Bengaluru",
    "Royal Challengers":      "Royal Challengers Bengaluru",
    "RCB":                    "Royal Challengers Bengaluru",
    "CSK":                    "Chennai Super Kings",
    "MI":                     "Mumbai Indians",
    "KKR":                    "Kolkata Knight Riders",
    "DC":                     "Delhi Capitals",
    "RR":                     "Rajasthan Royals",
    "PBKS":                   "Punjab Kings",
    "SRH":                    "Sunrisers Hyderabad",
    "GT":                     "Gujarat Titans",
    "LSG":                    "Lucknow Super Giants",
}


def canonical_team(name):
    if name in IPL_TEAMS:
        return name
    return TEAM_ALIASES.get(name, name)

# -- Helpers -------------------------------------------------------------------
def parse_overs(score_str):
    """Extract overs float from 'runs/wkts (N.x)' -> float or None."""
    if not score_str:
        return None
    m = re.search(r"\((\d+\.?\d*)\)", score_str)
    return float(m.group(1)) if m else None


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


# ==============================================================================
# STEP 1: Parse betx21 scores files
# ==============================================================================
def parse_scores_file(path):
    records = []
    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            records.append({
                "t":  r.get("t"),
                "ev": r.get("ev"),
                "t1": canonical_team(r.get("t1", "") or ""),
                "t2": canonical_team(r.get("t2", "") or ""),
                "s1": r.get("s1", ""),
                "s2": r.get("s2", ""),
                "st": r.get("st", ""),
            })
    return records


def extract_match_info(scores):
    """Return {t1, t2, match_date_str, winner} or None."""
    if not scores:
        return None
    t1 = canonical_team(scores[0]["t1"] or "")
    t2 = canonical_team(scores[0]["t2"] or "")
    if not t1 or not t2:
        return None

    # Match date from first score timestamp
    try:
        match_date_str = dtparser.parse(scores[0]["t"]).strftime("%Y-%m-%d")
    except Exception:
        return None

    # Determine winner: scan last ~20 records for "won" in st
    winner = None
    for r in reversed(scores[-30:]):
        st = r.get("st", "")
        if "won" in st.lower() or "win" in st.lower():
            if t1.lower() in st.lower():
                winner = t1
            elif t2.lower() in st.lower():
                winner = t2
            break

    # Fallback: compare final runs
    if winner is None:
        last_with_both = None
        for r in reversed(scores):
            if r["s1"] and r["s2"]:
                last_with_both = r
                break
        if last_with_both:
            ov1 = parse_overs(last_with_both["s1"])
            ov2 = parse_overs(last_with_both["s2"])
            r1m = re.match(r"(\d+)/", last_with_both["s1"])
            r2m = re.match(r"(\d+)/", last_with_both["s2"])
            if r1m and r2m:
                runs1, runs2 = int(r1m.group(1)), int(r2m.group(1))
                if runs2 > runs1:
                    winner = t2
                elif runs1 > runs2:
                    winner = t1

    return {"t1": t1, "t2": t2, "match_date_str": match_date_str, "winner": winner}


def collect_betx21_matches():
    """
    Iterate all date folders, collect ev_ids for IPL matches.
    For ev_ids appearing in multiple folders, use the file with the most records.
    Returns: dict {ev_id -> {t1,t2,match_date_str,winner,scores_file,odds_file}}
    """
    # ev_id -> list of (n_records, folder, scores_path, odds_path)
    candidates = {}

    for date_dir in sorted(BETX21_DIR.iterdir()):
        if not date_dir.is_dir():
            continue
        for sf in date_dir.glob("*_scores.jsonl.gz"):
            ev_id = sf.stem.replace("_scores.jsonl", "")
            of = date_dir / f"{ev_id}_odds.jsonl.gz"
            if not of.exists():
                continue
            # Quick peek at team names (read first few lines only)
            try:
                with gzip.open(sf, "rt", encoding="utf-8", errors="replace") as fh:
                    first_lines = [json.loads(l) for l in fh if l.strip()]
                if not first_lines:
                    continue
                t1 = canonical_team(first_lines[0].get("t1", "") or "")
                t2 = canonical_team(first_lines[0].get("t2", "") or "")
                n  = len(first_lines)
            except Exception:
                continue

            if t1 not in IPL_TEAMS or t2 not in IPL_TEAMS:
                continue

            if ev_id not in candidates:
                candidates[ev_id] = []
            candidates[ev_id].append((n, date_dir.name, sf, of, first_lines))

    # For each ev_id, pick the folder with the most score records
    betx21 = {}
    for ev_id, opts in candidates.items():
        best = max(opts, key=lambda x: x[0])
        _, folder_date, sf, of, scores = best
        info = extract_match_info(scores)
        if not info:
            continue
        betx21[ev_id] = {
            "t1": info["t1"], "t2": info["t2"],
            "match_date_str": info["match_date_str"],
            "winner": info["winner"],
            "scores_file": sf,
            "odds_file": of,
        }

    return betx21


# ==============================================================================
# STEP 2: Map betx21 -> Cricsheet
# ==============================================================================
def build_cs_info():
    raw    = pd.read_parquet("data/ipl_raw/matches")
    raw26  = raw[raw["season"] == "2026"].copy()
    teams  = raw26.groupby(["match_id", "innings"])["batting_team"].first().unstack()
    dates  = raw26.groupby("match_id")["date"].first()
    wins   = raw26.groupby("match_id")["winner"].first()
    info   = pd.concat([dates, teams[1].rename("inn1_team"),
                        teams[2].rename("inn2_team"), wins], axis=1)
    info.columns = ["date", "inn1_team", "inn2_team", "winner"]
    info   = info.reset_index()
    info["date_str"] = pd.to_datetime(info["date"]).dt.strftime("%Y-%m-%d")
    return info


def map_betx21_to_cs(betx21_matches, cs_info):
    """Returns dict {ev_id -> {cs_match_id, inn1_team, inn2_team, winner, t1_is_inn1}}."""
    mapping = {}
    for ev_id, bx in betx21_matches.items():
        date_str = bx["match_date_str"]
        t1, t2   = bx["t1"], bx["t2"]
        on_date  = cs_info[cs_info["date_str"] == date_str]
        for _, row in on_date.iterrows():
            if {t1, t2} == {row["inn1_team"], row["inn2_team"]}:
                t1_is_inn1 = (t1 == row["inn1_team"])
                mapping[ev_id] = {
                    "cs_match_id": str(row["match_id"]),
                    "inn1_team":   row["inn1_team"],
                    "inn2_team":   row["inn2_team"],
                    "winner":      row["winner"],
                    "t1_is_inn1":  t1_is_inn1,
                }
                break
    return mapping


# ==============================================================================
# STEP 3: Extract end-of-over market odds
# ==============================================================================
def parse_odds_file(path):
    """Return list of {dt: datetime, p_t1: float} sorted by time."""
    records = []
    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("mt") != "matchOdds":
                continue
            if r.get("ms") != "active":
                continue
            runners = r.get("r", [])
            if len(runners) < 2:
                continue
            try:
                r0, r1 = runners[0], runners[1]
                if r0.get("st") != "active" or r1.get("st") != "active":
                    continue
                b0 = r0.get("b", [])
                b1 = r1.get("b", [])
                if not b0 or not b1:
                    continue
                back0, back1 = b0[0][0], b1[0][0]
                if back0 <= 1 or back1 <= 1:
                    continue
                inv0, inv1 = 1.0 / back0, 1.0 / back1
                p_t1 = inv0 / (inv0 + inv1)
                records.append({
                    "dt":   dtparser.parse(r["t"]),
                    "p_t1": p_t1,
                })
            except (IndexError, KeyError, ZeroDivisionError, TypeError):
                continue
    records.sort(key=lambda x: x["dt"])
    return records


def extract_eoo_odds(scores_records, odds_records, t1_is_inn1):
    """
    For each over N in innings 1 and innings 2, extract end-of-over market prob.
    'End of over N' = last odds snapshot before first ball of over N+1.
    Returns list of {innings, over, market_p_inn1}.
    """
    if not odds_records:
        return []

    # Parse score timestamps
    for r in scores_records:
        try:
            r["dt"] = dtparser.parse(r["t"])
        except Exception:
            r["dt"] = None

    # Build odds timeline arrays for bisect
    odds_times = [r["dt"] for r in odds_records]
    odds_p_t1  = np.array([r["p_t1"] for r in odds_records])

    result = []

    for innings, score_key in [(1, "s1"), (2, "s2")]:
        # Build (dt, overs_float) for this innings
        inn_timeline = []
        for r in scores_records:
            if r.get("dt") is None:
                continue
            ov = parse_overs(r.get(score_key, ""))
            if ov is not None:
                inn_timeline.append((r["dt"], ov))

        if not inn_timeline:
            continue

        inn_timeline.sort(key=lambda x: x[0])
        max_overs = max(ov for _, ov in inn_timeline)

        for over_n in range(1, 21):
            # Over_n is complete when score shows exactly over_n overs
            # First ball of over N+1 = first timestamp where overs > over_n
            first_after = None
            for dt, ov in inn_timeline:
                if ov > over_n:        # first ball of over N+1
                    first_after = dt
                    break

            if first_after is None:
                # Over N+1 never started (match ended during/after over_n)
                # Only extract if over_n was actually reached (score shows ≥ over_n-1+0.1)
                if max_overs < over_n - 1 + 0.1:
                    break  # over_n was never played
                # Use last odds overall for this innings
                if not odds_records:
                    break
                p_t1 = odds_records[-1]["p_t1"]
                market_p_inn1 = p_t1 if t1_is_inn1 else 1.0 - p_t1
                result.append({"innings": innings, "over": over_n,
                                "market_p_inn1": market_p_inn1})
                break  # no more overs after this

            # Last odds snapshot strictly before first_after
            idx = bisect.bisect_left(odds_times, first_after) - 1
            if idx < 0:
                continue

            p_t1 = float(odds_p_t1[idx])
            market_p_inn1 = p_t1 if t1_is_inn1 else 1.0 - p_t1
            result.append({"innings": innings, "over": over_n,
                            "market_p_inn1": market_p_inn1})

    return result


# ==============================================================================
# STEP 4: Train v7 model (<=2024 train, 2025 cal, 2026 test)
# ==============================================================================
def train_v7_model():
    from bbl_pipeline.training.trainer import XGBLogRegEnsemble

    print("  Loading ipl_features_v7/training.parquet ...")
    df = pd.read_parquet("data/ipl_features_v7/training.parquet")
    df["season_int"] = pd.to_numeric(
        df["season"].astype(str).str.split("/").str[0], errors="coerce"
    )

    train_df = df[df["season_int"] <= 2024].copy()
    cal_df   = df[df["season_int"] == 2025].copy()
    test_df  = df[df["season_int"] == 2026].copy()

    feats = [f for f in XGBLogRegEnsemble.TOP_FEATURES if f in df.columns]
    print(f"  Features: {len(feats)}/{len(XGBLogRegEnsemble.TOP_FEATURES)} available")
    print(f"  Train: {len(train_df):,}  Cal: {len(cal_df):,}  Test: {len(test_df):,}")

    # Train model on <=2024
    print("  Training XGBLogRegEnsemble on <=2024 ...")
    model = XGBLogRegEnsemble()
    model.fit(train_df[feats], train_df["is_winner"])

    # Raw predictions on cal + test
    print("  Predicting raw probabilities ...")
    cal_raw  = model.predict_proba(cal_df[feats])[:, 1]
    test_raw = model.predict_proba(test_df[feats])[:, 1]

    cal_df  = cal_df.copy();  cal_df["raw_p"]  = cal_raw
    test_df = test_df.copy(); test_df["raw_p"] = test_raw

    # Per-over isotonic calibrators on 2025
    print("  Fitting per-over isotonic calibrators on 2025 ...")
    calibrators = {}
    for (inn, ov), grp in cal_df.groupby(["innings", "over"]):
        if len(grp) < 5:
            continue
        ir = IsotonicRegression(out_of_bounds="clip")
        ir.fit(grp["raw_p"].values, grp["is_winner"].values)
        calibrators[(int(inn), int(ov))] = ir
    print(f"  Fitted {len(calibrators)} (innings, over) calibrators")

    # Apply calibrators to test
    def calibrate_row(row):
        key = (int(row["innings"]), int(row["over"]))
        if key in calibrators:
            return calibrators[key].predict([row["raw_p"]])[0]
        # Nearest-over fallback
        inn, ov = key
        for delta in range(1, 10):
            for d in [delta, -delta]:
                if (inn, ov + d) in calibrators:
                    return calibrators[(inn, ov + d)].predict([row["raw_p"]])[0]
        return row["raw_p"]

    test_df["cal_p"] = test_df.apply(calibrate_row, axis=1)
    return test_df


# ==============================================================================
# STEP 5: Build per-over model predictions (inn1 perspective)
# ==============================================================================
def build_per_over_preds(test_df):
    # Last ball of each over
    per_over = (
        test_df.sort_values(["match_id", "innings", "over", "ball"])
        .groupby(["match_id", "innings", "over"], as_index=False)
        .last()
    )

    # Convert cal_p -> inn1 perspective
    # inn1: batting_team = inn1_team -> cal_p = P(inn1 wins) ✓
    # inn2: batting_team = inn2_team -> cal_p = P(inn2 wins) -> need 1 - cal_p
    per_over["cal_p_inn1"] = np.where(
        per_over["innings"] == 1, per_over["cal_p"], 1.0 - per_over["cal_p"]
    )

    # Load CS metadata for inn1/inn2 team + winner
    raw   = pd.read_parquet("data/ipl_raw/matches")
    raw26 = raw[raw["season"] == "2026"]
    teams = raw26.groupby(["match_id", "innings"])["batting_team"].first().unstack()
    teams.columns = ["inn1_team", "inn2_team"]
    winners = raw26.groupby("match_id")["winner"].first().rename("cs_winner")

    per_over = per_over.merge(teams,   on="match_id", how="left")
    per_over = per_over.merge(winners, on="match_id", how="left")
    per_over["actual_inn1_wins"] = (
        per_over["cs_winner"] == per_over["inn1_team"]
    ).astype(float)

    return per_over[["match_id", "innings", "over", "cal_p_inn1",
                      "inn1_team", "inn2_team", "cs_winner", "actual_inn1_wins"]]


# ==============================================================================
# STEP 6: T-analysis
# ==============================================================================
def t_analysis(df, T_values):
    df = df.copy()
    df["phase"] = df.apply(lambda r: phase_label(r["over"], r["innings"]), axis=1)

    segments = ["Overall"] + sorted(df["phase"].unique().tolist())
    rows = []
    for T in T_values:
        p_T = apply_T(df["cal_p_inn1"].values, T)
        for seg in segments:
            mask = (pd.Series(True, index=df.index)
                    if seg == "Overall"
                    else df["phase"] == seg)
            sub_y = df.loc[mask, "actual_inn1_wins"].values
            sub_m = df.loc[mask, "market_p_inn1"].values
            sub_p = p_T[mask.values]
            n = len(sub_y)
            if n == 0:
                continue
            rows.append({
                "T": T, "segment": seg, "n": n,
                "brier_actual": float(np.mean((sub_p - sub_y) ** 2)),
                "brier_market": float(np.mean((sub_p - sub_m) ** 2)),
            })
    return pd.DataFrame(rows)


def find_optimal_T(df):
    df = df.copy()
    df["phase"] = df.apply(lambda r: phase_label(r["over"], r["innings"]), axis=1)

    segments = ["Overall"] + sorted(df["phase"].unique().tolist())
    rows = []
    for seg in segments:
        sub = df if seg == "Overall" else df[df["phase"] == seg]
        if len(sub) < 5:
            continue
        p = sub["cal_p_inn1"].values
        y = sub["actual_inn1_wins"].values
        m = sub["market_p_inn1"].values

        def b_actual(T): return np.mean((apply_T(p, T) - y) ** 2)
        def b_market(T): return np.mean((apply_T(p, T) - m) ** 2)

        res_a = minimize_scalar(b_actual, bounds=(0.25, 2.5), method="bounded")
        res_m = minimize_scalar(b_market, bounds=(0.25, 2.5), method="bounded")

        rows.append({
            "segment":          seg,
            "n":                len(sub),
            "T_opt_actual":     round(res_a.x, 3),
            "brier_opt_actual": round(res_a.fun, 6),
            "T_opt_market":     round(res_m.x, 3),
            "brier_opt_market": round(res_m.fun, 6),
        })
    return pd.DataFrame(rows)


# ==============================================================================
# MAIN
# ==============================================================================
if __name__ == "__main__":
    pd.set_option("display.width", 160)
    pd.set_option("display.max_columns", 20)
    pd.set_option("display.float_format", "{:.4f}".format)

    # -- Step 1: Collect betx21 IPL matches ----------------------------------
    print("=" * 70)
    print("STEP 1: Collecting betx21 IPL scores files ...")
    betx21_matches = collect_betx21_matches()
    print(f"  Found {len(betx21_matches)} unique IPL betx21 events with scores+odds")
    for ev_id, bx in sorted(betx21_matches.items()):
        print(f"    {ev_id}  {bx['match_date_str']}  {bx['t1']} vs {bx['t2']}")

    # -- Step 2: Map to Cricsheet ---------------------------------------------
    print("\nSTEP 2: Mapping betx21 -> Cricsheet ...")
    cs_info = build_cs_info()
    mapping = map_betx21_to_cs(betx21_matches, cs_info)
    print(f"  Mapped {len(mapping)}/{len(betx21_matches)} events to CS match IDs")
    for ev_id, m in sorted(mapping.items()):
        flag = "" if m["t1_is_inn1"] else " [t1=inn2]"
        print(f"    {ev_id} -> CS {m['cs_match_id']}  "
              f"{m['inn1_team']} vs {m['inn2_team']}{flag}")
    unmapped = [ev for ev in betx21_matches if ev not in mapping]
    if unmapped:
        print(f"  NOT mapped: {unmapped}")

    # -- Step 3: Extract end-of-over market odds ------------------------------
    print("\nSTEP 3: Extracting end-of-over market odds ...")
    market_rows = []
    for ev_id, m in sorted(mapping.items()):
        bx = betx21_matches[ev_id]
        scores = parse_scores_file(bx["scores_file"])
        odds   = parse_odds_file(bx["odds_file"])
        eoo    = extract_eoo_odds(scores, odds, m["t1_is_inn1"])
        actual_inn1_wins = float(m["winner"] == m["inn1_team"])
        for row in eoo:
            market_rows.append({
                "betx21_id":        ev_id,
                "cs_match_id":      m["cs_match_id"],
                "inn1_team":        m["inn1_team"],
                "inn2_team":        m["inn2_team"],
                "winner":           m["winner"],
                "actual_inn1_wins": actual_inn1_wins,
                "innings":          row["innings"],
                "over":             row["over"],
                "market_p_inn1":    row["market_p_inn1"],
            })
        print(f"  {ev_id}: {len(eoo)} over snapshots")

    market_df = pd.DataFrame(market_rows)
    print(f"  Total market rows: {len(market_df)} "
          f"across {market_df['cs_match_id'].nunique()} matches")

    # -- Step 4: Train v7 model -----------------------------------------------
    print("\nSTEP 4: Training v7 model ...")
    test_df = train_v7_model()

    # -- Step 5: Build per-over predictions + merge ---------------------------
    print("\nSTEP 5: Building per-over predictions ...")
    preds_df = build_per_over_preds(test_df)
    preds_df["match_id"] = preds_df["match_id"].astype(str)

    # Merge: market_df (betx21 side) ← left  +  preds_df (CS side) -> right
    merged = market_df.merge(
        preds_df[["match_id", "innings", "over", "cal_p_inn1"]],
        left_on  = ["cs_match_id", "innings", "over"],
        right_on = ["match_id", "innings", "over"],
        how="left",
    ).drop(columns=["match_id"])
    n_matched = merged["cal_p_inn1"].notna().sum()
    print(f"  Rows with model prediction: {n_matched}/{len(merged)}")

    # Drop rows without model prediction
    merged = merged.dropna(subset=["cal_p_inn1"]).reset_index(drop=True)
    print(f"  Final merged rows: {len(merged)} "
          f"({merged['cs_match_id'].nunique()} CS matches, "
          f"{merged['betx21_id'].nunique()} betx21 events)")

    # Save
    merged.to_parquet(OUTPUT_FILE, index=False)
    print(f"  Saved -> {OUTPUT_FILE}")

    # -- Step 6: T-analysis ---------------------------------------------------
    print("\nSTEP 6: T-analysis ...")
    df = merged.copy()

    # Baseline (T=1, no transformation)
    raw_brier_actual = np.mean((df["cal_p_inn1"] - df["actual_inn1_wins"]) ** 2)
    raw_brier_market = np.mean((df["cal_p_inn1"] - df["market_p_inn1"]) ** 2)
    print(f"  Baseline (T=1.0): Brier_actual={raw_brier_actual:.4f}  "
          f"Brier_market={raw_brier_market:.4f}")

    T_values = [0.30, 0.40, 0.50, 0.55, 0.60, 0.65,
                0.70, 0.75, 0.80, 0.85, 0.90, 0.95, 1.00]
    results_df = t_analysis(df, T_values)

    # -- Print T grid ---------------------------------------------------------
    print("\n-- Brier vs ACTUAL (lower=better) --")
    pivot_a = results_df.pivot(index="segment", columns="T", values="brier_actual")
    print(pivot_a.round(4).to_string())

    print("\n-- Brier vs MARKET (lower=better) --")
    pivot_m = results_df.pivot(index="segment", columns="T", values="brier_market")
    print(pivot_m.round(4).to_string())

    # -- Optimal T ------------------------------------------------------------
    print("\n-- Optimal T per segment --")
    opt_df = find_optimal_T(df)
    print(opt_df.to_string(index=False))

    # -- Summary per segment at optimal T_actual ------------------------------
    print("\n-- Summary at T=1.0 (raw) vs T_opt_actual --")
    summary_rows = []
    df["phase"] = df.apply(lambda r: phase_label(r["over"], r["innings"]), axis=1)
    for _, row in opt_df.iterrows():
        seg = row["segment"]
        sub = df if seg == "Overall" else df[df["phase"] == seg]
        p   = sub["cal_p_inn1"].values
        y   = sub["actual_inn1_wins"].values
        m   = sub["market_p_inn1"].values
        b1  = float(np.mean((p - y) ** 2))
        bm1 = float(np.mean((p - m) ** 2))
        T_opt = row["T_opt_actual"]
        p_T   = apply_T(p, T_opt)
        bT    = float(np.mean((p_T - y) ** 2))
        bmT   = float(np.mean((p_T - m) ** 2))
        summary_rows.append({
            "segment":       seg,
            "n":             int(row["n"]),
            "brier_T1_act":  round(b1, 4),
            "brier_T1_mkt":  round(bm1, 4),
            "T_opt":         T_opt,
            "brier_Topt_act":round(bT, 4),
            "brier_Topt_mkt":round(bmT, 4),
            "T_opt_market":  row["T_opt_market"],
        })
    summary_df = pd.DataFrame(summary_rows)
    print(summary_df.to_string(index=False))

    # -- Match-level overview -------------------------------------------------
    print("\n-- Match-level overview --")
    match_summary = (
        merged.groupby(["cs_match_id", "inn1_team", "inn2_team", "winner"])
        .agg(
            n_overs       = ("over", "count"),
            market_p_mean = ("market_p_inn1", "mean"),
            cal_p_mean    = ("cal_p_inn1", "mean"),
        )
        .reset_index()
    )
    print(match_summary.to_string(index=False))

    print("\nDone. Output ->", OUTPUT_FILE)
