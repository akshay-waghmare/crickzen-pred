"""Tests for message formatter."""

import pytest

from bbl_pipeline.telegram.message_formatter import (
    format_prematch_prediction,
    format_match_start,
    format_match_result,
    calculate_model_edge,
    determine_correctness,
    escape_html,
)


class TestEscapeHtml:
    """Tests for HTML escaping."""
    
    def test_escapes_angle_brackets(self):
        """Test that angle brackets are escaped."""
        assert escape_html("<script>") == "&lt;script&gt;"
    
    def test_escapes_ampersand(self):
        """Test that ampersand is escaped."""
        assert escape_html("Tom & Jerry") == "Tom &amp; Jerry"
    
    def test_escapes_quotes(self):
        """Test that quotes are escaped."""
        assert escape_html('Say "hello"') == 'Say &quot;hello&quot;'
    
    def test_preserves_normal_text(self):
        """Test that normal text is preserved."""
        assert escape_html("Sydney Sixers") == "Sydney Sixers"


class TestCalculateModelEdge:
    """Tests for edge calculation."""
    
    def test_positive_edge(self):
        """Test calculating positive edge."""
        # Model: 67.5%, Odds: 1.52 (implied: 65.8%)
        # Edge = (0.675 - 0.658) * 100 ≈ 1.7%
        edge = calculate_model_edge(67.5, 1.52)
        assert abs(edge - 1.7) < 0.5  # Allow small floating point error
    
    def test_negative_edge(self):
        """Test calculating negative edge."""
        # Model: 40%, Odds: 2.0 (implied: 50%)
        # Edge = (0.40 - 0.50) * 100 = -10%
        edge = calculate_model_edge(40.0, 2.0)
        assert abs(edge - (-10.0)) < 0.1
    
    def test_zero_edge(self):
        """Test calculating zero edge."""
        # Model: 50%, Odds: 2.0 (implied: 50%)
        edge = calculate_model_edge(50.0, 2.0)
        assert abs(edge) < 0.1


class TestFormatPrematchPrediction:
    """Tests for pre-match prediction formatting."""
    
    def test_basic_format(self):
        """Test basic message formatting."""
        message = format_prematch_prediction(
            match_id="1234567",
            league="BBL",
            team_a="Sydney Sixers",
            team_b="Melbourne Stars",
            selection_type="BACK",
            selected_team="Sydney Sixers",
            model_probability=67.5,
            market_odds=1.52,
        )
        
        assert "<b>MATCH ID:</b> 1234567" in message
        assert "<b>LEAGUE:</b> BBL" in message
        assert "Sydney Sixers vs Melbourne Stars" in message
        assert "Sydney Sixers win: 67.5%" in message
        assert "Sydney Sixers: 1.52" in message
        assert "BACK – Sydney Sixers" in message
        assert "Pre-Match Prediction" in message
    
    def test_with_provided_edge(self):
        """Test formatting with pre-calculated edge."""
        message = format_prematch_prediction(
            match_id="1234567",
            league="BBL",
            team_a="Sydney Sixers",
            team_b="Melbourne Stars",
            selection_type="BACK",
            selected_team="Sydney Sixers",
            model_probability=67.5,
            market_odds=1.52,
            model_edge=5.2,
        )
        
        assert "+5.2%" in message
    
    def test_lay_selection(self):
        """Test formatting with LAY selection."""
        message = format_prematch_prediction(
            match_id="1234567",
            league="BBL",
            team_a="Sydney Sixers",
            team_b="Melbourne Stars",
            selection_type="LAY",
            selected_team="Melbourne Stars",
            model_probability=32.5,
            market_odds=3.00,
        )
        
        assert "LAY – Melbourne Stars" in message
    
    def test_escapes_special_characters(self):
        """Test that special characters are escaped."""
        message = format_prematch_prediction(
            match_id="<test>",
            league="BBL",
            team_a="Team & Co",
            team_b='Team "B"',
            selection_type="BACK",
            selected_team="Team & Co",
            model_probability=50.0,
            market_odds=2.0,
        )
        
        assert "&lt;test&gt;" in message
        assert "Team &amp; Co" in message
        assert "Team &quot;B&quot;" in message


