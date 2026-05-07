"""
Live Feature Watcher — reads data/ipl_live_ml.json every N seconds and prints
a full colour-coded feature audit table.

Usage:
    python scripts/watch_features.py              # default ipl_live_ml.json, 5s refresh
    python scripts/watch_features.py --once       # print once and exit
    python scripts/watch_features.py --json data/my_live.json
    python scripts/watch_features.py --interval 2
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

# Force UTF-8 stdout on Windows so emoji/ANSI print correctly
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ── ANSI colours ──────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
BLUE   = "\033[94m"
GREY   = "\033[90m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def ok(s):      return f"{GREEN}{s}{RESET}"
def warn(s):    return f"{YELLOW}{s}{RESET}"
def err(s):     return f"{RED}{s}{RESET}"
def info(s):    return f"{CYAN}{s}{RESET}"
def dim(s):     return f"{GREY}{s}{RESET}"
def bold(s):    return f"{BOLD}{s}{RESET}"

# ── Per-feature sanity rules ──────────────────────────────────────────────────
# Each entry: (default_sentinel, zero_ok_always, zero_ok_inn1_only, zero_ok_inn2_only, description)
# status flags: OK ✅ | DEFAULT ⚠️ | ZERO_CORRECT 🔵 | SUSPECT ❌
FEATURE_RULES = {
    # ── core resource ──────────────────────────────────────────────────────────
    "resource_win_prob":        (None, False, False, False, "DLS-style win prob [0,1]"),
    "expected_final_score":     (None, False, False, False, "DLS projected final score"),
    "score_vs_par":             (None, False, False, False, "Current score vs par (can be –ve)"),
    "dls_pressure_index":       (None, True,  False, False, "DLS pressure (0 in inn1)"),
    "pressure_index":           (None, True,  False, False, "RRR-based pressure"),
    "resource_pct":             (None, False, False, False, "DLS resource % remaining"),
    "resources_remaining":      (None, False, False, False, "Balls×wickets resource proxy"),
    "balls_remaining":          (None, False, False, False, "Balls left"),
    "wickets_remaining":        (None, False, False, False, "Wickets remaining"),
    "overs_remaining":          (None, False, False, False, "Overs remaining"),
    # ── rate features ─────────────────────────────────────────────────────────
    "current_run_rate":         (None, True,  False, False, "CRR"),
    "required_run_rate":        (None, True,  True,  False, "RRR (0 in inn1)"),
    "run_rate_diff":            (None, True,  True,  False, "CRR – RRR (0 in inn1)"),
    "rrr_times_wickets":        (None, True,  True,  False, "RRR × wickets (0 in inn1/no wkt)"),
    "crr_times_res":            (None, True,  False, False, "CRR × resources"),
    "chase_difficulty":         (None, True,  True,  False, "Chase difficulty (0 in inn1)"),
    # ── phase flags ───────────────────────────────────────────────────────────
    "is_powerplay":             (None, True,  False, False, "1 if in powerplay"),
    "is_middle_overs":          (None, True,  False, False, "1 if in middle overs"),
    "is_death_overs":           (None, True,  False, False, "1 if in death overs"),
    # ── score features ────────────────────────────────────────────────────────
    "current_score":            (None, True,  False, False, "Runs scored"),
    "wickets_lost":             (None, True,  False, False, "Wickets fallen"),
    "score_per_wicket":         (None, False, False, False, "Runs per wicket"),
    "wickets_times_balls":      (None, True,  False, False, "Wickets × balls faced"),
    "runs_required":            (0.0,  True,  True,  False, "Runs still needed (0 in inn1)"),
    # ── projected ─────────────────────────────────────────────────────────────
    "projected_score":          (None, True,  False, True,  "Inn1 projection (0 in inn2 ✓)"),
    "projected_vs_venue_avg":   (None, True,  False, True,  "Proj vs venue avg (0 in inn2 ✓)"),
    "score_vs_venue_over_par":  (None, True,  False, True,  "Score vs venue-over par (0 inn2 ✓)"),
    # ── rolling stats (sparse early = OK) ─────────────────────────────────────
    "runs_last_12":             (None, True,  False, False, "Runs in last 12 balls"),
    "runs_last_18":             (None, True,  False, False, "Runs in last 18 balls"),
    "boundary_pct_last_18":     (None, True,  False, False, "Boundary % last 18 balls"),
    "dot_pct_last_12":          (None, True,  False, False, "Dot % last 12 balls"),
    "wickets_last_6":           (None, True,  False, False, "Wickets in last 6 balls"),
    "wickets_last_12":          (None, True,  False, False, "Wickets in last 12 balls"),
    "wickets_last_30":          (None, True,  False, False, "Wickets in last 30 balls"),
    "balls_since_wicket":       (None, True,  False, False, "Balls since last wicket"),
    "set_batter_exposure":      (None, True,  False, False, "Max batsman balls faced"),
    "acceleration_potential":   (None, True,  False, False, "SR – CRR×16.67"),
    # ── team win rates ─────────────────────────────────────────────────────────
    "batting_team_win_rate":    (0.5,  False, False, False, "Batting team overall WR"),
    "bowling_team_win_rate":    (0.5,  False, False, False, "Bowling team overall WR"),
    "batting_team_situation_wr":(0.5,  False, False, False, "Batting team situation WR"),
    "bowling_team_situation_wr":(0.5,  False, False, False, "Bowling team situation WR"),
    "situation_advantage":      (None, True,  False, False, "Situation WR diff"),
    "team_strength_diff":       (None, True,  False, False, "Team overall WR diff"),
    "batting_team_venue_wr":    (0.5,  False, False, False, "Batting team WR at this venue"),
    "batting_won_toss":         (0.5,  False, False, False, "Batting team won toss (0.5=unk)"),
    "batting_recent_nrr_l5":    (0.0,  True,  False, False, "Batting team recent NRR (L5)"),
    # ── inn1 carryover ─────────────────────────────────────────────────────────
    "inn1_pp_runs":             (45.0, False, True,  False, "Inn1 powerplay runs"),
    "inn1_death_rr":            (9.0,  False, True,  False, "Inn1 death over run rate"),
    "inn1_wickets_lost":        (5.0,  False, True,  False, "Inn1 total wickets lost"),
    "inn1_defendability":       (0.5,  False, True,  False, "Resource win prob at end inn1"),
    "target_above_par":         (0.0,  True,  True,  False, "Inn1 score – venue avg (0 inn1)"),
    "venue_chase_success":      (0.5,  False, False, False, "Chase win rate at this venue"),
    "is_low_target":            (0.0,  True,  True,  False, "1 if target < 140 (else 0 ok)"),
    # ── venue stats ───────────────────────────────────────────────────────────
    "venue_avg_score":          (160.0,False, False, False, "Venue average 1st innings score"),
    "venue_avg_wickets":        (6.0,  False, False, False, "Venue average wickets"),
    "venue_bat_first_win_rate": (0.5,  False, False, False, "Venue bat-first win rate"),
    # ── player stats ──────────────────────────────────────────────────────────
    "batsman_rolling_avg":      (25.0, False, False, False, "Batsman rolling batting avg"),
    "batsman_rolling_sr":       (130.0,False, False, False, "Batsman rolling strike rate"),
    "batsman_venue_avg":        (38.0, False, False, False, "Batsman avg at this venue"),
    "batsman_venue_sr":         (61.0, False, False, False, "Batsman SR at this venue"),
    "batsman_vs_team_avg":      (31.5, False, False, False, "Batsman avg vs bowling team"),
    "batting_pair_strength":    (50.0, False, False, False, "Sum of both batsmen rolling avgs"),
    "bowler_rolling_econ":      (8.0,  False, False, False, "Bowler rolling economy"),
    "bowler_rolling_sr":        (18.0, False, False, False, "Bowler rolling strike rate"),
    "bowler_venue_econ":        (4.2,  False, False, False, "Bowler economy at this venue"),
    "bowler_venue_sr":          (516.0,False, False, False, "Bowler SR at this venue"),
    "bowler_vs_team_econ":      (5.7,  False, False, False, "Bowler economy vs batting team"),
    # ── extra state ───────────────────────────────────────────────────────────
    "innings":                  (None, False, False, False, "Innings number (1 or 2)"),
    "over":                     (None, True,  False, False, "Current over (0-indexed)"),
    "ball":                     (None, True,  False, False, "Ball within over"),
}

# Features in model training order (ipl_v11 / v12 TOP_FEATURES)
MODEL_FEATURES = [
    "resource_win_prob", "score_vs_par", "dls_pressure_index", "expected_final_score",
    "projected_vs_venue_avg", "projected_score", "is_powerplay", "score_per_wicket",
    "run_rate_diff", "required_run_rate", "chase_difficulty", "wickets_times_balls",
    "pressure_index", "team_strength_diff", "rrr_times_wickets", "overs_remaining",
    "batting_team_win_rate", "bowling_team_win_rate", "batting_team_situation_wr",
    "situation_advantage", "boundary_pct_last_18", "bowling_team_situation_wr",
    "runs_last_12", "runs_last_18", "wickets_last_12", "dot_pct_last_12",
    "set_batter_exposure", "balls_since_wicket", "wickets_last_6",
    "batsman_venue_avg", "batsman_venue_sr", "batsman_vs_team_avg",
    "bowler_venue_econ", "bowler_venue_sr", "bowler_vs_team_econ",
    "batting_pair_strength", "acceleration_potential", "wickets_last_30",
    "crr_times_res", "resources_remaining", "venue_chase_success", "target_above_par",
    "batting_won_toss", "inn1_wickets_lost", "inn1_pp_runs", "inn1_death_rr",
    "inn1_defendability", "score_vs_venue_over_par", "batting_team_venue_wr",
    "batting_recent_nrr_l5", "is_low_target",
]


def flag(name, value, innings):
    """Return (status_str, flag_char) for a feature value."""
    rule = FEATURE_RULES.get(name)
    if rule is None:
        return ok("OK"), "✅"

    default_val, zero_ok_always, zero_ok_inn1_only, zero_ok_inn2_only, _ = rule

    # Zero check — is it expected to be zero?
    is_zero = (value == 0.0 or value is None)
    if is_zero:
        if zero_ok_inn2_only and innings == 2:
            return info("INN2=0✓"), "🔵"
        if zero_ok_inn1_only and innings == 1:
            return info("INN1=0✓"), "🔵"
        if zero_ok_always:
            return dim("ZERO?"), "⚪"
        # Zero but NOT expected to be zero
        return err("ZERO!"), "❌"

    # Default/sentinel check
    if default_val is not None and abs(float(value) - float(default_val)) < 1e-9:
        return warn("DEFAULT"), "⚠️"

    return ok("OK"), "✅"


def format_value(v):
    if v is None:
        return err("None")
    if isinstance(v, float):
        if abs(v) >= 100:
            return f"{v:>9.1f}"
        elif abs(v) >= 1:
            return f"{v:>9.4f}"
        else:
            return f"{v:>9.6f}"
    return f"{v:>9}"


def print_audit(json_path: Path):
    with open(json_path, encoding="utf-8") as f:
        d = json.load(f)

    feats = d.get("features", {})
    # Innings: prefer features dict, then JSON flag, then is_second_innings bool
    innings_raw = feats.get("innings") or d.get("innings")
    if innings_raw is None:
        innings = 2 if d.get("is_second_innings") else 1
    else:
        try:
            innings = int(innings_raw)
        except Exception:
            innings = 1

    # ── Header ──────────────────────────────────────────────────────────────
    ts    = d.get("timestamp", "?")
    bat   = d.get("batting_team", "?")
    bowl  = d.get("bowling_team", "?")
    score = d.get("score", "?")
    wkts  = d.get("wickets", "?")
    overs = d.get("overs", "?")
    # JSON key is "target", not "target_runs"
    tgt   = d.get("target") or d.get("target_runs") or "N/A"
    bwp   = d.get("bat_win_prob")
    cal   = d.get("calibrated_win_prob") or d.get("calibrated_per_over_prob")
    calib_chain = d.get("calibration_chain", "")

    print()
    print(bold("═" * 90))
    print(bold(f"  📊 FEATURE AUDIT — {ts}"))
    print(bold("═" * 90))
    print(f"  {'Batting:':<12}{bat}   {score}/{wkts} ({overs} ov)   Inn: {innings}   Target: {tgt}")
    print(f"  {'Bowling:':<12}{bowl}")
    if bwp is not None:
        print(f"  {'Win prob:':<12}{ok(f'{bwp*100:.1f}%')}  cal={ok(f'{cal*100:.1f}%') if cal else '—'}")
    if calib_chain:
        print(f"  {'Cal chain:':<12}{calib_chain}")

    # ── Feature table ────────────────────────────────────────────────────────
    all_feature_names = set(feats.keys()) | set(MODEL_FEATURES)
    # Sort: model features first (ranked), then extras
    ordered = list(MODEL_FEATURES) + sorted(k for k in all_feature_names if k not in MODEL_FEATURES)

    counts = {"✅": 0, "⚠️": 0, "❌": 0, "🔵": 0, "⚪": 0}

    print()
    print(bold(f"  {'#':<4} {'FEATURE':<30} {'VALUE':>12}  {'STATUS':<12}  DESCRIPTION"))
    print("  " + "─" * 86)

    for i, name in enumerate(ordered, 1):
        value = feats.get(name)
        in_model = "★" if name in MODEL_FEATURES else " "
        status_str, flag_char = flag(name, value, innings)
        counts[flag_char] = counts.get(flag_char, 0) + 1
        rule = FEATURE_RULES.get(name)
        desc = rule[4] if rule else dim("(extra)")
        val_str = format_value(value)
        missing = err("MISSING") if value is None else ""
        print(f"  {in_model}{i:<3} {name:<30} {val_str}  {status_str:<20}  {dim(desc)} {missing}")

    # ── Summary ──────────────────────────────────────────────────────────────
    print()
    print("  " + "─" * 86)
    print(f"  ★ = used by model   "
          f"✅ OK:{counts.get('✅',0)}  "
          f"{warn('⚠️  DEFAULT:'+str(counts.get('⚠️',0)))}  "
          f"{err('❌ ZERO!:'+str(counts.get('❌',0)))}  "
          f"{info('🔵 INN2=0✓:'+str(counts.get('🔵',0)))}  "
          f"{dim('⚪ ZERO?:'+str(counts.get('⚪',0)))}")
    print()

    # ── Inn2-specific check block ─────────────────────────────────────────────
    if innings == 2:
        print(bold("  🏏 INN2 SANITY CHECKS"))
        print("  " + "─" * 86)
        checks = [
            # JSON key is "target" not "target_runs"
            ("target (JSON)",        d.get("target") or d.get("target_runs"), lambda v: v is not None and v > 0,   "Must be set"),
            ("inn1_pp_runs",          feats.get("inn1_pp_runs"), lambda v: v not in (None, 45.0),    "Should be actual value, not default 45"),
            ("inn1_death_rr",         feats.get("inn1_death_rr"),lambda v: v not in (None, 9.0),    "Should be actual value, not default 9.0"),
            ("inn1_wickets_lost",     feats.get("inn1_wickets_lost"),lambda v: v not in (None,5.0), "Should be actual wickets (not default 5)"),
            ("inn1_defendability",    feats.get("inn1_defendability"),lambda v: v not in (None,0.5),"Should be calculated, not default 0.5"),
            ("target_above_par",      feats.get("target_above_par"),  lambda v: v not in (None,0.0),"Should be inn1_score – venue_avg"),
            ("required_run_rate",     feats.get("required_run_rate"),  lambda v: v is not None and v > 0, "Must be > 0 in inn2"),
            ("chase_difficulty",      feats.get("chase_difficulty"),  lambda v: v is not None and v > 0, "Must be > 0 in inn2"),
            ("venue_chase_success",   feats.get("venue_chase_success"),lambda v: v not in (None,0.5),"Real venue data, not default 0.5"),
            ("balls_since_wicket",    feats.get("balls_since_wicket"),lambda v: v is not None,       "Counter must be set"),
        ]
        for label, value, test, reason in checks:
            passed = test(value) if value is not None else False
            icon  = ok("✅ PASS") if passed else err("❌ FAIL")
            print(f"  {icon}  {label:<30}  = {format_value(value)}  ({reason})")
        print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json",     default="data/ipl_live_ml.json")
    ap.add_argument("--interval", type=int, default=5)
    ap.add_argument("--once",     action="store_true")
    args = ap.parse_args()

    json_path = Path(args.json)

    # Enable ANSI on Windows
    if sys.platform == "win32":
        os.system("")

    while True:
        if not json_path.exists():
            print(err(f"File not found: {json_path}"))
        else:
            try:
                # Clear screen
                if not args.once:
                    os.system("cls" if sys.platform == "win32" else "clear")
                print_audit(json_path)
            except Exception as e:
                print(err(f"Error reading {json_path}: {e}"))

        if args.once:
            break
        print(dim(f"  Refreshing every {args.interval}s — Ctrl+C to stop"))
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
