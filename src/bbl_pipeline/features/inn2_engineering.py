"""
Inn2 Chase Feature Engineering — package module.

Moved from scripts/inn2_feature_engineering.py so it can be imported in
production inference code without sys.path hacks.

Also computes two live-inference features:
  - resource_team_adjusted   = resource_win_prob * (0.7 + 0.6 * team_strength_diff)
  - score_adjusted_by_team   = score_vs_par       * (1   +       team_strength_diff)

These are present in the training data (verified corr=1.0) but were not
produced by RealTimeFeatureMapper.  The router computes them explicitly.
"""

import numpy as np
import pandas as pd

# Chase difficulty thresholds (based on target_above_par distribution in IPL)
# p25=-16, p50=+4, p75=+25 → high=>+20, par=[-20,+20], low=<-20
HIGH_CHASE_THRESHOLD = 20
LOW_CHASE_THRESHOLD  = -20


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
      set_batter_exposure, over,
      resource_win_prob, team_strength_diff   ← for adjusted features
    """
    df = df.copy()

    # ── training-only league phase features used by NTB / generic phase routers ──
    # These were added in league phase build scripts before calling this helper.
    # Runtime router inference also needs them so phase-model feature lists don't
    # silently fall back to 0.0 for these columns.
    tap = df.get("target_above_par", pd.Series(0.0, index=df.index)).fillna(0.0)
    overs_remaining = df.get("overs_remaining", pd.Series(0.0, index=df.index)).fillna(0.0)
    wickets_lost = df.get("wickets_lost", pd.Series(0.0, index=df.index)).fillna(0.0)
    wickets_remaining_base = df.get(
        "wickets_remaining",
        10 - wickets_lost,
    ).fillna(10 - wickets_lost)
    required_run_rate = df.get("required_run_rate", pd.Series(0.0, index=df.index)).fillna(0.0)
    score_vs_par = df.get("score_vs_par", pd.Series(0.0, index=df.index)).fillna(0.0)
    resources_remaining = df.get("resources_remaining", pd.Series(0.0, index=df.index)).fillna(0.0)
    runs_last_12 = df.get("runs_last_12", pd.Series(0.0, index=df.index)).fillna(0.0)
    wickets_last_6_base = df.get("wickets_last_6", pd.Series(0.0, index=df.index)).fillna(0.0)

    # Populate the training-script features that are not otherwise engineered here.
    df["target_clarity_index"] = tap / (overs_remaining + 1.0)
    df["wicket_budget_remaining"] = wickets_remaining_base - (overs_remaining * 0.4)
    df["early_settle_flag"] = ((wickets_lost <= 2) & (score_vs_par >= 0)).astype(float)
    df["late_mid_run_gap"] = runs_last_12 - (required_run_rate * 2.0)

    # ── 0. Derived team-adjusted features (missing from RealTimeFeatureMapper) ──
    rwp = df.get("resource_win_prob", pd.Series(0.5, index=df.index)).fillna(0.5)
    tsd = df.get("team_strength_diff", pd.Series(0.0, index=df.index)).fillna(0.0)
    svp = df.get("score_vs_par", pd.Series(0.0, index=df.index)).fillna(0.0)

    df["resource_team_adjusted"]  = (rwp * (0.7 + 0.6 * tsd)).clip(0, 1.3)
    df["score_adjusted_by_team"]  = (svp * (1.0 + tsd)).clip(-300, 300)

    # ── 1. Chase Category Labels ──────────────────────────────────────────────
    tap = df.get("target_above_par", pd.Series(0.0, index=df.index)).fillna(0)

    df["is_high_chase"] = (tap > HIGH_CHASE_THRESHOLD).astype(float)
    df["is_par_chase"]  = tap.between(LOW_CHASE_THRESHOLD, HIGH_CHASE_THRESHOLD).astype(float)
    df["is_low_chase"]  = (tap < LOW_CHASE_THRESHOLD).astype(float)
    df["chase_category"] = np.where(
        tap > HIGH_CHASE_THRESHOLD,  1,
        np.where(tap < LOW_CHASE_THRESHOLD, -1, 0)
    ).astype(float)
    df["target_difficulty_norm"] = (tap / 40.0).clip(-2, 2)

    # ── 2. Chase State Features ───────────────────────────────────────────────
    df["wickets_remaining"] = (10 - df.get("wickets_lost", pd.Series(0, index=df.index)).fillna(0)).clip(0, 10)
    df["balls_remaining"]   = (df.get("overs_remaining", pd.Series(0, index=df.index)).fillna(0) * 6).clip(0, 120)

    rrr = df.get("required_run_rate", pd.Series(8.0, index=df.index)).fillna(8.0).clip(0, 50)
    crr = df.get("current_run_rate",  pd.Series(8.0, index=df.index)).fillna(8.0).clip(0, 40)

    df["crr_vs_rrr_ratio"]  = (crr / rrr.replace(0, np.nan)).fillna(1.0).clip(0, 5)
    df["scoring_rate_gap"]  = (crr - rrr).clip(-30, 30)
    df["required_rpb"]      = (rrr / 6).clip(0, 10)
    df["chase_run_buffer"]  = df.get("score_vs_par", pd.Series(0, index=df.index)).fillna(0)
    df["chase_completion"]  = (1 - df.get("resource_pct", pd.Series(1, index=df.index)).fillna(1)).clip(0, 1)

    # ── 3. Wicket Pressure Features ───────────────────────────────────────────
    df["wicket_pressure"]   = (df["wickets_remaining"].clip(0, 10) * rrr * 0 + df.get("wickets_lost", pd.Series(0, index=df.index)).fillna(0) * rrr).clip(0, 300)
    df["wr_x_rrr"]          = (df["wickets_remaining"] * rrr).clip(0, 500)
    df["runs_per_wkt_rem"]  = (
        rrr * df["balls_remaining"].clip(1, 120) / 6
        / df["wickets_remaining"].replace(0, 0.5)
    ).clip(0, 200)
    wl6  = df.get("wickets_last_6",  pd.Series(0, index=df.index)).fillna(0)
    wl12 = df.get("wickets_last_12", pd.Series(0, index=df.index)).fillna(0)
    df["critical_wicket_zone"]    = (df.get("wickets_lost", pd.Series(0, index=df.index)).fillna(0) >= 7).astype(float)
    df["comfortable_wicket_zone"] = (df["wickets_remaining"] >= 7).astype(float)
    df["wicket_shock_recency"]    = (wl6 / (wl12 + 0.5)).clip(0, 2)
    df["wicket_free_balls"]       = df.get("balls_since_wicket", pd.Series(0, index=df.index)).fillna(0).clip(0, 120)

    # Wicket × Chase difficulty interactions (helps all phases, especially PP high-chase)
    # High wickets in hand while DLS pace says you're behind → model was ignoring this signal
    df["wickets_x_high_chase"]    = (df["wickets_remaining"] * df["is_high_chase"]).clip(0, 10)
    df["wicket_resource_buffer"]  = (df["wickets_remaining"] / 10.0 - rwp.clip(0, 1)).clip(-1, 1)
    df["high_chase_wickets_flag"] = ((df["is_high_chase"] > 0) & (df["wickets_remaining"] >= 8)).astype(float)

    # ── 4. Momentum / Stagnation Features ─────────────────────────────────────
    r12   = df.get("runs_last_12",        pd.Series(0, index=df.index)).fillna(0)
    r18   = df.get("runs_last_18",        pd.Series(0, index=df.index)).fillna(0)
    dot12 = df.get("dot_pct_last_12",     pd.Series(0.5, index=df.index)).fillna(0.5)
    bnd18 = df.get("boundary_pct_last_18",pd.Series(0, index=df.index)).fillna(0)

    pace2 = r12 / 2
    pace3 = r18 / 3

    df["momentum_vs_rrr"]      = (pace2 / rrr.replace(0, np.nan)).fillna(1.0).clip(0, 5)
    df["momentum_trend"]       = (pace2 - pace3).clip(-10, 10)
    df["momentum_acceleration"] = (r12 * 1.5 - r18).clip(-20, 30)
    df["scoring_consistency"]  = (pace2 / (pace3 + 0.5)).clip(0, 4)
    df["dot_pressure"]         = (dot12 * rrr).clip(0, 50)
    df["boundary_momentum"]    = (bnd18 * crr).clip(0, 80)
    df["momentum_score"]       = df["crr_vs_rrr_ratio"] * (1 - dot12)

    wicket_cost = (1 - (wl6 / 4.0)).clip(0, 1)
    df["wicket_adj_momentum"]  = (df["momentum_vs_rrr"] * wicket_cost).clip(0, 5)
    df["net_momentum"]         = (df["scoring_rate_gap"] * wicket_cost).clip(-30, 30)

    bsw = df.get("balls_since_wicket", pd.Series(0, index=df.index)).fillna(0).clip(0, 120)
    df["recovery_momentum"]    = (bsw / 6 * (df["crr_vs_rrr_ratio"] - 1).clip(-2, 2)).clip(-20, 20)
    df["wicket_cluster_flag"]  = (wl6 >= 2).astype(float)
    df["recent_surge_flag"]    = (pace2 >= rrr).astype(float)
    df["momentum_shift_flag"] = ((df["momentum_score"] > 0.5) & (df["scoring_rate_gap"] < 0)).astype(float)
    df["acceleration_zone"] = ((overs_remaining <= 4) & (df["crr_vs_rrr_ratio"] >= 0.9)).astype(float)
    df["late_wkt_collapse_risk"] = ((wickets_last_6_base >= 2) & (rrr > 9)).astype(float)

    dls_p = df.get("dls_pressure_index", pd.Series(0, index=df.index)).fillna(0).clip(0, 1)
    df["pressure_momentum_gap"]   = (dls_p - (1 - df["crr_vs_rrr_ratio"].clip(0, 2))).clip(-1, 1)
    df["momentum_under_pressure"] = (df["crr_vs_rrr_ratio"] / (dls_p + 0.1)).clip(0, 10)

    bp = df.get("batting_pair_strength", pd.Series(0, index=df.index)).fillna(0).clip(0, 5)
    df["batting_pair_momentum"] = (bp * df["crr_vs_rrr_ratio"]).clip(0, 20)
    df["pair_strength_adj"]     = (bp * wicket_cost).clip(0, 5)

    wr10 = df["wickets_remaining"] / 10.0
    df["momentum_x_wickets"]   = (df["momentum_score"] * wr10).clip(0, 5)

    df["accel_potential"]  = df.get("acceleration_potential", pd.Series(0, index=df.index)).fillna(0)
    df["crr_resource_adj"] = df.get("crr_times_res", pd.Series(0, index=df.index)).fillna(0).clip(0, 40)

    # ── 5. Inn1 Quality / Chase Context Features ──────────────────────────────
    indef  = df.get("inn1_defendability", pd.Series(0.5, index=df.index)).fillna(0.5).clip(0, 1)
    inn1pp = df.get("inn1_pp_runs",       pd.Series(0,   index=df.index)).fillna(0)
    inn1dr = df.get("inn1_death_rr",      pd.Series(8.0, index=df.index)).fillna(8.0)
    inn1wl = df.get("inn1_wickets_lost",  pd.Series(5,   index=df.index)).fillna(5)

    df["inn1_quality_index"]   = (indef * 0.5 + (inn1dr / 15) * 0.3 + ((10 - inn1wl) / 10) * 0.2).clip(0, 1)
    df["inn1_pp_vs_median"]    = (inn1pp - 50).clip(-30, 30)
    df["inn1_death_intensity"] = (inn1dr / 10.0).clip(0, 3)

    # ── 6. Chase Category × Feature Interactions ──────────────────────────────
    hc  = df["is_high_chase"]
    lc  = df["is_low_chase"]
    pc  = df["is_par_chase"]
    cat = df["chase_category"]

    pi = df.get("pressure_index", pd.Series(0, index=df.index)).fillna(0)
    df["rrr_x_high_chase"]      = (rrr * hc).clip(0, 50)
    df["rrr_x_low_chase"]       = (rrr * lc).clip(0, 50)
    df["pressure_x_high_chase"] = (pi * hc)
    df["pressure_x_low_chase"]  = (pi * lc)
    df["inn1def_x_hard_chase"]  = (indef * (hc + 0.5 * pc)).clip(0, 1.5)
    df["svp_x_chase_cat"]       = (svp * (cat + 1)).clip(-200, 200)

    # ── 7. Phase-specific Features ─────────────────────────────────────────────
    ov = df.get("over", pd.Series(1, index=df.index)).fillna(1)

    df["pp_run_rate_premium"]  = (crr - 8.0).clip(-8, 20)
    df["pp_chase_feasibility"] = (crr / rrr.replace(0, np.nan)).fillna(1).clip(0, 4)

    # PP easy-chase features (used by ipl_v12 PP model)
    vcs = df.get("venue_chase_success", pd.Series(0.5, index=df.index)).fillna(0.5)
    res = df.get("resources_remaining", pd.Series(1.0, index=df.index)).fillna(1.0)
    rrr_clipped = rrr.clip(lower=0.1)
    df["pp_ease_score"]           = (-tap / rrr_clipped).clip(-50, 50)
    df["pp_rrr_ease"]             = (10.0 - rrr).clip(-40, 10)
    df["chase_ease_x_venue"]      = ((-tap).clip(lower=0) * vcs).clip(0, 200)
    df["low_target_strong_venue"] = ((tap < -15).astype(float) * vcs).clip(0, 1)
    df["pp_resources_adj_ease"]   = ((-tap) * res).clip(-300, 300)

    pp_ball = (ov * 6 + df.get("ball", pd.Series(0, index=df.index)).fillna(0) + 1).clip(1, 36)
    pp_progress = (pp_ball / 36.0).clip(0.03, 1.0)
    overs_faced = (pp_ball / 6.0).clip(0.2, 6.0)
    current_score_est = (crr * overs_faced).clip(0, 120)
    expected_pp_curve = (inn1pp * pp_progress).clip(1, 120)
    innings_pp_rate = (inn1pp / 6.0).clip(1, 20)
    gap_rr = (rrr - crr).clip(lower=0)

    df["pp_scoring_trajectory"] = (current_score_est / expected_pp_curve).replace([np.inf, -np.inf], np.nan).fillna(1.0).clip(0, 4)
    df["pp_wicket_impact_adj"] = (df.get("wickets_lost", pd.Series(0, index=df.index)).fillna(0) * (1.4 - pp_progress)).clip(0, 10)
    df["over_normalized_score"] = (crr / rrr.replace(0, np.nan)).replace([np.inf, -np.inf], np.nan).fillna(1.0).clip(0, 4)
    df["pp_survival_score"] = (bsw / pp_ball).replace([np.inf, -np.inf], np.nan).fillna(0.0).clip(0, 3)
    df["inn1_pp_run_rate"] = innings_pp_rate
    df["pp_run_rate_vs_inn1_pp"] = (crr / innings_pp_rate).replace([np.inf, -np.inf], np.nan).fillna(1.0).clip(0, 4)
    df["inn1_pp_runs_x_is_high_chase"] = (inn1pp * hc).clip(0, 150)
    df["inn1_quality_x_chase_diff"] = (df["inn1_quality_index"] * df["target_difficulty_norm"]).clip(-3, 3)
    df["set_batter_stability"] = (df.get("set_batter_exposure", pd.Series(0, index=df.index)).fillna(0) * (1 - df.get("wickets_lost", pd.Series(0, index=df.index)).fillna(0) / 10.0)).clip(0, 100)
    df["recovery_potential"] = (df["recovery_momentum"] * df["wickets_remaining"]).clip(-100, 100)
    df["dot_pressure_adj"] = (dot12 * rrr / 10.0).clip(0, 10)
    df["boundary_acceleration"] = (bnd18 * gap_rr).clip(0, 20)
    df["above_par_wicket_cost"] = (df.get("wickets_lost", pd.Series(0, index=df.index)).fillna(0) * tap.clip(lower=0) / 20.0).clip(0, 50)
    df["below_par_run_cushion"] = ((-tap).clip(lower=0) * df["wickets_remaining"]).clip(0, 400)
    df["chase_category_x_balls_since_wkt"] = (cat * bsw).clip(-120, 120)
    df["runs_per_over_trend"] = ((1.5 * r12 - r18).clip(0, 36) / r18.replace(0, np.nan) * 3.0).replace([np.inf, -np.inf], np.nan).fillna(1.0).clip(0, 6)
    df["score_vs_rrr_momentum"] = ((crr - rrr) * (6 - ov)).clip(-60, 60)
    df["pp_score_bin"] = pd.cut(svp, bins=[-300, -20, -10, -3, 3, 10, 20, 300], labels=False, include_lowest=True).fillna(0).astype(int)
    df["pp_gap_bin"] = pd.cut(crr - rrr, bins=[-50, -6, -3, -1, 1, 3, 6, 50], labels=False, include_lowest=True).fillna(0).astype(int)

    df["partnership_solidity"] = (
        df["wicket_free_balls"] / 30 * 0.4
        + df.get("set_batter_exposure", pd.Series(0, index=df.index)).fillna(0) / 60 * 0.3
        + (1 - wl12 / 4) * 0.3
    ).clip(0, 1)

    df["death_chase_urgency"]  = (rrr / crr.replace(0, np.nan)).fillna(2).clip(0.5, 10)
    df["death_feasibility"]    = (df["wickets_remaining"] / rrr.replace(0, np.nan)).fillna(1).clip(0, 5)

    # ── 8. Chase Outcome Pattern Features ─────────────────────────────────────
    df["comfortable_chase_flag"] = (
        (svp > 5) & (df["wickets_remaining"] >= 5)
    ).astype(float)
    df["rescue_needed_flag"] = (
        (svp < -20) & (df["wickets_remaining"] <= 4)
    ).astype(float)
    df["tight_finish_zone"] = (
        (svp.abs() < 20) & (ov >= 16)
    ).astype(float)

    # ── 9. Relative Performance Index ─────────────────────────────────────────
    df["venue_chase_advantage"] = (
        df.get("venue_chase_success", pd.Series(0.5, index=df.index)).fillna(0.5)
        * (1 + df.get("batting_won_toss", pd.Series(0, index=df.index)).fillna(0) * 0.1)
    ).clip(0, 1)

    # ── 10. v17 PP Chase Tracking Features ────────────────────────────────────
    # NOTE: These features were listed in phase_features.json / routing_config.json
    # but were missing from training (ipl_features_v16).  They are implemented here
    # consistently with the gap_rr / innings_pp_rate / dls_p variables defined above.
    # They will produce meaningful non-zero values; retrain model to get full benefit.

    overs_rem = df.get("overs_remaining", pd.Series(0, index=df.index)).fillna(0).clip(0, 20)

    # How much urgency has built up in the late-middle window: deficit × innings_progress
    df["late_mid_urgency"] = (
        gap_rr * (1 - (overs_rem / 20.0).clip(0, 1))
    ).clip(0, 20)

    # Composite "comfortable finish" zone: ahead-of-par AND wickets in hand
    df["finish_quality_zone"] = (
        (svp.clip(-50, 30) + 50) / 80.0 * (df["wickets_remaining"] / 10.0)
    ).clip(0, 1)

    # How on-track is the chase: RR parity × wickets × inverse DLS pressure
    df["chase_on_track_score"] = (
        df["crr_vs_rrr_ratio"] * (df["wickets_remaining"] / 10.0) * (1 - dls_p.clip(0, 0.8))
    ).clip(0, 5)

    # RRR relative to the inn1 PP run-rate (proxy for venue/match expected pace)
    df["early_mid_rrr_vs_venue_avg"] = (rrr - innings_pp_rate).clip(-15, 15)

    return df


def get_feature_sets() -> dict:
    """Return the recommended feature sets per phase after engineering."""

    INN2_PP = [
        "chase_category", "is_high_chase", "is_low_chase", "is_par_chase",
        "target_difficulty_norm",
        "target_above_par", "inn1_defendability", "inn1_pp_runs",
        "inn1_death_rr", "inn1_wickets_lost",
        "inn1_quality_index", "inn1_pp_vs_median", "inn1_death_intensity",
        "venue_chase_success", "venue_chase_advantage",
        "batting_won_toss", "situation_advantage", "team_strength_diff",
        "batting_team_situation_wr", "bowling_team_situation_wr",
        "batting_team_win_rate", "bowling_team_win_rate",
        "pressure_index", "score_vs_par", "run_rate_diff",
        "resource_win_prob", "dls_pressure_index",
        "current_run_rate", "required_run_rate",
        "crr_vs_rrr_ratio", "scoring_rate_gap",
        "pp_run_rate_premium", "pp_chase_feasibility",
        "momentum_vs_rrr", "momentum_score",
        "dot_pressure", "boundary_momentum",
        "wicket_adj_momentum", "net_momentum",
        "recent_surge_flag",
        "wickets_last_6", "wicket_shock_recency",
        "batting_pair_momentum", "crr_resource_adj", "accel_potential",
        "rrr_x_high_chase", "rrr_x_low_chase",
        "pressure_x_high_chase", "inn1def_x_hard_chase",
        "wickets_remaining", "overs_remaining",
        "resource_team_adjusted", "resources_remaining",
        # Wicket-resource interaction features
        "runs_per_wkt_rem", "wr_x_rrr", "comfortable_wicket_zone",
        "wickets_x_high_chase", "wicket_resource_buffer", "high_chase_wickets_flag",
    ]

    INN2_MID = [
        "chase_category", "is_high_chase", "is_low_chase", "target_difficulty_norm",
        "score_vs_par", "dls_pressure_index", "resource_win_prob",
        "required_run_rate", "current_run_rate", "run_rate_diff",
        "crr_vs_rrr_ratio", "scoring_rate_gap",
        "score_per_wicket", "chase_difficulty", "chase_run_buffer",
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
        "balls_since_wicket", "set_batter_exposure", "wickets_last_6", "wickets_last_12",
        "wicket_shock_recency", "partnership_solidity",
        "wickets_remaining", "wicket_pressure", "wr_x_rrr",
        "comfortable_wicket_zone", "critical_wicket_zone",
        "wicket_cluster_flag",
        "target_above_par", "inn1_defendability", "inn1_pp_runs", "inn1_death_rr",
        "inn1_quality_index",
        "venue_chase_success", "situation_advantage",
        "batting_team_situation_wr", "batting_team_win_rate",
        "score_adjusted_by_team", "resource_team_adjusted",
        "rrr_x_high_chase", "pressure_x_high_chase", "svp_x_chase_cat",
        "comfortable_chase_flag", "rescue_needed_flag",
        "rrr_times_wickets", "wickets_times_balls", "pressure_index",
        "overs_remaining", "resource_pct",
        # Wicket-resource interaction features
        "runs_per_wkt_rem", "wickets_x_high_chase", "wicket_resource_buffer", "high_chase_wickets_flag",
    ]

    INN2_DEATH = [
        "chase_category", "is_high_chase", "is_low_chase",
        "dls_pressure_index", "pressure_index", "score_vs_par",
        "required_run_rate", "current_run_rate", "run_rate_diff",
        "chase_difficulty", "crr_vs_rrr_ratio", "required_rpb",
        "death_chase_urgency", "death_feasibility",
        "wickets_lost", "wickets_remaining", "runs_per_wkt_rem",
        "wickets_times_balls", "rrr_times_wickets", "wr_x_rrr",
        "critical_wicket_zone",
        "wickets_last_6", "wickets_last_12", "wicket_shock_recency",
        "wicket_cluster_flag",
        "runs_last_12", "boundary_pct_last_18",
        "momentum_vs_rrr", "momentum_trend", "momentum_score",
        "momentum_acceleration",
        "dot_pressure", "boundary_momentum",
        "wicket_adj_momentum", "net_momentum",
        "recovery_momentum", "recent_surge_flag",
        "pressure_momentum_gap", "momentum_under_pressure",
        "batting_pair_momentum", "pair_strength_adj",
        "accel_potential", "crr_resource_adj",
        "overs_remaining", "balls_remaining", "resource_pct",
        "resource_team_adjusted", "resources_remaining",
        "chase_completion",
        "target_above_par", "inn1_pp_runs", "inn1_death_rr",
        "inn1_quality_index",
        "batting_team_win_rate", "situation_advantage",
        "rrr_x_high_chase", "tight_finish_zone",
        "comfortable_chase_flag", "rescue_needed_flag",
        # Wicket-resource interaction features
        "wickets_x_high_chase", "wicket_resource_buffer", "high_chase_wickets_flag",
    ]

    return {"pp": INN2_PP, "mid": INN2_MID, "death": INN2_DEATH}
