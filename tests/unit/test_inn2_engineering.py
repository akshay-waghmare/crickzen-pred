import math
import sys
from pathlib import Path

import pandas as pd

PROJECT_SRC = Path(__file__).resolve().parents[2] / "src"
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))

from bbl_pipeline.features.inn2_engineering import engineer_inn2_features


def test_engineer_inn2_features_adds_phase_router_training_fields():
    row = pd.DataFrame(
        [
            {
                "innings": 2.0,
                "over": 12.0,
                "ball": 5.0,
                "target_above_par": 5.0,
                "overs_remaining": 7.166666666666667,
                "wickets_lost": 2.0,
                "required_run_rate": 8.0,
                "current_run_rate": 9.0,
                "run_rate_diff": 1.0,
                "score_vs_par": 8.0,
                "resources_remaining": 0.5,
                "resource_pct": 0.45,
                "pressure_index": 9.2,
                "dls_pressure_index": 0.42,
                "runs_last_12": 22.0,
                "runs_last_18": 32.0,
                "wickets_last_12": 0.0,
                "wickets_last_6": 0.0,
                "dot_pct_last_12": 0.25,
                "boundary_pct_last_18": 0.22,
                "balls_since_wicket": 31.0,
                "set_batter_exposure": 30.0,
                "batting_pair_strength": 54.0,
                "team_strength_diff": 0.0,
                "crr_times_res": 4.5,
                "acceleration_potential": 10.0,
                "inn1_defendability": 0.5,
                "inn1_pp_runs": 50.0,
                "inn1_death_rr": 10.0,
                "inn1_wickets_lost": 7.0,
                "resource_win_prob": 0.55,
                "venue_chase_success": 0.5,
            }
        ]
    )

    engineered = engineer_inn2_features(row).iloc[0]

    assert math.isclose(engineered["target_clarity_index"], 5.0 / (7.166666666666667 + 1.0))
    assert math.isclose(engineered["wicket_budget_remaining"], 8.0 - (7.166666666666667 * 0.4))
    assert engineered["early_settle_flag"] == 1.0
    assert math.isclose(engineered["late_mid_run_gap"], 22.0 - (8.0 * 2.0))
    assert engineered["momentum_shift_flag"] == 0.0
    assert engineered["acceleration_zone"] == 0.0
    assert engineered["late_wkt_collapse_risk"] == 0.0
