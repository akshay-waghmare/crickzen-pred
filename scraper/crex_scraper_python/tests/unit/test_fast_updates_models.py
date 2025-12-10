"""
Unit tests for Fast Updates Models (Feature 007).
"""

import pytest
from datetime import datetime
from src.models import (
    BallEvent,
    Extras,
    Wicket,
    ScoreSnapshot,
    ScorecardState,
    BatsmanStats,
    BowlerStats,
    FallOfWicket,
    UpdateSequence,
    MatchPriority,
    MatchPhase,
    MatchImportance,
)


class TestBallEvent:
    """Tests for BallEvent model."""

    def test_create_basic_ball(self):
        """Test creating a basic ball event."""
        ball = BallEvent(
            match_id="crex:123",
            ball_number=9.4,
            runs=2,
            timestamp=datetime.now(),
            sequence_number=1,
        )
        assert ball.match_id == "crex:123"
        assert ball.ball_number == 9.4
        assert ball.runs == 2
        assert ball.over == 9
        assert ball.ball_in_over == 4

    def test_ball_with_extras(self):
        """Test ball event with extras."""
        extras = Extras(wides=1, no_balls=0, byes=0, leg_byes=0)
        ball = BallEvent(
            match_id="crex:123",
            ball_number=5.2,
            runs=0,
            timestamp=datetime.now(),
            sequence_number=2,
            extras=extras,
        )
        assert ball.total_runs == 1
        assert not ball.is_legal_delivery

    def test_ball_with_wicket(self):
        """Test ball event with wicket."""
        wicket = Wicket(type="caught", batsman="Kohli", fielder="Smith")
        ball = BallEvent(
            match_id="crex:123",
            ball_number=10.5,
            runs=0,
            timestamp=datetime.now(),
            sequence_number=3,
            wicket=wicket,
        )
        assert ball.is_wicket
        assert ball.wicket.type == "caught"
        assert ball.wicket.fielder == "Smith"

    def test_invalid_ball_number(self):
        """Test that invalid ball numbers raise errors."""
        with pytest.raises(ValueError, match="ball within over must be 1-6"):
            BallEvent(
                match_id="crex:123",
                ball_number=9.7,  # Invalid: ball must be 1-6
                runs=1,
                timestamp=datetime.now(),
                sequence_number=1,
            )

    def test_invalid_runs(self):
        """Test that invalid runs raise errors."""
        with pytest.raises(ValueError, match="runs must be between 0 and 7"):
            BallEvent(
                match_id="crex:123",
                ball_number=9.4,
                runs=8,  # Invalid: max 7 (boundary + overthrow)
                timestamp=datetime.now(),
                sequence_number=1,
            )

    def test_ball_follows_previous(self):
        """Test ball continuity checking."""
        ball1 = BallEvent(
            match_id="crex:123",
            ball_number=9.3,
            runs=1,
            timestamp=datetime.now(),
            sequence_number=10,
        )
        ball2 = BallEvent(
            match_id="crex:123",
            ball_number=9.4,
            runs=2,
            timestamp=datetime.now(),
            sequence_number=11,
        )
        assert ball2.follows(ball1)

    def test_ball_gap_detection(self):
        """Test gap detection between balls."""
        ball1 = BallEvent(
            match_id="crex:123",
            ball_number=9.3,
            runs=1,
            timestamp=datetime.now(),
            sequence_number=10,
        )
        ball2 = BallEvent(
            match_id="crex:123",
            ball_number=9.6,
            runs=4,
            timestamp=datetime.now(),
            sequence_number=13,  # Skipped 2 balls
        )
        assert not ball2.follows(ball1)
        assert ball2.gap_from(ball1) == 2

    def test_ball_serialization(self):
        """Test ball event to/from dict."""
        original = BallEvent(
            match_id="crex:123",
            ball_number=15.5,
            runs=6,
            timestamp=datetime(2024, 1, 15, 12, 0, 0),
            sequence_number=100,
            extras=Extras(wides=0, no_balls=0, byes=0, leg_byes=0),
            wicket=Wicket(type="bowled", batsman="Warner"),
        )
        
        data = original.to_dict()
        restored = BallEvent.from_dict(data)
        
        assert restored.match_id == original.match_id
        assert restored.ball_number == original.ball_number
        assert restored.runs == original.runs
        assert restored.is_wicket


