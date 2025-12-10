"""
ScoreParser Service - Parse sV3 score data into structured models.

Feature: 007-fast-updates
"""

import logging
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from ..models import BallEvent, Extras, Wicket, ScoreSnapshot

logger = logging.getLogger(__name__)


class ScoreParser:
    """
    Parses sV3 API responses into structured models.
    
    The sV3 endpoint returns live score updates in a compact format.
    This parser extracts ball-by-ball and score data.
    """

    # Pattern for ball number in sV3 response (e.g., "9.4" = over 9, ball 4)
    BALL_PATTERN = re.compile(r"(\d+)\.(\d)")
    
    # Pattern for score format (e.g., "145/3" = 145 runs, 3 wickets)
    SCORE_PATTERN = re.compile(r"(\d+)/(\d+)")
    
    # Pattern for overs format (e.g., "15.4" = 15 overs, 4 balls)
    OVERS_PATTERN = re.compile(r"(\d+)\.?(\d)?")

    def __init__(self, match_id: str):
        """
        Initialize the parser for a specific match.
        
        Args:
            match_id: Unique match identifier
        """
        self.match_id = match_id
        self._sequence_counter = 0

    def parse_sv3_response(self, data: Dict) -> Tuple[Optional[ScoreSnapshot], Optional[BallEvent]]:
        """
        Parse sV3 API response into ScoreSnapshot and optional BallEvent.
        
        Args:
            data: Raw sV3 response dictionary
            
        Returns:
            Tuple of (ScoreSnapshot, BallEvent) - BallEvent may be None if no new ball
        """
        try:
            score_snapshot = self._parse_score_snapshot(data)
            ball_event = self._parse_ball_event(data)
            return score_snapshot, ball_event
        except Exception as e:
            logger.error(f"Error parsing sV3 response for match {self.match_id}: {e}")
            return None, None

    def _parse_score_snapshot(self, data: Dict) -> Optional[ScoreSnapshot]:
        """Extract ScoreSnapshot from sV3 data."""
        try:
            # Common sV3 field mappings (adjust based on actual API response)
            innings = self._extract_innings(data)
            batting_team = data.get("bat", {}).get("team", "Unknown")
            
            # Parse score
            score_str = data.get("score", "0/0")
            runs, wickets = self._parse_score_string(score_str)
            
            # Parse overs
            overs_str = data.get("overs", "0.0")
            overs = self._parse_overs_string(overs_str)
            
            # Calculate run rate
            run_rate = self._calculate_run_rate(runs, overs)
            
            # Second innings fields
            target = data.get("target")
            required_rate = None
            if target and innings == 2:
                runs_needed = target - runs
                balls_remaining = self._calculate_balls_remaining(overs, data.get("max_overs", 20))
                if balls_remaining > 0:
                    required_rate = (runs_needed / balls_remaining) * 6

            self._sequence_counter += 1
            
            return ScoreSnapshot(
                match_id=self.match_id,
                innings=innings,
                batting_team=batting_team,
                runs=runs,
                wickets=wickets,
                overs=overs,
                run_rate=run_rate,
                timestamp=datetime.now(),
                sequence_number=self._sequence_counter,
                required_rate=required_rate,
                target=target,
            )
        except Exception as e:
            logger.warning(f"Failed to parse score snapshot: {e}")
            return None

    def _parse_ball_event(self, data: Dict) -> Optional[BallEvent]:
        """Extract BallEvent from sV3 data if a new ball occurred."""
        try:
            # Check if there's new ball data
            ball_data = data.get("last_ball") or data.get("curr_ball") or data.get("lb")
            if not ball_data:
                return None

            ball_number = self._parse_ball_number(ball_data.get("ball", "0.1"))
            runs = int(ball_data.get("runs", 0))
            
            # Parse extras if present
            extras = self._parse_extras(ball_data.get("extras", {}))
            
            # Parse wicket if present
            wicket = self._parse_wicket(ball_data.get("wicket", {}))

            self._sequence_counter += 1
            
            return BallEvent(
                match_id=self.match_id,
                ball_number=ball_number,
                runs=runs,
                timestamp=datetime.now(),
                sequence_number=self._sequence_counter,
                extras=extras,
                wicket=wicket,
            )
        except Exception as e:
            logger.warning(f"Failed to parse ball event: {e}")
            return None

    def _extract_innings(self, data: Dict) -> int:
        """Extract current innings number."""
        innings = data.get("innings", 1)
        if isinstance(innings, str):
            # Handle "1st", "2nd" format
            innings = 1 if "1" in innings else 2
        return int(innings)

    def _parse_score_string(self, score_str: str) -> Tuple[int, int]:
        """Parse 'runs/wickets' format."""
        match = self.SCORE_PATTERN.search(str(score_str))
        if match:
            return int(match.group(1)), int(match.group(2))
        return 0, 0

    def _parse_overs_string(self, overs_str: str) -> float:
        """Parse overs string to float."""
        try:
            overs_str = str(overs_str).strip()
            if "." in overs_str:
                parts = overs_str.split(".")
                over = int(parts[0])
                balls = int(parts[1]) if len(parts) > 1 else 0
                return float(f"{over}.{min(balls, 6)}")
            return float(overs_str)
        except (ValueError, TypeError):
            return 0.0

    def _parse_ball_number(self, ball_str: str) -> float:
        """Parse ball number to float (e.g., '9.4' -> 9.4)."""
        try:
            ball_str = str(ball_str).strip()
            if "." in ball_str:
                parts = ball_str.split(".")
                over = int(parts[0])
                ball = int(parts[1]) if len(parts) > 1 else 1
                # Ensure ball is 1-6
                ball = max(1, min(6, ball))
                return float(f"{over}.{ball}")
            return float(ball_str) + 0.1  # Assume first ball of over
        except (ValueError, TypeError):
            return 0.1

    def _calculate_run_rate(self, runs: int, overs: float) -> float:
        """Calculate current run rate."""
        if overs <= 0:
            return 0.0
        # Convert overs to actual overs (0.3 = 0.5 actual overs)
        completed_overs = int(overs)
        balls = int((overs % 1) * 10 + 0.5)
        total_overs = completed_overs + (balls / 6)
        return round(runs / total_overs, 2) if total_overs > 0 else 0.0

    def _calculate_balls_remaining(self, current_overs: float, max_overs: int) -> int:
        """Calculate balls remaining in innings."""
        completed_overs = int(current_overs)
        balls_in_current_over = int((current_overs % 1) * 10 + 0.5)
        balls_faced = completed_overs * 6 + balls_in_current_over
        total_balls = max_overs * 6
        return max(0, total_balls - balls_faced)

    def _parse_extras(self, extras_data: Dict) -> Optional[Extras]:
        """Parse extras from ball data."""
        if not extras_data:
            return None
        
        wides = int(extras_data.get("wd", 0) or extras_data.get("wides", 0))
        no_balls = int(extras_data.get("nb", 0) or extras_data.get("no_balls", 0))
        byes = int(extras_data.get("b", 0) or extras_data.get("byes", 0))
        leg_byes = int(extras_data.get("lb", 0) or extras_data.get("leg_byes", 0))
        
        if wides or no_balls or byes or leg_byes:
            return Extras(wides=wides, no_balls=no_balls, byes=byes, leg_byes=leg_byes)
        return None

    def _parse_wicket(self, wicket_data: Dict) -> Optional[Wicket]:
        """Parse wicket from ball data."""
        if not wicket_data or not wicket_data.get("type"):
            return None
        
        return Wicket(
            type=wicket_data.get("type", "unknown"),
            batsman=wicket_data.get("batsman", "Unknown"),
            fielder=wicket_data.get("fielder"),
        )

    def reset_sequence(self):
        """Reset sequence counter (e.g., for new innings)."""
        self._sequence_counter = 0

    @staticmethod
    def parse_compact_score(compact: str) -> Dict:
        """
        Parse compact score format used in some sV3 responses.
        
        Format: "TEAM_RUNS_WICKETS_OVERS" (e.g., "IND_156_3_18.2")
        """
        parts = compact.split("_")
        if len(parts) >= 4:
            return {
                "team": parts[0],
                "runs": int(parts[1]),
                "wickets": int(parts[2]),
                "overs": float(parts[3]),
            }
        return {}
