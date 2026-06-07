from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd


def _build_training_rows() -> pd.DataFrame:
    rows = []
    season_by_match = {
        "9001": "2023",
        "9002": "2023",
        "9003": "2024",
        "9004": "2024",
        "9005": "2025",
        "9006": "2025",
        "9007": "2026",
        "9008": "2026",
    }
    for match_num, match_id in enumerate(season_by_match):
        winner = "MI" if match_num % 2 == 0 else "CSK"
        for innings in [1, 2]:
            batting_team = "MI" if innings == 1 else "CSK"
            bowling_team = "CSK" if innings == 1 else "MI"
            for over in range(1, 7):
                rows.append(
                    {
                        "bowler_rolling_econ": 7.0 + over * 0.1,
                        "batsman_rolling_sr": 110 + over * 2 + innings,
                        "batting_pair_strength": 20 + over + innings,
                        "bowler_vs_team_econ": 7.1,
                        "batsman_venue_sr": 105 + over,
                        "batsman_rolling_avg": 25 + innings,
                        "bowler_venue_econ": 7.3,
                        "batsman_vs_team_avg": 30 + over,
                        "batsman_venue_avg": 28 + innings,
                        "bowler_rolling_sr": 20 + over,
                        "bowler_venue_sr": 22 + innings,
                        "score_vs_par": -5 + over,
                        "required_run_rate": 8.5 - innings,
                        "pressure_index": 0.1 * over,
                        "run_rate_diff": 0.2 * innings,
                        "chase_difficulty": 0.3 * innings,
                        "current_run_rate": 6 + over * 0.4,
                        "resources_remaining": 1 - over * 0.03,
                        "wickets_lost": min(over // 3, 4),
                        "projected_vs_venue_avg": 5 + over,
                        "team_strength_diff": 0.2 if winner == batting_team else -0.2,
                        "runs_last_12": 10 + over,
                        "runs_last_18": 14 + over,
                        "wickets_last_12": over % 2,
                        "boundary_pct_last_18": 0.2 + (over % 3) * 0.1,
                        "batting_team_win_rate": 0.55 if batting_team == "MI" else 0.48,
                        "bowling_team_win_rate": 0.48 if bowling_team == "CSK" else 0.55,
                        "batting_team_situation_wr": 0.5 + over * 0.01,
                        "bowling_team_situation_wr": 0.45 + innings * 0.02,
                        "situation_advantage": 0.05 * over,
                        "acceleration_potential": 0.2 + over * 0.05,
                        "wickets_last_30": min(over // 2, 3),
                        "projected_score": 140 + over * 4,
                        "score_per_wicket": 25 + over,
                        "rrr_times_wickets": 8 + over,
                        "wickets_times_balls": (min(over // 3, 4)) * (120 - over * 6),
                        "crr_times_res": (6 + over * 0.4) * (1 - over * 0.03),
                        "resource_pct": 95 - over * 3,
                        "expected_final_score": 150 + over * 3,
                        "dls_pressure_index": 0.02 * over,
                        "resource_win_prob": 0.52 + (0.02 if winner == batting_team else -0.02) + over * 0.005,
                        "overs_remaining": float(20 - over),
                        "is_powerplay": 1 if over <= 6 else 0,
                        "is_middle_overs": 0,
                        "is_death_overs": 0,
                        "innings": innings,
                        "score_adjusted_by_team": 1.5 * over,
                        "projected_adjusted": 145 + over * 4,
                        "resource_team_adjusted": 0.5 + over * 0.01,
                        "run_rate_team_adj": 6.0 + over * 0.3,
                        "inn1_defendability": 0.5,
                        "target_above_par": 5.0,
                        "inn1_wickets_lost": 5.0,
                        "inn1_death_rr": 9.0,
                        "inn1_pp_runs": 45.0,
                        "venue_chase_success": 0.52,
                        "batting_won_toss": 1 if match_num % 2 == 0 else 0,
                        "is_winner": 1 if batting_team == winner else 0,
                        "match_id": match_id,
                        "season": season_by_match[match_id],
                        "over": over,
                        "ball": 6,
                        "batting_team": batting_team,
                        "bowling_team": bowling_team,
                        "winner": winner,
                    }
                )
    return pd.DataFrame(rows)


def test_state_embeddings_experiment_end_to_end(tmp_path: Path):
    feature_dir = tmp_path / "data" / "ipl_features_v6"
    feature_dir.mkdir(parents=True)
    raw_backfill_dir = tmp_path / "data" / "ipl_raw" / "matches"
    raw_backfill_dir.mkdir(parents=True)
    json_dir = tmp_path / "ipl_male_json"
    json_dir.mkdir()

    training_df = _build_training_rows()
    sampled_df = training_df.drop(columns=["match_id", "season", "over", "ball", "batting_team", "bowling_team", "winner"]).iloc[::2].reset_index(drop=True)
    training_df.to_parquet(feature_dir / "training.parquet", index=False)
    sampled_df.to_parquet(feature_dir / "training_sampled.parquet", index=False)

    for match_id in training_df["match_id"].unique():
        season = training_df.loc[training_df["match_id"] == match_id, "season"].iloc[0]
        (json_dir / f"{match_id}.json").write_text(
            json.dumps({"info": {"dates": [f"{season}-04-01"], "venue": "Wankhede", "season": season}}),
            encoding="utf-8",
        )

    output_dir = tmp_path / "experiments" / "ipl_state_embeddings_v1"
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "scripts" / "analyze_ipl_state_embeddings_experiment.py"

    completed = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--input",
            str(feature_dir / "training_sampled.parquet"),
            "--raw-backfill-dir",
            str(raw_backfill_dir),
            "--output-dir",
            str(output_dir),
            "--mode",
            "pilot",
            "--seed",
            "42",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )

    assert "Experiment complete." in completed.stdout
    assert (output_dir / "corpus" / "embedding_corpus.parquet").exists()
    assert (output_dir / "regimes" / "regime_assignments.parquet").exists()
    assert (output_dir / "retrieval" / "analogue_results.parquet").exists()
    assert (output_dir / "features" / "regime_features.parquet").exists()
    assert (output_dir / "evaluation" / "metrics.csv").exists()
    assert (output_dir / "evaluation" / "segment_metrics.csv").exists()
    assert (output_dir / "evaluation" / "reliability_bins.csv").exists()
    assert (output_dir / "evaluation" / "calibration_guardrails.csv").exists()
    assert (output_dir / "evaluation" / "calibration_summary.csv").exists()
    assert (output_dir / "evaluation" / "season_slice_metrics.csv").exists()
    assert (output_dir / "evaluation" / "season_slice_segment_metrics.csv").exists()
    assert (output_dir / "evaluation" / "season_slice_reliability_bins.csv").exists()
    assert (output_dir / "evaluation" / "season_slice_calibration_guardrails.csv").exists()
    assert (output_dir / "evaluation" / "season_slice_calibration_summary.csv").exists()
    assert (output_dir / "evaluation" / "inn2_powerplay_predictions.csv").exists()
    assert (output_dir / "evaluation" / "inn2_powerplay_overconfident_wrongs.csv").exists()
    assert (output_dir / "evaluation" / "inn2_powerplay_reliability_bins.csv").exists()
    assert (output_dir / "evaluation" / "inn2_powerplay_cluster_behavior.csv").exists()
    assert (output_dir / "evaluation" / "inn2_powerplay_cluster_behavior_2025_2026.csv").exists()
    assert (output_dir / "evaluation" / "inn2_powerplay_cluster_stability_2025_2026.csv").exists()
    assert (output_dir / "evaluation" / "inn2_powerplay_cluster_stability_2025_2026.json").exists()
    assert (output_dir / "evaluation" / "INNINGS2_POWERPLAY_DIAGNOSTICS.md").exists()
    assert (output_dir / "evaluation" / "PILOT_REPORT.md").exists()

    metrics_df = pd.read_csv(output_dir / "evaluation" / "metrics.csv")
    assert set(metrics_df["method"]) >= {
        "baseline_ipl_v6_features",
        "regime_retrieval_features",
        "regime_cluster_features",
        "v18A_hard_pp_fallback",
        "v18B_confidence_cap",
        "v18C_dominant_cluster_only",
        "regime_hybrid_features",
        "guarded_regime_phase_calibration",
    }
    assert {
        "baseline_brier_delta",
        "baseline_log_loss_delta",
        "baseline_ece_delta",
        "cluster_winner_brier_delta",
        "cluster_winner_log_loss_delta",
        "cluster_winner_ece_delta",
    } <= set(metrics_df.columns)

    season_slice_df = pd.read_csv(output_dir / "evaluation" / "season_slice_metrics.csv")
    assert set(season_slice_df["split"]) >= {"season_2024", "season_2025", "season_2026"}
    assert set(season_slice_df["method"]) >= {
        "baseline_ipl_v6_features",
        "regime_cluster_features",
        "v18A_hard_pp_fallback",
        "v18B_confidence_cap",
        "v18C_dominant_cluster_only",
        "guarded_regime_phase_calibration",
    }
    assert {
        "baseline_brier_delta",
        "baseline_log_loss_delta",
        "baseline_ece_delta",
        "cluster_winner_brier_delta",
        "cluster_winner_log_loss_delta",
        "cluster_winner_ece_delta",
    } <= set(season_slice_df.columns)

    calibration_summary_df = pd.read_csv(output_dir / "evaluation" / "calibration_summary.csv")
    assert set(calibration_summary_df["method"]) >= {"guarded_regime_phase_calibration"}
    assert {"candidate_slices", "fitted_slices", "applied_share", "skip_reason_counts"} <= set(calibration_summary_df.columns)

    pp_reliability_df = pd.read_csv(output_dir / "evaluation" / "inn2_powerplay_reliability_bins.csv")
    assert set(pp_reliability_df["method"]) == {
        "baseline_ipl_v6_features",
        "regime_cluster_features",
        "v18A_hard_pp_fallback",
        "v18B_confidence_cap",
        "v18C_dominant_cluster_only",
    }

    pp_predictions_df = pd.read_csv(output_dir / "evaluation" / "inn2_powerplay_predictions.csv")
    assert set(pp_predictions_df["method"]) == {
        "baseline_ipl_v6_features",
        "regime_cluster_features",
        "v18A_hard_pp_fallback",
        "v18B_confidence_cap",
        "v18C_dominant_cluster_only",
    }
    assert {"route_source", "route_reason", "baseline_predicted_prob", "cluster_predicted_prob"} <= set(pp_predictions_df.columns)

    recent_summary = json.loads((output_dir / "evaluation" / "inn2_powerplay_cluster_stability_2025_2026.json").read_text(encoding="utf-8"))
    assert recent_summary["recent_seasons"] == ["2025", "2026"]

    report_text = (output_dir / "evaluation" / "PILOT_REPORT.md").read_text(encoding="utf-8")
    assert "Season-Slice Validation" in report_text
    assert "v18A_hard_pp_fallback" in report_text
    assert "v18B_confidence_cap" in report_text
    assert "v18C_dominant_cluster_only" in report_text
    assert "Regime-Conditioned Calibration Guardrails" in report_text
    assert "season_2024" in report_text
    assert "NO-GO" in report_text or "GO" in report_text

    pp_report_text = (output_dir / "evaluation" / "INNINGS2_POWERPLAY_DIAGNOSTICS.md").read_text(encoding="utf-8")
    assert "Innings 2 Powerplay Diagnostics" in pp_report_text
