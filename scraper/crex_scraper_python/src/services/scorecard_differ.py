"""
ScorecardDiffer Service - Detect and track scorecard changes.

Feature: 007-fast-updates
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from ..models import ScorecardState, BatsmanStats, BowlerStats

logger = logging.getLogger(__name__)


class ScorecardDiffer:
    """
    Tracks scorecard changes and produces minimal diffs.
    
    Features:
    - Compares scorecard states to detect changes
    - Produces minimal change diffs for efficient updates
    - Tracks staleness for alerting
    """

    def __init__(self, staleness_threshold_seconds: float = 30.0):
        """
        Initialize the scorecard differ.
        
        Args:
            staleness_threshold_seconds: Threshold for considering scorecard stale
        """
        self.staleness_threshold_seconds = staleness_threshold_seconds
        
        # Per-match latest scorecard
        self._scorecards: Dict[Tuple[str, int], ScorecardState] = {}
        # Last update timestamps
        self._last_updates: Dict[Tuple[str, int], datetime] = {}
        # Change history for debugging
        self._change_counts: Dict[str, int] = {}

    def update(self, scorecard: ScorecardState) -> Optional[Dict]:
        """
        Update stored scorecard and return diff if changed.
        
        Args:
            scorecard: New scorecard state
            
        Returns:
            Dict of changes if changed, None if unchanged
        """
        key = (scorecard.match_id, scorecard.innings)
        old_scorecard = self._scorecards.get(key)
        
        now = datetime.now()
        self._last_updates[key] = now
        
        if old_scorecard is None:
            # First scorecard - store and return full as "new"
            self._scorecards[key] = scorecard
            self._change_counts[scorecard.match_id] = 1
            return {
                "type": "new",
                "match_id": scorecard.match_id,
                "innings": scorecard.innings,
                "scorecard": scorecard.to_dict(),
            }

        # Calculate diff
        changes = self._diff(old_scorecard, scorecard)
        
        if changes["has_changes"]:
            self._scorecards[key] = scorecard
            self._change_counts[scorecard.match_id] = (
                self._change_counts.get(scorecard.match_id, 0) + 1
            )
            return changes
        
        return None

    def _diff(self, old: ScorecardState, new: ScorecardState) -> Dict:
        """
        Calculate differences between two scorecard states.
        """
        changes = {
            "type": "diff",
            "match_id": new.match_id,
            "innings": new.innings,
            "has_changes": False,
            "batting_changes": [],
            "bowling_changes": [],
            "new_wickets": [],
            "extras_changed": False,
            "extras_diff": None,
        }

        # Compare batsmen
        old_batsmen = {b.name: b for b in old.batting}
        for batsman in new.batting:
            if batsman.name not in old_batsmen:
                changes["batting_changes"].append({
                    "type": "new",
                    "name": batsman.name,
                    "stats": batsman.to_dict(),
                })
                changes["has_changes"] = True
            else:
                old_bat = old_batsmen[batsman.name]
                bat_diff = self._diff_batsman(old_bat, batsman)
                if bat_diff:
                    changes["batting_changes"].append(bat_diff)
                    changes["has_changes"] = True

        # Compare bowlers
        old_bowlers = {b.name: b for b in old.bowling}
        for bowler in new.bowling:
            if bowler.name not in old_bowlers:
                changes["bowling_changes"].append({
                    "type": "new",
                    "name": bowler.name,
                    "stats": bowler.to_dict(),
                })
                changes["has_changes"] = True
            else:
                old_bowl = old_bowlers[bowler.name]
                bowl_diff = self._diff_bowler(old_bowl, bowler)
                if bowl_diff:
                    changes["bowling_changes"].append(bowl_diff)
                    changes["has_changes"] = True

        # Compare extras
        if old.extras.total != new.extras.total:
            changes["extras_changed"] = True
            changes["extras_diff"] = {
                "old_total": old.extras.total,
                "new_total": new.extras.total,
                "diff": new.extras.total - old.extras.total,
            }
            changes["has_changes"] = True

        # Compare fall of wickets
        old_fow_count = len(old.fall_of_wickets)
        new_fow = new.fall_of_wickets[old_fow_count:]
        if new_fow:
            changes["new_wickets"] = [f.to_dict() for f in new_fow]
            changes["has_changes"] = True

        return changes

    def _diff_batsman(self, old: BatsmanStats, new: BatsmanStats) -> Optional[Dict]:
        """Calculate diff for a single batsman."""
        if (old.runs == new.runs and 
            old.balls == new.balls and 
            old.status == new.status):
            return None
        
        return {
            "type": "updated",
            "name": new.name,
            "runs_added": new.runs - old.runs,
            "balls_added": new.balls - old.balls,
            "fours_added": new.fours - old.fours,
            "sixes_added": new.sixes - old.sixes,
            "status_changed": old.status != new.status,
            "new_status": new.status,
            "dismissal": new.dismissal if new.status == "out" else None,
        }

    def _diff_bowler(self, old: BowlerStats, new: BowlerStats) -> Optional[Dict]:
        """Calculate diff for a single bowler."""
        if (old.overs == new.overs and 
            old.runs == new.runs and 
            old.wickets == new.wickets):
            return None
        
        return {
            "type": "updated",
            "name": new.name,
            "overs_added": new.overs - old.overs,
            "runs_added": new.runs - old.runs,
            "wickets_added": new.wickets - old.wickets,
            "wides_added": new.wides - old.wides,
            "no_balls_added": new.no_balls - old.no_balls,
        }

    def get_scorecard(self, match_id: str, innings: int) -> Optional[ScorecardState]:
        """Get stored scorecard for a match/innings."""
        return self._scorecards.get((match_id, innings))

    def get_staleness_seconds(self, match_id: str, innings: int) -> float:
        """Get seconds since last update for a match/innings."""
        key = (match_id, innings)
        last_update = self._last_updates.get(key)
        if last_update is None:
            return float("inf")
        return (datetime.now() - last_update).total_seconds()

    def is_stale(self, match_id: str, innings: int) -> bool:
        """Check if scorecard is stale."""
        return self.get_staleness_seconds(match_id, innings) > self.staleness_threshold_seconds

    def get_stale_matches(self) -> List[Tuple[str, int, float]]:
        """Get list of matches with stale scorecards."""
        stale = []
        for (match_id, innings), _ in self._scorecards.items():
            staleness = self.get_staleness_seconds(match_id, innings)
            if staleness > self.staleness_threshold_seconds:
                stale.append((match_id, innings, staleness))
        return sorted(stale, key=lambda x: x[2], reverse=True)

    def get_stats(self) -> Dict:
        """Get differ statistics."""
        now = datetime.now()
        stalenesses = [
            (now - ts).total_seconds()
            for ts in self._last_updates.values()
        ]
        
        return {
            "scorecards_tracked": len(self._scorecards),
            "total_changes": sum(self._change_counts.values()),
            "stale_count": sum(1 for s in stalenesses if s > self.staleness_threshold_seconds),
            "avg_staleness_seconds": sum(stalenesses) / len(stalenesses) if stalenesses else 0,
            "max_staleness_seconds": max(stalenesses) if stalenesses else 0,
        }

    def clear_match(self, match_id: str):
        """Clear all scorecards for a match."""
        keys_to_remove = [k for k in self._scorecards.keys() if k[0] == match_id]
        for key in keys_to_remove:
            del self._scorecards[key]
            if key in self._last_updates:
                del self._last_updates[key]
        if match_id in self._change_counts:
            del self._change_counts[match_id]
        logger.debug(f"[{match_id}] Scorecard tracking cleared")

    def clear_all(self):
        """Clear all tracking state."""
        self._scorecards.clear()
        self._last_updates.clear()
        self._change_counts.clear()
        logger.info("All scorecard tracking cleared")
