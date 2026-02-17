"""
Unit tests for StateAnalyzer.

Tests consolidation, calibration report generation, and CLI command wiring.
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path
from src.bbl_pipeline.analysis.state_analyzer import StateAnalyzer


@pytest.fixture
def temp_states_dir(tmp_path):
    """Create a temporary directory for test match state files."""
    states_dir = tmp_path / "match_states" / "test_league"
    states_dir.mkdir(parents=True, exist_ok=True)
    return states_dir


@pytest.fixture
def sample_match_data():
    """Create sample match state data for testing."""
    # Create 2 matches with ~20 balls each
    data = []
    
    for match_id in ["1234567", "7654321"]:
        for innings in [1, 2]:
            for over in range(1, 11):  # 10 overs
                for ball in range(1, 3):  # 2 balls per over
                    ball_record = {
                        "match_id": match_id,
                        "league": "test",
                        "venue": "Test Stadium",
                        "batting_team": "Team A" if innings == 1 else "Team B",
                        "bowling_team": "Team B" if innings == 1 else "Team A",
                        "innings": innings,
                        "over_number": over,
                        "ball_in_over": ball,
                        "runs_this_ball": np.random.choice([0, 1, 2, 4, 6]),
                        "wicket_this_ball": np.random.choice([True, False], p=[0.05, 0.95]),
                        "bat_team_runs": (over - 1) * 12 + ball * 6,
                        "bat_team_wickets": min((over - 1) // 3, 9),
                        "match_phase": "powerplay" if over <= 6 else ("middle" if over <= 15 else "death"),
                        "batting_team_tier": "top",
                        "bowling_team_tier": "mid",
                        "model_prob_final": 0.5 + np.random.uniform(-0.2, 0.2),
                        "market_batting_team_prob": 0.5 + np.random.uniform(-0.15, 0.15),
                        "timestamp": pd.Timestamp("2025-01-01") + pd.Timedelta(hours=innings, minutes=over * 6 + ball),
                        "model_version": "test_v1",
                        "feature_store_version": "test_fs_v1",
                    }
                    data.append(ball_record)
    
    return pd.DataFrame(data)


@pytest.fixture
def sample_metadata():
    """Create sample match metadata."""
    return pd.DataFrame([
        {
            "match_id": "1234567",
            "league": "test",
            "venue": "Test Stadium",
            "team_a": "Team A",
            "team_b": "Team B",
            "winner": "Team A",
            "team_a_score": 185,
            "team_b_score": 178,
            "result_type": "completed",
        },
        {
            "match_id": "7654321",
            "league": "test",
            "venue": "Test Stadium 2",
            "team_a": "Team A",
            "team_b": "Team B",
            "winner": "Team B",
            "team_a_score": 165,
            "team_b_score": 168,
            "result_type": "completed",
        }
    ])


class TestStateAnalyzerInit:
    """Test StateAnalyzer initialization."""

    def test_init_discovers_match_files(self, temp_states_dir, sample_match_data):
        """Test that __init__ discovers match Parquet files."""
        # Write two match files
        match1 = sample_match_data[sample_match_data["match_id"] == "1234567"]
        match2 = sample_match_data[sample_match_data["match_id"] == "7654321"]
        
        match1.to_parquet(temp_states_dir / "1234567.parquet", index=False)
        match2.to_parquet(temp_states_dir / "7654321.parquet", index=False)
        
        # Initialize analyzer
        analyzer = StateAnalyzer(league="test", states_dir=temp_states_dir)
        
        assert analyzer.league == "test"
        assert len(analyzer.match_files) == 2
        assert analyzer.states_dir == temp_states_dir

    def test_init_excludes_metadata_files(self, temp_states_dir, sample_match_data, sample_metadata):
        """Test that __init__ excludes special files from match_files list."""
        # Write match files and metadata
        sample_match_data.to_parquet(temp_states_dir / "1234567.parquet", index=False)
        sample_metadata.to_parquet(temp_states_dir / "match_metadata.parquet", index=False)
        
        # Create other special files
        pd.DataFrame().to_parquet(temp_states_dir / "all_matches.parquet", index=False)
        pd.DataFrame().to_parquet(temp_states_dir / "volatility_profiles.parquet", index=False)
        pd.DataFrame().to_parquet(temp_states_dir / "signal_events.parquet", index=False)
        
        analyzer = StateAnalyzer(league="test", states_dir=temp_states_dir)
        
        # Should only find the match file, not metadata/consolidated files
        assert len(analyzer.match_files) == 1
        assert analyzer.match_files[0].name == "1234567.parquet"


class TestConsolidate:
    """Test consolidate method."""

    def test_consolidate_merges_files(self, temp_states_dir, sample_match_data):
        """Test that consolidate merges all match files correctly."""
        # Write two match files
        match1 = sample_match_data[sample_match_data["match_id"] == "1234567"]
        match2 = sample_match_data[sample_match_data["match_id"] == "7654321"]
        
        match1.to_parquet(temp_states_dir / "1234567.parquet", index=False)
        match2.to_parquet(temp_states_dir / "7654321.parquet", index=False)
        
        # Consolidate
        analyzer = StateAnalyzer(league="test", states_dir=temp_states_dir)
        df = analyzer.consolidate()
        
        # Verify consolidation
        assert len(df) == len(sample_match_data)
        assert df["match_id"].nunique() == 2
        assert set(df["match_id"].unique()) == {"1234567", "7654321"}
        
        # Verify output file created
        assert analyzer.consolidated_file.exists()

    def test_consolidate_sorts_correctly(self, temp_states_dir, sample_match_data):
        """Test that consolidate sorts by match_id, innings, over, ball."""
        # Write match files (in reverse order to test sorting)
        match1 = sample_match_data[sample_match_data["match_id"] == "1234567"]
        match2 = sample_match_data[sample_match_data["match_id"] == "7654321"]
        
        match2.to_parquet(temp_states_dir / "7654321.parquet", index=False)
        match1.to_parquet(temp_states_dir / "1234567.parquet", index=False)
        
        # Consolidate
        analyzer = StateAnalyzer(league="test", states_dir=temp_states_dir)
        df = analyzer.consolidate()
        
        # Verify sorting
        assert df.iloc[0]["match_id"] == "1234567"
        assert df.iloc[-1]["match_id"] == "7654321"
        
        # Within a match, verify innings/over/ball sorting
        match1_df = df[df["match_id"] == "1234567"]
        assert match1_df.iloc[0]["innings"] == 1
        assert match1_df.iloc[-1]["innings"] == 2

    def test_consolidate_handles_empty_directory(self, temp_states_dir):
        """Test consolidate returns empty DataFrame when no files found."""
        analyzer = StateAnalyzer(league="test", states_dir=temp_states_dir)
        df = analyzer.consolidate()
        
        assert len(df) == 0
        assert isinstance(df, pd.DataFrame)


class TestCalibrationReport:
    """Test calibration_report method."""

    def test_calibration_report_computes_metrics(self, temp_states_dir, sample_match_data, sample_metadata):
        """Test that calibration_report computes Brier/ECE/LogLoss correctly."""
        # Write consolidated data and metadata
        sample_match_data.to_parquet(temp_states_dir / "all_matches.parquet", index=False)
        sample_metadata.to_parquet(temp_states_dir / "match_metadata.parquet", index=False)
        
        # Generate report
        analyzer = StateAnalyzer(league="test", states_dir=temp_states_dir)
        results = analyzer.calibration_report()
        
        # Verify overall metrics exist
        assert "overall" in results
        assert "brier" in results["overall"]
        assert "ece" in results["overall"]
        assert "log_loss" in results["overall"]
        assert "sample_count" in results["overall"]
        
        # Verify metrics are valid numbers
        assert 0 <= results["overall"]["brier"] <= 1
        assert 0 <= results["overall"]["ece"] <= 1
        assert results["overall"]["log_loss"] > 0
        assert results["overall"]["sample_count"] == len(sample_match_data)

    def test_calibration_report_by_innings(self, temp_states_dir, sample_match_data, sample_metadata):
        """Test that calibration_report segments by innings."""
        # Write data
        sample_match_data.to_parquet(temp_states_dir / "all_matches.parquet", index=False)
        sample_metadata.to_parquet(temp_states_dir / "match_metadata.parquet", index=False)
        
        # Generate report
        analyzer = StateAnalyzer(league="test", states_dir=temp_states_dir)
        results = analyzer.calibration_report()
        
        # Verify innings segmentation
        assert "innings_1" in results
        assert "innings_2" in results
        
        # Verify sample counts match
        innings1_count = len(sample_match_data[sample_match_data["innings"] == 1])
        innings2_count = len(sample_match_data[sample_match_data["innings"] == 2])
        
        assert results["innings_1"]["sample_count"] == innings1_count
        assert results["innings_2"]["sample_count"] == innings2_count

    def test_calibration_report_by_phase(self, temp_states_dir, sample_match_data, sample_metadata):
        """Test that calibration_report segments by match phase."""
        # Write data
        sample_match_data.to_parquet(temp_states_dir / "all_matches.parquet", index=False)
        sample_metadata.to_parquet(temp_states_dir / "match_metadata.parquet", index=False)
        
        # Generate report
        analyzer = StateAnalyzer(league="test", states_dir=temp_states_dir)
        results = analyzer.calibration_report()
        
        # Verify phase segmentation
        assert "phase_powerplay" in results
        assert "phase_middle" in results
        assert "phase_death" in results

    def test_calibration_report_creates_markdown(self, temp_states_dir, sample_match_data, sample_metadata):
        """Test that calibration_report creates markdown file."""
        # Write data
        sample_match_data.to_parquet(temp_states_dir / "all_matches.parquet", index=False)
        sample_metadata.to_parquet(temp_states_dir / "match_metadata.parquet", index=False)
        
        # Generate report
        analyzer = StateAnalyzer(league="test", states_dir=temp_states_dir)
        analyzer.calibration_report()
        
        # Verify markdown file exists
        report_file = temp_states_dir / "CALIBRATION_REPORT.md"
        assert report_file.exists()
        
        # Verify markdown contains expected sections
        content = report_file.read_text()
        assert "# Calibration Report:" in content
        assert "## Overall Calibration" in content
        assert "## Calibration by Innings" in content
        assert "## Calibration by Match Phase" in content
        assert "Brier Score" in content
        assert "ECE" in content
        assert "Log Loss" in content

    def test_calibration_report_handles_no_metadata(self, temp_states_dir, sample_match_data):
        """Test calibration_report handles missing metadata gracefully."""
        # Write only consolidated data (no metadata)
        sample_match_data.to_parquet(temp_states_dir / "all_matches.parquet", index=False)
        
        analyzer = StateAnalyzer(league="test", states_dir=temp_states_dir)
        results = analyzer.calibration_report()
        
        # Should return empty results since no outcomes available
        assert results == {}

    def test_calibration_report_filters_incomplete_matches(self, temp_states_dir, sample_match_data, sample_metadata):
        """Test that incomplete matches (no winner) are filtered out."""
        # Add an incomplete match to metadata
        incomplete = pd.DataFrame([{
            "match_id": "incomplete_match",
            "league": "test",
            "winner": None,
            "result_type": "in_progress",
        }])
        
        metadata_with_incomplete = pd.concat([sample_metadata, incomplete], ignore_index=True)
        
        # Write data
        sample_match_data.to_parquet(temp_states_dir / "all_matches.parquet", index=False)
        metadata_with_incomplete.to_parquet(temp_states_dir / "match_metadata.parquet", index=False)
        
        # Generate report
        analyzer = StateAnalyzer(league="test", states_dir=temp_states_dir)
        results = analyzer.calibration_report()
        
        # Should only include completed matches
        assert results["overall"]["sample_count"] == len(sample_match_data)


class TestECEComputation:
    """Test ECE computation helper method."""

    def test_ece_perfect_calibration(self, temp_states_dir):
        """Test ECE = 0 for perfectly calibrated predictions."""
        analyzer = StateAnalyzer(league="test", states_dir=temp_states_dir)
        
        # Perfect calibration: predictions match actual frequencies
        y_true = np.array([0, 0, 0, 0, 0, 1, 1, 1, 1, 1])
        y_pred = np.array([0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0, 1.0])
        
        ece = analyzer._compute_ece(y_true, y_pred, n_bins=2)
        
        assert ece == pytest.approx(0.0, abs=0.01)

    def test_ece_poor_calibration(self, temp_states_dir):
        """Test ECE > 0 for poorly calibrated predictions."""
        analyzer = StateAnalyzer(league="test", states_dir=temp_states_dir)
        
        # Poor calibration: all 0.5 predictions for mixed outcomes
        y_true = np.array([0, 0, 0, 0, 0, 1, 1, 1, 1, 1])
        y_pred = np.array([0.9, 0.9, 0.9, 0.9, 0.9, 0.1, 0.1, 0.1, 0.1, 0.1])
        
        ece = analyzer._compute_ece(y_true, y_pred, n_bins=2)
        
        # Should have significant error
        assert ece > 0.3


class TestSignalExtraction:
    """Test extract_signals method (US8 - T035)."""

    def test_extract_signals_basic(self, temp_states_dir):
        """Test signal extraction with simple price reversion."""
        # Create match data with deliberate deviation pattern
        data = []
        for ball in range(1, 6):
            data.append({
                "match_id": "1234567",
                "league": "test",
                "venue": "Test Stadium",
                "batting_team": "Team A",
                "bowling_team": "Team B",
                "innings": 1,
                "over_number": 10,
                "ball_in_over": ball,
                "match_phase": "middle",
                "batting_team_tier": "top",
                "bowling_team_tier": "mid",
                "model_prob_final": 0.70,  # Model says 70%
                "market_batting_team_prob": 0.50 if ball == 1 else 0.65,  # Market moves from 50% to 65%
                "deviation": 0.20 if ball == 1 else 0.05,
                "deviation_abs": 0.20 if ball == 1 else 0.05,
                "deviation_bucket": "0.20-0.25" if ball == 1 else "0.00-0.05",
                "deviation_direction": "model_higher",
                "timestamp": pd.Timestamp("2025-01-01") + pd.Timedelta(minutes=ball),
            })
        
        df = pd.DataFrame(data)
        df.to_parquet(temp_states_dir / "all_matches.parquet", index=False)
        
        # Extract signals
        analyzer = StateAnalyzer(league="test", states_dir=temp_states_dir)
        signals = analyzer.extract_signals(deviation_threshold=0.10, reversion_threshold=0.50)
        
        # Should find 1 signal (ball 1 with 0.20 deviation)
        assert len(signals) == 1
        assert signals.iloc[0]["price_reverted"] == True
        assert signals.iloc[0]["reversion_magnitude"] > 0.5

    def test_extract_signals_no_reversion(self, temp_states_dir):
        """Test signal extraction when price doesn't revert."""
        data = []
        for ball in range(1, 4):
            data.append({
                "match_id": "1234567",
                "league": "test",
                "venue": "Test Stadium",
                "batting_team": "Team A",
                "bowling_team": "Team B",
                "innings": 1,
                "over_number": 10,
                "ball_in_over": ball,
                "match_phase": "middle",
                "batting_team_tier": "top",
                "bowling_team_tier": "mid",
                "model_prob_final": 0.70,
                "market_batting_team_prob": 0.50,  # Market stays at 50%
                "deviation": 0.20,
                "deviation_abs": 0.20,
                "deviation_bucket": "0.20-0.25",
                "deviation_direction": "model_higher",
                "timestamp": pd.Timestamp("2025-01-01") + pd.Timedelta(minutes=ball),
            })
        
        df = pd.DataFrame(data)
        df.to_parquet(temp_states_dir / "all_matches.parquet", index=False)
        
        # Extract signals
        analyzer = StateAnalyzer(league="test", states_dir=temp_states_dir)
        signals = analyzer.extract_signals(deviation_threshold=0.10)
        
        # Should find signals but no reversion
        assert len(signals) == 3
        assert signals["price_reverted"].sum() == 0