class TestScoreSnapshot:
    """Tests for ScoreSnapshot model."""

    def test_create_first_innings(self):
        """Test creating first innings snapshot."""
        snapshot = ScoreSnapshot(
            match_id="crex:123",
            innings=1,
            batting_team="India",
            runs=156,
            wickets=3,
            overs=18.4,
            run_rate=8.35,
            timestamp=datetime.now(),
            sequence_number=50,
        )
        assert snapshot.score_string == "156/3 (18.4)"
        assert snapshot.balls_faced == 18 * 6 + 4

    def test_create_second_innings(self):
        """Test creating second innings snapshot with target."""
        snapshot = ScoreSnapshot(
            match_id="crex:123",
            innings=2,
            batting_team="Australia",
            runs=100,
            wickets=2,
            overs=12.0,
            run_rate=8.33,
            timestamp=datetime.now(),
            sequence_number=100,
            target=181,
            required_rate=10.12,
        )
        assert snapshot.runs_needed == 81
        assert snapshot.target == 181

    def test_invalid_wickets(self):
        """Test that invalid wicket count raises error."""
        with pytest.raises(ValueError, match="wickets must be 0-10"):
            ScoreSnapshot(
                match_id="crex:123",
                innings=1,
                batting_team="India",
                runs=100,
                wickets=11,  # Invalid
                overs=15.0,
                run_rate=6.66,
                timestamp=datetime.now(),
                sequence_number=1,
            )

    def test_required_rate_only_second_innings(self):
        """Test that required_rate only valid for 2nd innings."""
        with pytest.raises(ValueError, match="required_rate only valid for 2nd innings"):
            ScoreSnapshot(
                match_id="crex:123",
                innings=1,  # First innings
                batting_team="India",
                runs=100,
                wickets=3,
                overs=15.0,
                run_rate=6.66,
                timestamp=datetime.now(),
                sequence_number=1,
                required_rate=10.0,  # Invalid for 1st innings
            )

    def test_snapshot_ordering(self):
        """Test snapshot sequence ordering."""
        old = ScoreSnapshot(
            match_id="crex:123",
            innings=1,
            batting_team="India",
            runs=100,
            wickets=3,
            overs=15.0,
            run_rate=6.66,
            timestamp=datetime.now(),
            sequence_number=10,
        )
        new = ScoreSnapshot(
            match_id="crex:123",
            innings=1,
            batting_team="India",
            runs=105,
            wickets=3,
            overs=15.4,
            run_rate=6.83,
            timestamp=datetime.now(),
            sequence_number=15,
        )
        assert new.is_newer_than(old)
        assert not old.is_newer_than(new)


class TestScorecardState:
    """Tests for ScorecardState model."""

    def test_create_scorecard(self):
        """Test creating a scorecard state."""
        batsman = BatsmanStats(
            name="Kohli",
            runs=85,
            balls=60,
            fours=8,
            sixes=2,
            status="batting",
        )
        bowler = BowlerStats(
            name="Starc",
            overs=4.0,
            maidens=0,
            runs=35,
            wickets=2,
        )
        
        scorecard = ScorecardState(
            match_id="crex:123",
            innings=1,
            batting=[batsman],
            bowling=[bowler],
            extras=ScorecardExtras(wides=5, no_balls=2),
            fall_of_wickets=[],
            timestamp=datetime.now(),
            team_name="India",
        )
        
        assert scorecard.total_runs == 85 + 7  # runs + extras
        assert scorecard.wickets_fallen == 0
        assert len(scorecard.current_batsmen) == 1

    def test_batsman_strike_rate(self):
        """Test batsman strike rate calculation."""
        batsman = BatsmanStats(
            name="Rohit",
            runs=50,
            balls=30,
            fours=6,
            sixes=2,
            status="batting",
        )
        assert abs(batsman.strike_rate - 166.67) < 0.1

    def test_bowler_economy(self):
        """Test bowler economy rate calculation."""
        bowler = BowlerStats(
            name="Bumrah",
            overs=4.0,
            maidens=1,
            runs=28,
            wickets=3,
        )
        assert abs(bowler.economy - 7.0) < 0.1


