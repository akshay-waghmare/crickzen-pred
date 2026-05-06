"""
Inn2 Chase Feature Engineering Module
======================================
Creates rich inn2-specific features from existing ipl_features_v7 data:

1. Chase Category Labels:
   - is_high_chase  : target well above venue par (target_above_par > +20)
   - is_par_chase   : target near venue par  (|target_above_par| <= 20)
   - is_low_chase   : target below venue par (target_above_par < -20)
   - chase_category : ordinal -1/0/1

2. Chase State Features:
   - wickets_remaining, balls_remaining, required_runs_per_ball
   - crr_vs_rrr_ratio, chase_run_buffer, scoring_rate_gap

3. Momentum & Pressure Interactions:
   - dot_pressure, momentum_vs_required, wicket_shock_recency
   - resource_efficiency

4. Chase-Category Interactions (explicit):
   - rrr_x_high_chase, rrr_x_low_chase
   - pressure_x_high_chase, inn1def_x_hard_chase

5. Inn2 PP Specific:
   - pp_chase_feasibility, inn1_quality_index

6. Inn2 Death Specific:
   - last5_run_rate, runs_per_wicket_remaining, chase_completion_index

Usage:
    from scripts.inn2_feature_engineering import engineer_inn2_features
    df_inn2 = engineer_inn2_features(df[df['innings'] == 2])
"""

import numpy as np
import pandas as pd

# ── Chase difficulty thresholds (based on target_above_par distribution) ─────
# p25 = -16, p50 = +4, p75 = +25  → high = >+20, par = [-20, +20], low = <-20
HIGH_CHASE_THRESHOLD = 20   # inn1 scored > 20 runs above venue par
LOW_CHASE_THRESHOLD  = -20  # inn1 scored > 20 runs below venue par