class TestMetaModelReadiness:
    """Test meta_model_readiness method (US8 - T036)."""

    def test_readiness_with_sufficient_data(self, temp_states_dir, sample_match_data, sample_metadata):
        """Test readiness check with sufficient matches and signals."""
        # Create large metadata (200+ matches)
        large_metadata = pd.concat([sample_metadata] * 150, ignore_index=True)
        large_metadata["match_id"] = [f"match_{i}" for i in range(len(large_metadata))]
        large_metadata.to_parquet(temp_states_dir / "match_metadata.parquet", index=False)
        
        # Create signal events (1000+ signals)
        large_signals = pd.DataFrame([{
            "match_id": f"match_{i % 100}",
            "deviation_bucket": "0.10-0.15",
            "price_reverted": True,
        } for i in range(1200)])
        large_signals.to_parquet(temp_states_dir / "signal_events.parquet", index=False)
        
        # Create consolidated data
        sample_match_data.to_parquet(temp_states_dir / "all_matches.parquet", index=False)
        
        # Check readiness
        analyzer = StateAnalyzer(league="test", states_dir=temp_states_dir)
        readiness = analyzer.meta_model_readiness()
        
        assert readiness["ready_for_meta_model"] == True
        assert readiness["total_matches"] >= 200
        assert readiness["total_signal_events"] >= 1000

    def test_readiness_with_insufficient_data(self, temp_states_dir, sample_metadata):
        """Test readiness check with insufficient data."""
        # Write minimal metadata
        sample_metadata.to_parquet(temp_states_dir / "match_metadata.parquet", index=False)
        
        # Check readiness
        analyzer = StateAnalyzer(league="test", states_dir=temp_states_dir)
        readiness = analyzer.meta_model_readiness()
        
        assert readiness["ready_for_meta_model"] == False
        assert readiness["total_matches"] < 200