class TestFormatMatchStart:
    """Tests for match start formatting."""
    
    def test_basic_format(self):
        """Test basic match start formatting."""
        message = format_match_start(
            match_id="1234567",
            team_a="Sydney Sixers",
            team_b="Melbourne Stars",
            toss_winner="Melbourne Stars",
            toss_decision="Bowl",
            model_prematch_probability=67.5,
            selected_team="Sydney Sixers",
        )
        
        assert "<b>MATCH ID:</b> 1234567" in message
        assert "Melbourne Stars won the toss" in message
        assert "Decision: Bowl" in message
        assert "Sydney Sixers win probability: 67.5%" in message
        assert "Match Started" in message
    
    def test_without_prematch_probability(self):
        """Test formatting without pre-match probability."""
        message = format_match_start(
            match_id="1234567",
            team_a="Sydney Sixers",
            team_b="Melbourne Stars",
            toss_winner="Sydney Sixers",
            toss_decision="Bat",
        )
        
        assert "N/A (no pre-match prediction)" in message


class TestFormatMatchResult:
    """Tests for match result formatting."""
    
    def test_correct_prediction(self):
        """Test formatting with correct prediction."""
        message = format_match_result(
            match_id="1234567",
            winning_team="Sydney Sixers",
            model_call_correct=True,
            original_selection_type="BACK",
            original_probability=67.5,
        )
        
        assert "<b>MATCH ID:</b> 1234567" in message
        assert "Winner: Sydney Sixers" in message
        assert "✓ CORRECT" in message
        assert "(BACK @ 67.5%)" in message
        assert "Match Complete" in message
    
    def test_incorrect_prediction(self):
        """Test formatting with incorrect prediction."""
        message = format_match_result(
            match_id="1234567",
            winning_team="Melbourne Stars",
            model_call_correct=False,
            original_selection_type="BACK",
            original_probability=67.5,
        )
        
        assert "✗ INCORRECT" in message
    
    def test_without_original_prediction(self):
        """Test formatting without original prediction."""
        message = format_match_result(
            match_id="1234567",
            winning_team="Sydney Sixers",
        )
        
        assert "N/A (no pre-match prediction)" in message


class TestDetermineCorrectness:
    """Tests for correctness determination."""
    
    def test_back_correct(self):
        """Test BACK selection when team wins."""
        assert determine_correctness(
            winning_team="Sydney Sixers",
            selection_type="BACK",
            selected_team="Sydney Sixers",
        ) is True
    
    def test_back_incorrect(self):
        """Test BACK selection when team loses."""
        assert determine_correctness(
            winning_team="Melbourne Stars",
            selection_type="BACK",
            selected_team="Sydney Sixers",
        ) is False
    
    def test_lay_correct(self):
        """Test LAY selection when team loses."""
        assert determine_correctness(
            winning_team="Melbourne Stars",
            selection_type="LAY",
            selected_team="Sydney Sixers",
        ) is True
    
    def test_lay_incorrect(self):
        """Test LAY selection when team wins."""
        assert determine_correctness(
            winning_team="Sydney Sixers",
            selection_type="LAY",
            selected_team="Sydney Sixers",
        ) is False
    
    def test_case_insensitive(self):
        """Test that selection type is case insensitive."""
        assert determine_correctness("A", "back", "A") is True
        assert determine_correctness("B", "BACK", "A") is False
        assert determine_correctness("B", "lay", "A") is True
    
    def test_invalid_selection_type_raises(self):
        """Test that invalid selection type raises ValueError."""
        with pytest.raises(ValueError, match="Invalid selection_type"):
            determine_correctness("A", "INVALID", "A")
