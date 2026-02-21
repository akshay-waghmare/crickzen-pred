"""
Simulate a rain-reduced BBL match using the reduced-over MC engine.

Match: Sydney Thunder vs Brisbane Heat (BBL 2017-12-27)
- 17 overs per side (reduced from 20 due to rain)
- Thunder batted first: 149/4 in 17 overs
- Heat chased DLS target of 151, scored 153/4 → Won by 6 wickets (D/L)
"""

import json
import numpy as np
from bbl_pipeline.simulation import MatchState, simulate, get_phase
from bbl_pipeline.features.format_config import FormatConfig


def count_legal(delivery: dict) -> int:
    """Return 1 if the delivery is a legal ball, 0 for wides/no-balls."""
    extras = delivery.get("extras", {})
    if "wides" in extras or "noballs" in extras:
        return 0
    return 1


def main():
    with open("bbl_male_json/1114863.json") as f:
        data = json.load(f)

    TOTAL_OVERS = 17
    TOTAL_BALLS = TOTAL_OVERS * 6  # 102
    TARGET = 151

    config = FormatConfig.t20_reduced(TOTAL_OVERS)
    print("=" * 72)
    print("BBL Match 1114863: Sydney Thunder vs Brisbane Heat")
    print(f"Date: 2017-12-27 | Venue: The Gabba, Brisbane")
    print(f"17 overs per side (rain reduced) | DLS target: {TARGET}")
    print(f"FormatConfig: par={config.par_score:.1f}, phases={config.phase_thresholds}")
    print("=" * 72)
    print()

    # =============================================
    # INNINGS 1: Sydney Thunder batting
    # =============================================
    header = f"{'Over':>6} | {'Score':>8} | {'Phase':>10} | {'MC Win%':>10} | {'Event':>8}"
    sep = "-" * 60

    print("INNINGS 1: Sydney Thunder batting")
    print(header)
    print(sep)

    inn1 = data["innings"][0]
    score = 0
    wickets = 0
    legal_balls = 0

    for ov in inn1["overs"]:
        for d in ov["deliveries"]:
            runs = d["runs"]["total"]
            is_wkt = bool(d.get("wickets"))
            legal_balls += count_legal(d)
            score += runs
            if is_wkt:
                wickets += 1

            balls_remaining = max(0, TOTAL_BALLS - legal_balls)

            if (legal_balls % 6 == 0 or is_wkt) and balls_remaining > 0:
                state = MatchState(
                    innings=1,
                    score=score,
                    wickets_lost=min(wickets, 9),
                    balls_remaining=balls_remaining,
                    batting_team="Sydney Thunder",
                    bowling_team="Brisbane Heat",
                    league="bbl",
                    total_balls=TOTAL_BALLS,
                )
                np.random.seed(42)
                result = simulate(state, horizon=6, n_simulations=1000)
                phase = get_phase(balls_remaining, total_balls=TOTAL_BALLS)
                event = "WICKET" if is_wkt else f"+{runs}"
                ov_d = f"{legal_balls // 6}.{legal_balls % 6}"
                print(
                    f"{ov_d:>6} | {score}/{wickets:>2}    | {phase:>10} | "
                    f"{result.mean_prob:>9.1%} | {event:>8}"
                )

    print(f"\n  Sydney Thunder: {score}/{wickets} in {TOTAL_OVERS} overs\n")

    # =============================================
    # INNINGS 2: Brisbane Heat chasing
    # =============================================
    header2 = (
        f"{'Over':>6} | {'Score':>8} | {'Phase':>10} | "
        f"{'MC Win%':>10} | {'RRR':>6} | {'Event':>8}"
    )
    sep2 = "-" * 72

    print(f"INNINGS 2: Brisbane Heat chasing {TARGET} (DLS)")
    print(header2)
    print(sep2)

    inn2 = data["innings"][1]
    score = 0
    wickets = 0
    legal_balls = 0

    for ov in inn2["overs"]:
        for d in ov["deliveries"]:
            runs = d["runs"]["total"]
            is_wkt = bool(d.get("wickets"))
            legal_balls += count_legal(d)
            score += runs
            if is_wkt:
                wickets += 1

            balls_remaining = max(0, TOTAL_BALLS - legal_balls)

            if (
                (legal_balls % 6 == 0 or is_wkt)
                and balls_remaining > 0
                and score < TARGET
            ):
                state = MatchState(
                    innings=2,
                    score=score,
                    wickets_lost=min(wickets, 9),
                    balls_remaining=balls_remaining,
                    target_runs=TARGET,
                    batting_team="Brisbane Heat",
                    bowling_team="Sydney Thunder",
                    league="bbl",
                    total_balls=TOTAL_BALLS,
                )
                np.random.seed(42)
                result = simulate(state, horizon=6, n_simulations=1000)
                phase = get_phase(balls_remaining, total_balls=TOTAL_BALLS)
                runs_needed = TARGET - score
                overs_left = balls_remaining / 6
                rrr = runs_needed / overs_left if overs_left > 0 else 0
                event = "WICKET" if is_wkt else f"+{runs}"
                ov_d = f"{legal_balls // 6}.{legal_balls % 6}"
                print(
                    f"{ov_d:>6} | {score}/{wickets:>2}    | {phase:>10} | "
                    f"{result.mean_prob:>9.1%} | {rrr:>5.1f} | {event:>8}"
                )

    print()
    print("=" * 72)
    print(f"RESULT: Brisbane Heat {score}/{wickets} - WON by {10 - wickets} wickets (D/L)")
    print(f"Match: 17 overs per side (reduced from 20 due to rain)")
    print("=" * 72)


if __name__ == "__main__":
    main()
