"""
Integration test for match state recording and analysis.

Tests end-to-end workflow:
1. Create synthetic match data with features and predictions
2. Use MatchStateLogger to record ~20 balls across 2 innings
3. Finalize match
4. Use StateAnalyzer to consolidate, compute volatility, extract signals, generate calibration report
5. Verify all output files exist with correct schemas
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path
from unittest.mock import Mock

from src.bbl_pipeline.inference.match_state_logger import MatchStateLogger
from src.bbl_pipeline.analysis.state_analyzer import StateAnalyzer


@pytest.fixture
def temp_integration_dir(tmp_path):
    """Create temporary directory for integration test."""
    states_dir = tmp_path / "match_states" / "integration_test"
    states_dir.mkdir(parents=True, exist_ok=True)
    return states_dir


@pytest.fixture
def synthetic_predictor():
    """Create synthetic predictor with calibration attributes."""
    predictor = Mock()
    predictor.last_raw_prob = 0.65
    predictor.last_smoothed_prob = 0.64
    predictor.last_calibrated_combined = 0.63
    predictor.last_calibrated_innings = 0.62
    predictor.last_calibrated_phase = 0.61
    predictor.last_calibrated_per_over = 0.60
    predictor.last_league_calibrated = 0.59
    predictor.last_prediction = 0.59
    return predictor


def create_synthetic_match_state(match_id, innings, over, ball):
    """Create synthetic match state for a single ball."""
    return {
        "match_id": match_id,
        "league": "integration_test",
        "venue": "Integration Test Stadium",
        "batting_team": "Team A" if innings == 1 else "Team B",
        "bowling_team": "Team B" if innings == 1 else "Team A",
        "innings": innings,
        "over": over,
        "ball": ball,
        "runs_this_ball": np.random.choice([0, 1, 2, 4, 6]),
        "wicket_this_ball": False,
        "bat_team_overs": over + ball / 6.0,
        "bat_team_runs": (over - 1) * 12 + ball * 6,
        "bat_team_wickets": min((over - 1) // 3, 9),
        "bowl_team_overs": 0.0 if innings == 1 else over + ball / 6.0,
        "bowl_team_runs": 0 if innings == 1 else 150,
        "bowl_team_wickets": 0 if innings == 1 else 5,
        "team_a": "Team A",
        "team_b": "Team B",
    }


def create_synthetic_features():
    """Create synthetic feature dict."""
    return {
        "resource_win_prob": 0.52 + np.random.uniform(-0.1, 0.1),
        "score_vs_par": np.random.uniform(-10, 10),
        "bat_team_win_rate": 0.65,
        "bowl_team_win_rate": 0.55,
        "venue_bat_first_avg": 165.0,
        "balls_remaining": 86,
        "wickets_in_hand": 9,
        "current_rr": 8.49,
        "required_rr": 0.0,
    }


def create_synthetic_market_odds():
    """Create synthetic market odds dict."""
    return {
        "market_fav_team": "Team A",
        "market_back_odds": 1.75,
        "market_lay_odds": 1.78,
        "market_fav_prob": 0.57 + np.random.uniform(-0.05, 0.05),
    }


class TestEndToEndRecordingAndAnalysis:
    """Integration test for complete match state workflow."""

    def test_full_workflow(self, temp_integration_dir, synthetic_predictor):
        """
        Test complete workflow: record match → consolidate → analyze.
        
        This is the primary integration test validating T038.
        """
        match_id = "integration_test_match"
        
        # Step 1: Create logger
        logger = MatchStateLogger(
            match_id=match_id,
            league="integration_test",
            states_dir=temp_integration_dir,
            model_version="test_v1",
            feature_store_version="test_fs_v1",
        )
        
        # Step 2: Record ~20 balls across 2 innings
        recorded_balls = []
        
        for innings in [1, 2]:
            for over in range(1, 6):  # 5 overs per innings
                for ball in range(1, 3):  # 2 balls per over = 10 balls per innings
                    match_state = create_synthetic_match_state(match_id, innings, over, ball)
                    features = create_synthetic_features()
                    market_odds = create_synthetic_market_odds()
                    
                    # Vary predictor probabilities to simulate match progression
                    synthetic_predictor.last_prediction = 0.59 + np.random.uniform(-0.1, 0.1)
                    
                    # Record ball
                    logger.record_ball(match_state, features, synthetic_predictor, market_odds)
                    recorded_balls.append((innings, over, ball))
        
        # Step 3: Finalize match
        logger.finalize(
            winner="Team A",
            team_a_score=185,
            team_b_score=178,
            result_type="completed",
        )
        
        # Verify match file exists
        match_file = temp_integration_dir / f"{match_id}.parquet"
        assert match_file.exists()
        
        # Verify match metadata exists
        metadata_file = temp_integration_dir / "match_metadata.parquet"
        assert metadata_file.exists()
        
        # Load and verify match data
        match_df = pd.read_parquet(match_file)
        assert len(match_df) == 20  # 10 balls × 2 innings
        assert set(match_df["innings"].unique()) == {1, 2}
        assert "model_prob_final" in match_df.columns
        assert "market_batting_team_prob" in match_df.columns
        assert "deviation" in match_df.columns
        
        # Step 4: Initialize analyzer
        analyzer = StateAnalyzer(league="integration_test", states_dir=temp_integration_dir)
        
        # Verify analyzer discovered the match file
        assert len(analyzer.match_files) == 1
        
        # Step 5: Consolidate matches
        consolidated_df = analyzer.consolidate()
        assert len(consolidated_df) == 20
        assert analyzer.consolidated_file.exists()
        
        # Step 6: Generate calibration report
        results = analyzer.calibration_report()
        
        # Verify report exists
        report_file = temp_integration_dir / "CALIBRATION_REPORT.md"
        assert report_file.exists()
        
        # Verify metrics computed
        assert "overall" in results
        assert "brier" in results["overall"]
        assert "ece" in results["overall"]
        assert "sample_count" in results["overall"]
        
        # Step 7: Compute volatility
        volatility_df = analyzer.compute_volatility()
        assert len(volatility_df) == 1
        assert volatility_df.iloc[0]["match_id"] == match_id
        
        volatility_file = temp_integration_dir / "volatility_profiles.parquet"
        assert volatility_file.exists()
        
        # Step 8: Extract signals
        signals_df = analyzer.extract_signals(deviation_threshold=0.05)
        
        # Should have some signals (deviation > 0.05)
        assert len(signals_df) > 0
        
        signal_file = temp_integration_dir / "signal_events.parquet"
        assert signal_file.exists()
        
        # Verify signal columns
        assert "price_reverted" in signals_df.columns
        assert "reversion_magnitude" in signals_df.columns
        assert "balls_to_reversion" in signals_df.columns
        
        # Step 9: Check meta-model readiness
        readiness = analyzer.meta_model_readiness()
        assert readiness["total_matches"] == 1
        assert readiness["completed_matches"] == 1
        assert readiness["ready_for_meta_model"] == False  # Only 1 match (need 200+)

    def test_multiple_matches_consolidation(self, temp_integration_dir, synthetic_predictor):
        """Test consolidation works correctly with multiple matches."""
        # Record 3 matches
        for match_num in range(1, 4):
            match_id = f"match_{match_num}"
            
            logger = MatchStateLogger(
                match_id=match_id,
                league="integration_test",
                states_dir=temp_integration_dir,
                model_version="test_v1",
                feature_store_version="test_fs_v1",
            )
            
            # Record a few balls
            for over in range(1, 3):
                for ball in range(1, 4):
                    match_state = create_synthetic_match_state(match_id, 1, over, ball)
                    features = create_synthetic_features()
                    market_odds = create_synthetic_market_odds()
                    
                    logger.record_ball(match_state, features, synthetic_predictor, market_odds)
            
            logger.finalize(winner="Team A", team_a_score=200, team_b_score=180, result_type="completed")
        
        # Consolidate
        analyzer = StateAnalyzer(league="integration_test", states_dir=temp_integration_dir)
        assert len(analyzer.match_files) == 3
        
        consolidated = analyzer.consolidate()
        
        # Should have 3 matches × 6 balls = 18 balls
        assert len(consolidated) == 18
        assert consolidated["match_id"].nunique() == 3
        
        # Verify sorting (match_id, innings, over, ball)
        assert consolidated.iloc[0]["match_id"] == "match_1"
        assert consolidated.iloc[-1]["match_id"] == "match_3"

    def test_missing_market_odds_integration(self, temp_integration_dir, synthetic_predictor):
        """Test integration with missing market odds."""
        match_id = "no_odds_match"
        
        logger = MatchStateLogger(
            match_id=match_id,
            league="integration_test",
            states_dir=temp_integration_dir,
            model_version="test_v1",
            feature_store_version="test_fs_v1",
        )
        
        # Record balls with no market odds
        for ball in range(1, 6):
            match_state = create_synthetic_match_state(match_id, 1, 10, ball)
            features = create_synthetic_features()
            
            # Pass None for market odds
            logger.record_ball(match_state, features, synthetic_predictor, None)
        
        logger.finalize(winner=None, team_a_score=None, team_b_score=None, result_type="in_progress")
        
        # Verify file created
        match_file = temp_integration_dir / f"{match_id}.parquet"
        assert match_file.exists()
        
        # Verify market columns are null
        df = pd.read_parquet(match_file)
        assert df["market_batting_team_prob"].isna().all()
        assert df["deviation"].isna().all()
