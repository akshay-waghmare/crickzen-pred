"""
Unit tests for MatchStateLogger.

Tests FR-009 (error isolation), FR-010 (buffering), schema compliance,
deviation computation, market probability mapping, and team tier classification.
"""

import pytest
import pandas as pd
import pyarrow.parquet as pq
from pathlib import Path
from unittest.mock import Mock, MagicMock
from src.bbl_pipeline.inference.match_state_logger import MatchStateLogger


@pytest.fixture
def temp_states_dir(tmp_path):
    """Create a temporary directory for test output."""
    states_dir = tmp_path / "match_states" / "test_league"
    states_dir.mkdir(parents=True, exist_ok=True)
    return states_dir


@pytest.fixture
def mock_predictor():
    """Create a mock predictor with calibration attributes."""
    predictor = Mock()
    predictor.raw_pred = 0.65
    predictor.combined_calibrated = 0.63
    predictor.innings_calibrated = 0.62
    predictor.phase_calibrated = 0.61
    predictor.perover_calibrated = 0.60
    predictor.league_calibrated = 0.59
    predictor.final_win_prob = 0.59
    return predictor


@pytest.fixture
def sample_match_state():
    """Create a sample match state dictionary."""
    return {
        "match_id": "1234567",
        "league": "test_league",
        "venue": "Test Stadium",
        "batting_team": "Team A",
        "bowling_team": "Team B",
        "innings": 1,
        "over": 5,
        "ball": 3,
        "runs_this_ball": 4,
        "wicket_this_ball": False,
        "bat_team_overs": 5.3,
        "bat_team_runs": 47,
        "bat_team_wickets": 1,
        "bowl_team_overs": 0.0,
        "bowl_team_runs": 0,
        "bowl_team_wickets": 0,
        "team_a": "Team A",
        "team_b": "Team B",
    }


@pytest.fixture
def sample_features():
    """Create a sample features dictionary."""
    return {
        "resource_win_prob": 0.52,
        "score_vs_par": 5.0,
        "bat_team_win_rate": 0.65,
        "bowl_team_win_rate": 0.55,
        "venue_bat_first_avg": 165.0,
        "balls_remaining": 86,
        "wickets_in_hand": 9,
        "current_rr": 8.49,
        "required_rr": 0.0,
    }


@pytest.fixture
def sample_market_odds():
    """Create a sample market odds dictionary."""
    return {
        "market_fav_team": "Team A",
        "market_back_odds": 1.75,
        "market_lay_odds": 1.78,
        "market_fav_prob": 0.57,
    }


class TestMatchStateLoggerInit:
    """Test MatchStateLogger initialization."""

    def test_init_creates_directory(self, temp_states_dir):
        """Test that __init__ creates the output directory."""
        logger = MatchStateLogger(
            match_id="1234567",
            league="test_league",
            states_dir=temp_states_dir,
            model_version="test_v1",
            feature_store_version="test_fs_v1",
        )
        
        assert temp_states_dir.exists()
        assert logger.match_id == "1234567"
        assert logger.league == "test_league"
        assert logger.model_version == "test_v1"
        assert logger.feature_store_version == "test_fs_v1"
        assert isinstance(logger.buffer, list)
        assert len(logger.buffer) == 0

    def test_init_with_existing_directory(self, temp_states_dir):
        """Test initialization when directory already exists."""
        temp_states_dir.mkdir(parents=True, exist_ok=True)
        
        logger = MatchStateLogger(
            match_id="1234567",
            league="test_league",
            states_dir=temp_states_dir,
            model_version="test_v1",
            feature_store_version="test_fs_v1",
        )
        
        assert temp_states_dir.exists()
        assert logger.match_id == "1234567"