class TestUpdateSequence:
    """Tests for UpdateSequence model."""

    def test_initial_sequence(self):
        """Test creating initial sequence."""
        seq = UpdateSequence.initial("crex:123")
        assert seq.match_id == "crex:123"
        assert seq.last_sequence == 0
        assert seq.last_ball_number == 0.0
        assert not seq.gap_detected

    def test_process_update_no_gap(self):
        """Test processing update without gap."""
        seq = UpdateSequence(
            match_id="crex:123",
            last_sequence=10,
            last_ball_number=5.3,
        )
        new_seq = seq.process_update(11, 5.4)
        assert not new_seq.gap_detected
        assert new_seq.last_sequence == 11
        assert new_seq.last_ball_number == 5.4

    def test_process_update_with_gap(self):
        """Test processing update with gap."""
        seq = UpdateSequence(
            match_id="crex:123",
            last_sequence=10,
            last_ball_number=5.3,
        )
        new_seq = seq.process_update(14, 5.6)  # Skipped 3 updates
        assert new_seq.gap_detected
        assert "Missed 3 updates" in new_seq.gap_details

    def test_consecutive_gaps_tracking(self):
        """Test consecutive gap tracking."""
        seq = UpdateSequence.initial("crex:123")
        
        # First gap
        seq = seq.process_update(3, 0.3)  # Skipped 0.1, 0.2
        assert seq.gap_detected
        assert seq.consecutive_gaps == 1
        
        # Second gap
        seq = seq.process_update(6, 0.6)  # Skipped 0.4, 0.5
        assert seq.gap_detected
        assert seq.consecutive_gaps == 2

    def test_gap_escalation(self):
        """Test gap escalation threshold."""
        seq = UpdateSequence(
            match_id="crex:123",
            last_sequence=0,
            last_ball_number=0.0,
            consecutive_gaps=3,
        )
        assert seq.needs_escalation


class TestMatchPriority:
    """Tests for MatchPriority model."""

    def test_create_priority(self):
        """Test creating match priority."""
        priority = MatchPriority(
            match_id="crex:123",
            viewer_count=5000,
            match_phase=MatchPhase.DEATH,
            match_importance=MatchImportance.INTERNATIONAL,
        )
        assert priority.priority_score > 0
        assert priority.polling_interval_seconds > 0

    def test_phase_weights(self):
        """Test that phase weights affect priority."""
        base_args = {
            "match_id": "crex:123",
            "viewer_count": 1000,
            "match_importance": MatchImportance.DOMESTIC,
        }
        
        start = MatchPriority(**base_args, match_phase=MatchPhase.START)
        super_over = MatchPriority(**base_args, match_phase=MatchPhase.SUPER_OVER)
        
        assert super_over.priority_score > start.priority_score

    def test_importance_weights(self):
        """Test that importance weights affect priority."""
        base_args = {
            "match_id": "crex:123",
            "viewer_count": 1000,
            "match_phase": MatchPhase.MIDDLE,
        }
        
        club = MatchPriority(**base_args, match_importance=MatchImportance.CLUB)
        intl = MatchPriority(**base_args, match_importance=MatchImportance.INTERNATIONAL)
        
        assert intl.priority_score > club.priority_score

    def test_close_finish_bonus(self):
        """Test close finish priority bonus."""
        args = {
            "match_id": "crex:123",
            "viewer_count": 1000,
            "match_phase": MatchPhase.DEATH,
            "match_importance": MatchImportance.FRANCHISE,
        }
        
        normal = MatchPriority(**args, is_close_finish=False)
        close = MatchPriority(**args, is_close_finish=True)
        
        assert close.priority_score == normal.priority_score * 1.5

    def test_from_match_state(self):
        """Test creating priority from match state."""
        priority = MatchPriority.from_match_state(
            match_id="crex:123",
            viewer_count=10000,
            overs=18.4,
            max_overs=20,
            runs_needed=25,
            wickets=7,
            match_type="franchise",
        )
        assert priority.match_phase == MatchPhase.DEATH
        assert priority.match_importance == MatchImportance.FRANCHISE

    def test_priority_ordering(self):
        """Test that priorities can be compared for ordering."""
        high = MatchPriority(
            match_id="crex:1",
            viewer_count=10000,
            match_phase=MatchPhase.SUPER_OVER,
            match_importance=MatchImportance.INTERNATIONAL,
        )
        low = MatchPriority(
            match_id="crex:2",
            viewer_count=100,
            match_phase=MatchPhase.START,
            match_importance=MatchImportance.CLUB,
        )
        
        # Higher priority should be "less than" for min-heap priority queue
        assert high < low


# Need to import ScorecardExtras for the test
from src.models.scorecard_state import ScorecardExtras


class TestExtras:
    """Tests for Extras model."""

    def test_extras_total(self):
        """Test extras total calculation."""
        extras = Extras(wides=2, no_balls=1, byes=3, leg_byes=1)
        assert extras.total == 7

    def test_empty_extras(self):
        """Test empty extras."""
        extras = Extras()
        assert extras.total == 0


class TestWicket:
    """Tests for Wicket model."""

    def test_wicket_with_fielder(self):
        """Test wicket with fielder."""
        wicket = Wicket(type="caught", batsman="Kohli", fielder="Smith")
        data = wicket.to_dict()
        assert data["fielder"] == "Smith"

    def test_wicket_without_fielder(self):
        """Test wicket without fielder (bowled)."""
        wicket = Wicket(type="bowled", batsman="Warner")
        data = wicket.to_dict()
        assert "fielder" not in data