class TestDeviationAnalysis:
    """Test deviation_analysis method (US6 - T028)."""

    def test_deviation_analysis_by_bucket(self, temp_states_dir, sample_metadata):
        """Test deviation analysis groups by bucket correctly."""
        # Create signal events with winners
        signals = pd.DataFrame([
            {
                "match_id": "1234567",
                "league": "test",
                "venue": "Test Stadium",
                "batting_team": "Team A",
                "bowling_team": "Team B",
                "deviation": 0.12,
                "deviation_abs": 0.12,
                "deviation_bucket": "0.10-0.15",
                "deviation_direction": "model_higher",
                "price_reverted": True,
                "match_phase": "middle",
                "batting_team_tier": "top",
                "bowling_team_tier": "mid",
            }
        ] * 10 + [
            {
                "match_id": "7654321",
                "league": "test",
                "venue": "Test Stadium",
                "batting_team": "Team A",
                "bowling_team": "Team B",
                "deviation": 0.22,
                "deviation_abs": 0.22,
                "deviation_bucket": "0.20-0.25",
                "deviation_direction": "model_higher",
                "price_reverted": False,
                "match_phase": "death",
                "batting_team_tier": "mid",
                "bowling_team_tier": "bottom",
            }
        ] * 5)
        
        signals.to_parquet(temp_states_dir / "signal_events.parquet", index=False)
        sample_metadata.to_parquet(temp_states_dir / "match_metadata.parquet", index=False)
        
        # Run deviation analysis
        analyzer = StateAnalyzer(league="test", states_dir=temp_states_dir)
        analysis = analyzer.deviation_analysis()
        
        # Should have 2 bucket groups
        assert len(analysis) == 2
        assert "0.10-0.15" in analysis["deviation_bucket"].values
        assert "0.20-0.25" in analysis["deviation_bucket"].values