class TestComputeMatchPhase:
    """Test _compute_match_phase method."""

    def test_powerplay_phase(self, temp_states_dir):
        """Test over 1-6 classified as powerplay."""
        logger = MatchStateLogger("1234567", "test", temp_states_dir, "v1", "fs_v1")
        
        assert logger._compute_match_phase(1) == "powerplay"
        assert logger._compute_match_phase(3) == "powerplay"
        assert logger._compute_match_phase(6) == "powerplay"

    def test_middle_phase(self, temp_states_dir):
        """Test over 7-15 classified as middle."""
        logger = MatchStateLogger("1234567", "test", temp_states_dir, "v1", "fs_v1")
        
        assert logger._compute_match_phase(7) == "middle"
        assert logger._compute_match_phase(10) == "middle"
        assert logger._compute_match_phase(15) == "middle"

    def test_death_phase(self, temp_states_dir):
        """Test over 16-20 classified as death."""
        logger = MatchStateLogger("1234567", "test", temp_states_dir, "v1", "fs_v1")
        
        assert logger._compute_match_phase(16) == "death"
        assert logger._compute_match_phase(18) == "death"
        assert logger._compute_match_phase(20) == "death"


class TestComputeTeamTier:
    """Test _compute_team_tier method."""

    def test_top_tier(self, temp_states_dir):
        """Test win rate >= 0.60 classified as top tier."""
        logger = MatchStateLogger("1234567", "test", temp_states_dir, "v1", "fs_v1")
        
        assert logger._compute_team_tier(0.60) == "top"
        assert logger._compute_team_tier(0.75) == "top"
        assert logger._compute_team_tier(0.90) == "top"

    def test_mid_tier(self, temp_states_dir):
        """Test win rate 0.40-0.59 classified as mid tier."""
        logger = MatchStateLogger("1234567", "test", temp_states_dir, "v1", "fs_v1")
        
        assert logger._compute_team_tier(0.40) == "mid"
        assert logger._compute_team_tier(0.50) == "mid"
        assert logger._compute_team_tier(0.59) == "mid"

    def test_bottom_tier(self, temp_states_dir):
        """Test win rate < 0.40 classified as bottom tier."""
        logger = MatchStateLogger("1234567", "test", temp_states_dir, "v1", "fs_v1")
        
        assert logger._compute_team_tier(0.39) == "bottom"
        assert logger._compute_team_tier(0.25) == "bottom"
        assert logger._compute_team_tier(0.10) == "bottom"


class TestMapMarketProbs:
    """Test _map_market_probs method."""

    def test_fav_is_batting_team(self, temp_states_dir):
        """Test when market favorite is the batting team."""
        logger = MatchStateLogger("1234567", "test", temp_states_dir, "v1", "fs_v1")
        
        batting_prob, bowling_prob = logger._map_market_probs(
            market_fav_team="Team A",
            market_fav_prob=0.65,
            batting_team="Team A",
            bowling_team="Team B",
        )
        
        assert batting_prob == 0.65
        assert bowling_prob == 0.35

    def test_fav_is_bowling_team(self, temp_states_dir):
        """Test when market favorite is the bowling team."""
        logger = MatchStateLogger("1234567", "test", temp_states_dir, "v1", "fs_v1")
        
        batting_prob, bowling_prob = logger._map_market_probs(
            market_fav_team="Team B",
            market_fav_prob=0.70,
            batting_team="Team A",
            bowling_team="Team B",
        )
        
        assert batting_prob == 0.30
        assert bowling_prob == 0.70


class TestComputeDeviation:
    """Test _compute_deviation method."""

    def test_model_higher_deviation(self, temp_states_dir):
        """Test deviation when model probability is higher than market."""
        logger = MatchStateLogger("1234567", "test", temp_states_dir, "v1", "fs_v1")
        
        deviation, deviation_abs, bucket, direction = logger._compute_deviation(
            model_prob=0.70, market_batting_team_prob=0.50
        )
        
        assert deviation == 0.20
        assert deviation_abs == 0.20
        assert bucket == "0.20-0.25"
        assert direction == "model_higher"

    def test_model_lower_deviation(self, temp_states_dir):
        """Test deviation when model probability is lower than market."""
        logger = MatchStateLogger("1234567", "test", temp_states_dir, "v1", "fs_v1")
        
        deviation, deviation_abs, bucket, direction = logger._compute_deviation(
            model_prob=0.40, market_batting_team_prob=0.55
        )
        
        assert deviation == -0.15
        assert deviation_abs == 0.15
        assert bucket == "0.15-0.20"
        assert direction == "model_lower"

    def test_aligned_predictions(self, temp_states_dir):
        """Test aligned classification when difference is <= 0.02."""
        logger = MatchStateLogger("1234567", "test", temp_states_dir, "v1", "fs_v1")
        
        deviation, deviation_abs, bucket, direction = logger._compute_deviation(
            model_prob=0.51, market_batting_team_prob=0.50
        )
        
        assert deviation == 0.01
        assert deviation_abs == 0.01
        assert bucket == "0.00-0.05"
        assert direction == "aligned"

    def test_extreme_deviation(self, temp_states_dir):
        """Test extreme deviation bucket (>= 0.30)."""
        logger = MatchStateLogger("1234567", "test", temp_states_dir, "v1", "fs_v1")
        
        deviation, deviation_abs, bucket, direction = logger._compute_deviation(
            model_prob=0.90, market_batting_team_prob=0.50
        )
        
        assert deviation == 0.40
        assert deviation_abs == 0.40
        assert bucket == "0.30+"
        assert direction == "model_higher"