def engineer_inn2_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add inn2-specific engineered features to a DataFrame of inn2 rows.
    Operates on a copy — does not mutate input.

    Expects columns from ipl_features_v7:
      target_above_par, inn1_defendability, inn1_pp_runs, inn1_death_rr,
      inn1_wickets_lost, wickets_lost, overs_remaining, required_run_rate,
      current_run_rate, run_rate_diff, score_vs_par, pressure_index,
      dls_pressure_index, resources_remaining, resource_pct,
      runs_last_12, runs_last_18, wickets_last_12, wickets_last_6,
      dot_pct_last_12, boundary_pct_last_18, balls_since_wicket,
      set_batter_exposure, over
    """
    df = df.copy()

    # ── 1. Chase Category Labels ───────────────────────────────────────────────
    tap = df["target_above_par"].fillna(0)

    df["is_high_chase"] = (tap > HIGH_CHASE_THRESHOLD).astype(float)
    df["is_par_chase"]  = (tap.between(LOW_CHASE_THRESHOLD, HIGH_CHASE_THRESHOLD)).astype(float)
    df["is_low_chase"]  = (tap < LOW_CHASE_THRESHOLD).astype(float)
    # Ordinal: -1=low, 0=par, +1=high
    df["chase_category"] = np.where(
        tap > HIGH_CHASE_THRESHOLD,  1,
        np.where(tap < LOW_CHASE_THRESHOLD, -1, 0)
    ).astype(float)
    # Continuous target difficulty (normalised, roughly ~[-1, +1])
    df["target_difficulty_norm"] = (tap / 40.0).clip(-2, 2)

    # ── 2. Chase State Features ────────────────────────────────────────────────
    df["wickets_remaining"] = (10 - df["wickets_lost"]).clip(0, 10)
    df["balls_remaining"]   = (df["overs_remaining"] * 6).clip(0, 120)

    rrr = df["required_run_rate"].clip(0, 50)
    crr = df["current_run_rate"].clip(0, 40)

    # Current vs required rate ratio — how far ahead/behind
    df["crr_vs_rrr_ratio"]   = (crr / rrr.replace(0, np.nan)).fillna(1.0).clip(0, 5)
    df["scoring_rate_gap"]   = (crr - rrr).clip(-30, 30)   # same as run_rate_diff but direct
    df["required_rpb"]       = (rrr / 6).clip(0, 10)       # required runs per ball

    # "comfort buffer": runs above/below par (inverted sign — positive = behind)
    df["chase_run_buffer"]   = df["score_vs_par"].fillna(0)   # already exists; alias for clarity

    # Chase completion index = how much of the target has been effectively secured
    # = (par_score_fraction_completed) proxy via resource_pct
    df["chase_completion"]   = (1 - df["resource_pct"].fillna(1)).clip(0, 1)

    # ── 3. Wicket Pressure Features ───────────────────────────────────────────
    df["wicket_pressure"]    = (df["wickets_lost"] * rrr).clip(0, 300)
    df["wr_x_rrr"]           = (df["wickets_remaining"] * rrr).clip(0, 500)  # complement of rrr_times_wickets
    df["runs_per_wkt_rem"]   = (
        rrr * df["balls_remaining"].clip(1, 120) / 6
        / df["wickets_remaining"].replace(0, 0.5)
    ).clip(0, 200)

    # Critical wicket zone: ≥7 down or ≤3 wickets remaining
    df["critical_wicket_zone"] = (df["wickets_lost"] >= 7).astype(float)
    df["comfortable_wicket_zone"] = (df["wickets_remaining"] >= 7).astype(float)

    # Recent wicket acceleration: are wickets falling fast recently?
    wl6  = df["wickets_last_6"].fillna(0)
    wl12 = df["wickets_last_12"].fillna(0)
    df["wicket_shock_recency"] = (wl6 / (wl12 + 0.5)).clip(0, 2)
    df["wicket_free_balls"]    = df["balls_since_wicket"].fillna(0).clip(0, 120)

    # ── 4. Momentum / Stagnation Features ─────────────────────────────────────
    r12   = df["runs_last_12"].fillna(0)
    r18   = df["runs_last_18"].fillna(0)
    dot12 = df["dot_pct_last_12"].fillna(0.5)
    bnd18 = df["boundary_pct_last_18"].fillna(0)
    # wl6 / wl12 already defined in section 3 above

    # Per-over scoring rates (last 2 overs and last 3 overs)
    pace2 = r12 / 2                                        # avg runs/over, last 2 overs
    pace3 = r18 / 3                                        # avg runs/over, last 3 overs

    # Momentum (recent rate) vs required rate
    df["momentum_vs_rrr"]    = (pace2 / rrr.replace(0, np.nan)).fillna(1.0).clip(0, 5)

    # Over-level acceleration: is the team scoring faster in the last 2 overs vs last 3?
    # Positive = accelerating, negative = decelerating
    df["momentum_trend"]     = (pace2 - pace3).clip(-10, 10)

    # Stronger acceleration: last over implied = runs_last_12 - (runs_last_18 - runs_last_12)
    # i.e., 2×last2 − last3  (> 0 means last 2 overs faster than previous 1 over)
    df["momentum_acceleration"] = (r12 * 1.5 - r18).clip(-20, 30)

    # Scoring consistency: ratio of last-2 vs last-3 over pace (>1 = building, <1 = fading)
    df["scoring_consistency"]   = (pace2 / (pace3 + 0.5)).clip(0, 4)

    # Stagnation under pressure: high dot% while requirement is high
    df["dot_pressure"]       = (dot12 * rrr).clip(0, 50)
    df["boundary_momentum"]  = (bnd18 * crr).clip(0, 80)

    # Combined momentum score: recent run rate × (1 − dot rate)
    df["momentum_score"]     = df["crr_vs_rrr_ratio"] * (1 - dot12)

    # ── Wicket-adjusted momentum ───────────────────────────────────────────────
    # Scoring speed penalised by wickets falling recently
    wicket_cost = (1 - (wl6 / 4.0)).clip(0, 1)           # 0 wkts=1.0, 4 wkts=0.0
    df["wicket_adj_momentum"]   = (df["momentum_vs_rrr"] * wicket_cost).clip(0, 5)

    # Net momentum after wicket cost: positive = genuinely ahead despite wickets
    df["net_momentum"]          = (df["scoring_rate_gap"] * wicket_cost).clip(-30, 30)

    # ── Recovery momentum ─────────────────────────────────────────────────────
    # Long partnership in progress AND team scoring ahead of required rate
    bsw = df["balls_since_wicket"].fillna(0).clip(0, 120)
    df["recovery_momentum"]     = (bsw / 6 * (df["crr_vs_rrr_ratio"] - 1).clip(-2, 2)).clip(-20, 20)

    # Wicket collapse flag: 2+ wickets in last 6 balls → very dangerous
    df["wicket_cluster_flag"]   = (wl6 >= 2).astype(float)

    # Recent surge flag: last-2-over scoring pace beats required rate
    df["recent_surge_flag"]     = (pace2 >= rrr).astype(float)

    # ── Pressure-momentum interaction ─────────────────────────────────────────
    # High DLS pressure + team still scoring well = "managed pressure" (very different signal)
    dls_p = df["dls_pressure_index"].fillna(0).clip(0, 1)
    df["pressure_momentum_gap"]    = (dls_p - (1 - df["crr_vs_rrr_ratio"].clip(0, 2))).clip(-1, 1)
    df["momentum_under_pressure"]  = (df["crr_vs_rrr_ratio"] / (dls_p + 0.1)).clip(0, 10)

    # ── Batting pair × momentum interaction ───────────────────────────────────
    bp = df["batting_pair_strength"].fillna(0).clip(0, 5)
    df["batting_pair_momentum"]     = (bp * df["crr_vs_rrr_ratio"]).clip(0, 20)
    df["pair_strength_adj"]         = (bp * wicket_cost).clip(0, 5)

    # ── Momentum × wickets interaction ────────────────────────────────────────
    wr10 = df["wickets_remaining"] / 10.0
    df["momentum_x_wickets"]        = (df["momentum_score"] * wr10).clip(0, 5)

    # ── Use existing acceleration_potential and crr_times_res ─────────────────
    # These are already in data but not currently in feature sets — expose as aliases
    df["accel_potential"]   = df["acceleration_potential"].fillna(0)
    df["crr_resource_adj"]  = df["crr_times_res"].fillna(0).clip(0, 40)

    # ── 5. Inn1 Quality / Chase Context Features ──────────────────────────────
    indef   = df["inn1_defendability"].fillna(0.5).clip(0, 1)
    inn1pp  = df["inn1_pp_runs"].fillna(0)
    inn1dr  = df["inn1_death_rr"].fillna(8.0)
    inn1wl  = df["inn1_wickets_lost"].fillna(5)

    # Inn1 quality index: how "commanding" was the batting side's inn1?
    # High inn1_defendability + high inn1_death_rr + low wickets = quality
    df["inn1_quality_index"] = (indef * 0.5 + (inn1dr / 15) * 0.3 + ((10 - inn1wl) / 10) * 0.2).clip(0, 1)

    # How far was inn1 powerplay from typical — predicts trajectory quality
    df["inn1_pp_vs_median"]  = (inn1pp - 50).clip(-30, 30)   # 50 is ~ IPL PP median

    # Is this a "death-rate-sustained" chase? (inn1 scored heavily in death)
    df["inn1_death_intensity"] = (inn1dr / 10.0).clip(0, 3)

    # ── 6. Chase Category × Feature Interactions ──────────────────────────────
    hc = df["is_high_chase"]
    lc = df["is_low_chase"]
    pc = df["is_par_chase"]
    cat = df["chase_category"]

    # High-chase specific pressure (hard target × required rate)
    df["rrr_x_high_chase"]        = (rrr * hc).clip(0, 50)
    df["rrr_x_low_chase"]         = (rrr * lc).clip(0, 50)
    df["pressure_x_high_chase"]   = (df["pressure_index"].fillna(0) * hc)
    df["pressure_x_low_chase"]    = (df["pressure_index"].fillna(0) * lc)

    # Inn1 defendability matters more in high chases (hard targets demand more from bowling)
    df["inn1def_x_hard_chase"]    = (indef * (hc + 0.5 * pc)).clip(0, 1.5)

    # Score vs par weighted by chase difficulty
    svp = df["score_vs_par"].fillna(0)
    df["svp_x_chase_cat"]         = (svp * (cat + 1)).clip(-200, 200)   # boosted in high chase

    # ── 7. Phase-specific Features ────────────────────────────────────────────
    ov = df["over"].fillna(1)

    # PP-specific: how quickly is the chase being established?
    df["pp_run_rate_premium"]     = (crr - 8.0).clip(-8, 20)  # beats or trails typical PP pace (8 rpo)
    df["pp_chase_feasibility"]    = (crr / rrr.replace(0, np.nan)).fillna(1).clip(0, 4)  # same as crr_vs_rrr in PP

    # Mid-specific: partnership solidity score
    df["partnership_solidity"]    = (
        df["wicket_free_balls"] / 30 * 0.4
        + df["set_batter_exposure"].fillna(0) / 60 * 0.3
        + (1 - wl12 / 4) * 0.3
    ).clip(0, 1)

    # Death-specific: "finish" quality — can the tail support a big finish?
    df["death_chase_urgency"]     = (rrr / crr.replace(0, np.nan)).fillna(2).clip(0.5, 10)
    df["death_feasibility"]       = (df["wickets_remaining"] / rrr.replace(0, np.nan)).fillna(1).clip(0, 5)

    # ── 8. Chase Outcome Pattern Features ─────────────────────────────────────
    # "Comfortable chase" flag: ahead on runs AND have wickets in hand
    df["comfortable_chase_flag"] = (
        (svp > 5) & (df["wickets_remaining"] >= 5)
    ).astype(float)

    # "Rescue needed" flag: behind on runs AND low wickets
    df["rescue_needed_flag"] = (
        (svp < -20) & (df["wickets_remaining"] <= 4)
    ).astype(float)

    # "Tight finish" proxy: within 20 runs and 3 overs
    df["tight_finish_zone"] = (
        (svp.abs() < 20) & (ov >= 16)
    ).astype(float)

    # ── 9. Relative Performance Index ─────────────────────────────────────────
    # How much better/worse is the batting team vs the bowling team specifically?
    # (already have batting_team_situation_wr, bowling_team_situation_wr, situation_advantage)
    # Add: batting dominance in this SPECIFIC chase scenario
    df["venue_chase_advantage"] = (
        df["venue_chase_success"].fillna(0.5)
        * (1 + df["batting_won_toss"].fillna(0) * 0.1)
    ).clip(0, 1)

    return df


def get_feature_sets():
    """Return the recommended feature sets per phase after engineering."""

    # ── Inn2 PP features (overs 1–6) ──────────────────────────────────────────
    # Inn1 context dominates; team/venue info; early chase state
    # Momentum is limited at PP but scoring pace vs required matters
    INN2_PP = [
        # Chase category
        "chase_category", "is_high_chase", "is_low_chase", "is_par_chase",
        "target_difficulty_norm",
        # Inn1 quality
        "target_above_par", "inn1_defendability", "inn1_pp_runs",
        "inn1_death_rr", "inn1_wickets_lost",
        "inn1_quality_index", "inn1_pp_vs_median", "inn1_death_intensity",
        # Team/venue context
        "venue_chase_success", "venue_chase_advantage",
        "batting_won_toss", "situation_advantage", "team_strength_diff",
        "batting_team_situation_wr", "bowling_team_situation_wr",
        "batting_team_win_rate", "bowling_team_win_rate",
        # Early chase state
        "pressure_index", "score_vs_par", "run_rate_diff",
        "resource_win_prob", "dls_pressure_index",
        "current_run_rate", "required_run_rate",
        "crr_vs_rrr_ratio", "scoring_rate_gap",
        "pp_run_rate_premium", "pp_chase_feasibility",
        # Early momentum (limited but present)
        "momentum_vs_rrr", "momentum_score",
        "dot_pressure", "boundary_momentum",
        "wicket_adj_momentum", "net_momentum",
        "recent_surge_flag",
        "wickets_last_6", "wicket_shock_recency",
        "batting_pair_momentum", "crr_resource_adj", "accel_potential",
        # Interactions
        "rrr_x_high_chase", "rrr_x_low_chase",
        "pressure_x_high_chase", "inn1def_x_hard_chase",
        # State
        "wickets_remaining", "overs_remaining",
        "resource_team_adjusted", "resources_remaining",
    ]

    # ── Inn2 Mid features (overs 7–15) ────────────────────────────────────────
    # Momentum is MOST important here — trends establish chase trajectory
    INN2_MID = [
        # Chase category (context)
        "chase_category", "is_high_chase", "is_low_chase", "target_difficulty_norm",
        # Current match state (primary)
        "score_vs_par", "dls_pressure_index", "resource_win_prob",
        "required_run_rate", "current_run_rate", "run_rate_diff",
        "crr_vs_rrr_ratio", "scoring_rate_gap",
        "score_per_wicket", "chase_difficulty", "chase_run_buffer",
        # ── Momentum depth (key section) ──────────────────────────────────
        "runs_last_12", "runs_last_18",
        "boundary_pct_last_18", "dot_pct_last_12",
        "momentum_vs_rrr", "momentum_trend", "momentum_score",
        "momentum_acceleration", "scoring_consistency",
        "dot_pressure", "boundary_momentum",
        "wicket_adj_momentum", "net_momentum",
        "recovery_momentum", "recent_surge_flag",
        "pressure_momentum_gap", "momentum_under_pressure",
        "batting_pair_momentum", "pair_strength_adj",
        "momentum_x_wickets",
        "accel_potential", "crr_resource_adj",
        # Partnership / wicket state
        "balls_since_wicket", "set_batter_exposure", "wickets_last_6", "wickets_last_12",
        "wicket_shock_recency", "partnership_solidity",
        "wickets_remaining", "wicket_pressure", "wr_x_rrr",
        "comfortable_wicket_zone", "critical_wicket_zone",
        "wicket_cluster_flag",
        # Inn1 carryover
        "target_above_par", "inn1_defendability", "inn1_pp_runs", "inn1_death_rr",
        "inn1_quality_index",
        # Team/venue
        "venue_chase_success", "situation_advantage",
        "batting_team_situation_wr", "batting_team_win_rate",
        "score_adjusted_by_team", "resource_team_adjusted",
        # Interactions
        "rrr_x_high_chase", "pressure_x_high_chase", "svp_x_chase_cat",
        "comfortable_chase_flag", "rescue_needed_flag",
        # Composite pressure
        "rrr_times_wickets", "wickets_times_balls", "pressure_index",
        "overs_remaining", "resource_pct",
    ]

    # ── Inn2 Death features (overs 16–20) ─────────────────────────────────────
    # Momentum in last 2-3 overs is decisive — late acceleration / collapse
    INN2_DEATH = [
        # Chase category
        "chase_category", "is_high_chase", "is_low_chase",
        # Pressure (dominant)
        "dls_pressure_index", "pressure_index", "score_vs_par",
        "required_run_rate", "current_run_rate", "run_rate_diff",
        "chase_difficulty", "crr_vs_rrr_ratio", "required_rpb",
        "death_chase_urgency", "death_feasibility",
        # Wicket state (critical in death)
        "wickets_lost", "wickets_remaining", "runs_per_wkt_rem",
        "wickets_times_balls", "rrr_times_wickets", "wr_x_rrr",
        "critical_wicket_zone",
        "wickets_last_6", "wickets_last_12", "wicket_shock_recency",
        "wicket_cluster_flag",
        # ── Momentum in death (very recent matters most) ──────────────────
        "runs_last_12", "boundary_pct_last_18",
        "momentum_vs_rrr", "momentum_trend", "momentum_score",
        "momentum_acceleration",                # is last over better than previous?
        "dot_pressure", "boundary_momentum",
        "wicket_adj_momentum", "net_momentum",
        "recovery_momentum", "recent_surge_flag",
        "pressure_momentum_gap", "momentum_under_pressure",
        "batting_pair_momentum", "pair_strength_adj",
        "accel_potential", "crr_resource_adj",
        # Resources
        "overs_remaining", "balls_remaining", "resource_pct",
        "resource_team_adjusted", "resources_remaining",
        "chase_completion",
        # Inn1 targets
        "target_above_par", "inn1_pp_runs", "inn1_death_rr",
        "inn1_quality_index",
        # Team
        "batting_team_win_rate", "situation_advantage",
        # Interactions
        "rrr_x_high_chase", "tight_finish_zone",
        "comfortable_chase_flag", "rescue_needed_flag",
    ]

    return {
        "pp":    INN2_PP,
        "mid":   INN2_MID,
        "death": INN2_DEATH,
    }