class TestComputeVolatility:
    """Test compute_volatility method (US7 - T031)."""

    def test_compute_volatility_basic(self, temp_states_dir, sample_match_data):
        """Test volatility computation for a single match."""
        # Write match file
        match_data = sample_match_data[sample_match_data["match_id"] == "1234567"]
        
        # Add prob deltas
        match_data["model_prob_delta"] = np.random.uniform(-0.05, 0.05, len(match_data))
        match_data["market_prob_delta"] = np.random.uniform(-0.03, 0.03, len(match_data))
        
        match_data.to_parquet(temp_states_dir / "1234567.parquet", index=False)
        
        # Compute volatility
        analyzer = StateAnalyzer(league="test", states_dir=temp_states_dir)
        volatility = analyzer.compute_volatility()
        
        # Should have 1 profile
        assert len(volatility) == 1
        assert volatility.iloc[0]["match_id"] == "1234567"
        assert "model_volatility" in volatility.columns
        assert "market_volatility" in volatility.columns
        assert "volatility_ratio" in volatility.columns


class TestRecoveryAnalysis:
    """Test recovery_analysis method (US9 - T033)."""

    def test_recovery_analysis_basic(self, temp_states_dir, sample_metadata):
        """Test recovery analysis for top-tier teams under pressure."""
        # Create signal events with top-tier team under pressure
        signals = pd.DataFrame([
            {
                "match_id": "1234567",
                "league": "test",
                "venue": "Test Stadium",
                "batting_team": "Team A",
                "bowling_team": "Team B",
                "batting_team_tier": "top",
                "bowling_team_tier": "mid",
                "match_phase": "powerplay",
                "deviation": -0.15,  # Market favors bowling team
                "model_prob_final": 0.40,
                "market_batting_team_prob": 0.55,
            }
        ] * 5)
        
        signals.to_parquet(temp_states_dir / "signal_events.parquet", index=False)
        sample_metadata.to_parquet(temp_states_dir / "match_metadata.parquet", index=False)
        
        # Run recovery analysis
        analyzer = StateAnalyzer(league="test", states_dir=temp_states_dir)
        recovery = analyzer.recovery_analysis()
        
        # Should have at least 1 phase
        assert len(recovery) > 0
        assert "recovery_premium" in recovery.columns