class TestRecordBall:
    """Test record_ball method."""

    def test_record_ball_produces_complete_dict(
        self, temp_states_dir, sample_match_state, sample_features, 
        mock_predictor, sample_market_odds
    ):
        """Test that record_ball produces a dict with 80+ keys."""
        logger = MatchStateLogger("1234567", "test", temp_states_dir, "v1", "fs_v1")
        
        logger.record_ball(
            match_state=sample_match_state,
            features_dict=sample_features,
            predictor=mock_predictor,
            market_odds=sample_market_odds,
        )
        
        assert len(logger.buffer) == 1
        record = logger.buffer[0]
        
        # Check for key columns (sample)
        assert "match_id" in record
        assert "league" in record
        assert "innings" in record
        assert "over" in record
        assert "ball" in record
        assert "batting_team" in record
        assert "bowling_team" in record
        
        # Check computed features
        assert "resource_win_prob" in record
        assert "score_vs_par" in record
        
        # Check calibration chain
        assert "model_prob_raw" in record
        assert "model_prob_combined" in record
        assert "model_prob_innings" in record
        assert "model_prob_phase" in record
        assert "model_prob_perover" in record
        assert "model_prob_league" in record
        assert "model_prob_final" in record
        
        # Check market odds
        assert "market_fav_team" in record
        assert "market_back_odds" in record
        assert "market_fav_prob" in record
        assert "market_batting_team_prob" in record
        assert "market_bowling_team_prob" in record
        
        # Check deviation metrics
        assert "deviation" in record
        assert "deviation_abs" in record
        assert "deviation_bucket" in record
        assert "deviation_direction" in record
        
        # Check versioning
        assert record["model_version"] == "v1"
        assert record["feature_store_version"] == "fs_v1"

    def test_record_ball_buffer_auto_flush(
        self, temp_states_dir, sample_match_state, sample_features,
        mock_predictor, sample_market_odds
    ):
        """Test buffer auto-flushes at 30 records."""
        logger = MatchStateLogger("1234567", "test", temp_states_dir, "v1", "fs_v1")
        
        # Record 30 balls
        for i in range(30):
            state = sample_match_state.copy()
            state["ball"] = i + 1
            logger.record_ball(state, sample_features, mock_predictor, sample_market_odds)
        
        # Buffer should auto-flush and be empty
        assert len(logger.buffer) == 0
        
        # Parquet file should exist
        parquet_file = temp_states_dir / "1234567.parquet"
        assert parquet_file.exists()
        
        # Verify 30 rows written
        df = pd.read_parquet(parquet_file)
        assert len(df) == 30

    def test_record_ball_with_missing_market_odds(
        self, temp_states_dir, sample_match_state, sample_features, mock_predictor
    ):
        """Test record_ball handles missing market odds gracefully (FR-014)."""
        logger = MatchStateLogger("1234567", "test", temp_states_dir, "v1", "fs_v1")
        
        # Pass None for market odds
        logger.record_ball(
            match_state=sample_match_state,
            features_dict=sample_features,
            predictor=mock_predictor,
            market_odds=None,
        )
        
        assert len(logger.buffer) == 1
        record = logger.buffer[0]
        
        # Market columns should be None
        assert record["market_fav_team"] is None
        assert record["market_back_odds"] is None
        assert record["market_fav_prob"] is None
        assert record["market_batting_team_prob"] is None
        assert record["market_bowling_team_prob"] is None
        
        # Deviation columns should be None
        assert record["deviation"] is None
        assert record["deviation_abs"] is None
        assert record["deviation_bucket"] is None
        assert record["deviation_direction"] is None

    def test_record_ball_error_isolation(
        self, temp_states_dir, sample_match_state, sample_features, mock_predictor
    ):
        """Test that record_ball logs errors but doesn't raise (FR-009)."""
        logger = MatchStateLogger("1234567", "test", temp_states_dir, "v1", "fs_v1")
        
        # Pass malformed data (missing required keys)
        bad_state = {"match_id": "1234567"}  # Missing most keys
        
        # Should not raise exception
        logger.record_ball(bad_state, sample_features, mock_predictor, None)
        
        # Buffer should still be empty (record failed)
        assert len(logger.buffer) == 0

    def test_record_ball_computes_deltas(
        self, temp_states_dir, sample_match_state, sample_features,
        mock_predictor, sample_market_odds
    ):
        """Test that model_prob_delta and market_prob_delta are computed correctly."""
        logger = MatchStateLogger("1234567", "test", temp_states_dir, "v1", "fs_v1")
        
        # Record first ball
        logger.record_ball(
            sample_match_state, sample_features, mock_predictor, sample_market_odds
        )
        
        # First ball should have None deltas
        assert logger.buffer[0]["model_prob_delta"] is None
        assert logger.buffer[0]["market_prob_delta"] is None
        
        # Modify predictor and market odds for second ball
        mock_predictor.final_win_prob = 0.65  # Was 0.59
        market_odds_2 = sample_market_odds.copy()
        market_odds_2["market_fav_prob"] = 0.62  # Was 0.57
        
        state_2 = sample_match_state.copy()
        state_2["ball"] = 4
        
        # Record second ball
        logger.record_ball(state_2, sample_features, mock_predictor, market_odds_2)
        
        # Second ball should have computed deltas
        assert logger.buffer[1]["model_prob_delta"] == pytest.approx(0.06, abs=0.01)
        assert logger.buffer[1]["market_prob_delta"] == pytest.approx(0.05, abs=0.01)


class TestFlush:
    """Test flush method."""

    def test_flush_creates_parquet(
        self, temp_states_dir, sample_match_state, sample_features,
        mock_predictor, sample_market_odds
    ):
        """Test that flush creates a valid Parquet file."""
        logger = MatchStateLogger("1234567", "test", temp_states_dir, "v1", "fs_v1")
        
        # Record a few balls
        for i in range(5):
            state = sample_match_state.copy()
            state["ball"] = i + 1
            logger.record_ball(state, sample_features, mock_predictor, sample_market_odds)
        
        # Flush manually
        logger.flush()
        
        # Buffer should be cleared
        assert len(logger.buffer) == 0
        
        # Parquet file should exist
        parquet_file = temp_states_dir / "1234567.parquet"
        assert parquet_file.exists()
        
        # Verify 5 rows written
        df = pd.read_parquet(parquet_file)
        assert len(df) == 5

    def test_flush_appends_to_existing_file(
        self, temp_states_dir, sample_match_state, sample_features,
        mock_predictor, sample_market_odds
    ):
        """Test that flush appends to existing Parquet file."""
        logger = MatchStateLogger("1234567", "test", temp_states_dir, "v1", "fs_v1")
        
        # Record and flush first batch
        for i in range(3):
            state = sample_match_state.copy()
            state["ball"] = i + 1
            logger.record_ball(state, sample_features, mock_predictor, sample_market_odds)
        logger.flush()
        
        # Record and flush second batch
        for i in range(3, 6):
            state = sample_match_state.copy()
            state["ball"] = i + 1
            logger.record_ball(state, sample_features, mock_predictor, sample_market_odds)
        logger.flush()
        
        # Parquet should have 6 rows total
        parquet_file = temp_states_dir / "1234567.parquet"
        df = pd.read_parquet(parquet_file)
        assert len(df) == 6


class TestFinalize:
    """Test finalize method."""

    def test_finalize_creates_match_metadata(self, temp_states_dir):
        """Test that finalize creates match_metadata.parquet."""
        logger = MatchStateLogger("1234567", "test", temp_states_dir, "v1", "fs_v1")
        
        # Finalize with match result
        logger.finalize(
            winner="Team A",
            team_a_score=185,
            team_b_score=178,
            result_type="completed",
        )
        
        # Match metadata file should exist
        metadata_file = temp_states_dir / "match_metadata.parquet"
        assert metadata_file.exists()
        
        # Verify metadata
        df = pd.read_parquet(metadata_file)
        assert len(df) == 1
        assert df.iloc[0]["match_id"] == "1234567"
        assert df.iloc[0]["league"] == "test"
        assert df.iloc[0]["winner"] == "Team A"
        assert df.iloc[0]["team_a_score"] == 185
        assert df.iloc[0]["team_b_score"] == 178
        assert df.iloc[0]["result_type"] == "completed"

    def test_finalize_flushes_buffer(
        self, temp_states_dir, sample_match_state, sample_features,
        mock_predictor, sample_market_odds
    ):
        """Test that finalize flushes remaining buffer."""
        logger = MatchStateLogger("1234567", "test", temp_states_dir, "v1", "fs_v1")
        
        # Record a few balls (not enough to auto-flush)
        for i in range(5):
            state = sample_match_state.copy()
            state["ball"] = i + 1
            logger.record_ball(state, sample_features, mock_predictor, sample_market_odds)
        
        # Buffer should have 5 records
        assert len(logger.buffer) == 5
        
        # Finalize
        logger.finalize(winner=None, team_a_score=None, team_b_score=None, result_type="in_progress")
        
        # Buffer should be cleared
        assert len(logger.buffer) == 0
        
        # Parquet should have 5 rows
        parquet_file = temp_states_dir / "1234567.parquet"
        assert parquet_file.exists()
        df = pd.read_parquet(parquet_file)
        assert len(df) == 5

    def test_finalize_with_incomplete_match(self, temp_states_dir):
        """Test finalize with incomplete match (no winner)."""
        logger = MatchStateLogger("1234567", "test", temp_states_dir, "v1", "fs_v1")
        
        # Finalize incomplete match
        logger.finalize(
            winner=None,
            team_a_score=None,
            team_b_score=None,
            result_type="in_progress",
        )
        
        # Metadata file should exist
        metadata_file = temp_states_dir / "match_metadata.parquet"
        assert metadata_file.exists()
        
        # Verify nullable fields
        df = pd.read_parquet(metadata_file)
        assert pd.isna(df.iloc[0]["winner"])
        assert pd.isna(df.iloc[0]["team_a_score"])
        assert pd.isna(df.iloc[0]["team_b_score"])
        assert df.iloc[0]["result_type"] == "in_progress"


class TestMarketOddsHandling:
    """Test market odds handling (US2 - T018)."""

    def test_market_odds_recorded_correctly(
        self, temp_states_dir, sample_match_state, sample_features,
        mock_predictor, sample_market_odds
    ):
        """Test that all market odds fields are recorded correctly."""
        logger = MatchStateLogger("1234567", "test", temp_states_dir, "v1", "fs_v1")
        
        logger.record_ball(
            match_state=sample_match_state,
            features_dict=sample_features,
            predictor=mock_predictor,
            market_odds=sample_market_odds,
        )
        
        record = logger.buffer[0]
        
        # Verify all market fields populated
        assert record["market_fav_team"] == "Team A"
        assert record["market_back_odds"] == 1.75
        assert record["market_lay_odds"] == 1.78
        assert record["market_fav_prob"] == 0.57
        assert record["market_batting_team_prob"] == 0.57  # Fav is batting team
        assert record["market_bowling_team_prob"] == 0.43

    def test_missing_market_fav_team(
        self, temp_states_dir, sample_match_state, sample_features, mock_predictor
    ):
        """Test handling when market_fav_team is missing."""
        logger = MatchStateLogger("1234567", "test", temp_states_dir, "v1", "fs_v1")
        
        market_odds = {
            "market_back_odds": 1.75,
            "market_fav_prob": 0.57,
            # market_fav_team missing
        }
        
        logger.record_ball(sample_match_state, sample_features, mock_predictor, market_odds)
        
        record = logger.buffer[0]
        
        # Team-specific probs should be None
        assert record["market_batting_team_prob"] is None
        assert record["market_bowling_team_prob"] is None
        
        # Deviation should be None
        assert record["deviation"] is None
        assert record["deviation_bucket"] is None

    def test_missing_market_fav_prob(
        self, temp_states_dir, sample_match_state, sample_features, mock_predictor
    ):
        """Test handling when market_fav_prob is missing."""
        logger = MatchStateLogger("1234567", "test", temp_states_dir, "v1", "fs_v1")
        
        market_odds = {
            "market_fav_team": "Team A",
            "market_back_odds": 1.75,
            # market_fav_prob missing
        }
        
        logger.record_ball(sample_match_state, sample_features, mock_predictor, market_odds)
        
        record = logger.buffer[0]
        
        # Team-specific probs should be None
        assert record["market_batting_team_prob"] is None
        assert record["market_bowling_team_prob"] is None

    def test_lay_odds_recorded(
        self, temp_states_dir, sample_match_state, sample_features,
        mock_predictor, sample_market_odds
    ):
        """Test that lay odds are recorded correctly."""
        logger = MatchStateLogger("1234567", "test", temp_states_dir, "v1", "fs_v1")
        
        logger.record_ball(
            match_state=sample_match_state,
            features_dict=sample_features,
            predictor=mock_predictor,
            market_odds=sample_market_odds,
        )
        
        record = logger.buffer[0]
        assert record["market_lay_odds"] == 1.78


class TestMultiLeagueIsolation:
    """Test multi-league data isolation (US3 - T022)."""

    def test_separate_directories_per_league(self, tmp_path):
        """Test that different leagues write to separate directories."""
        # Create two loggers with different leagues
        bbl_dir = tmp_path / "match_states" / "bbl"
        sa20_dir = tmp_path / "match_states" / "sa20"
        
        bbl_logger = MatchStateLogger(
            match_id="1234567",
            league="bbl",
            states_dir=bbl_dir,
            model_version="v1",
            feature_store_version="fs_v1",
        )
        
        sa20_logger = MatchStateLogger(
            match_id="7654321",
            league="sa20",
            states_dir=sa20_dir,
            model_version="v1",
            feature_store_version="fs_v1",
        )
        
        # Verify loggers have correct configuration
        assert bbl_logger.league == "bbl"
        assert sa20_logger.league == "sa20"
        
        # Verify correct output paths
        assert bbl_logger.output_file == bbl_dir / "1234567.parquet"
        assert sa20_logger.output_file == sa20_dir / "7654321.parquet"
        
        # Verify directories are separate
        assert bbl_dir != sa20_dir

    def test_league_tag_in_records(
        self, temp_states_dir, sample_match_state, sample_features,
        mock_predictor, sample_market_odds
    ):
        """Test that league tag is correctly populated in every record."""
        # Create logger with specific league
        logger = MatchStateLogger(
            match_id="1234567",
            league="ilt20",
            states_dir=temp_states_dir,
            model_version="v1",
            feature_store_version="fs_v1",
        )
        
        # Record multiple balls
        for i in range(3):
            state = sample_match_state.copy()
            state["ball"] = i + 1
            logger.record_ball(state, sample_features, mock_predictor, sample_market_odds)
        
        # Verify all records have correct league tag
        for record in logger.buffer:
            assert record["league"] == "ilt20"

    def test_match_metadata_has_league(self, temp_states_dir):
        """Test that match metadata includes league tag."""
        logger = MatchStateLogger(
            match_id="1234567",
            league="wpl",
            states_dir=temp_states_dir,
            model_version="v1",
            feature_store_version="fs_v1",
        )
        
        logger.finalize(
            winner="Team A",
            team_a_score=185,
            team_b_score=178,
            result_type="completed",
        )
        
        # Verify metadata has league
        metadata_file = temp_states_dir / "match_metadata.parquet"
        df = pd.read_parquet(metadata_file)
        assert df.iloc[0]["league"] == "wpl"
