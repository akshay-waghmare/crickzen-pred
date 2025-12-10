"""
ScorecardState Model - Detailed batting and bowling statistics.

Feature: 007-fast-updates
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class BatsmanStats:
    """Individual batsman statistics."""
    name: str
    runs: int
    balls: int
    fours: int
    sixes: int
    status: str  # "batting", "out", "retired"
    dismissal: Optional[str] = None  # Dismissal description if out

    @property
    def strike_rate(self) -> float:
        """Calculate strike rate: (runs/balls) × 100."""
        if self.balls == 0:
            return 0.0
        return (self.runs / self.balls) * 100

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        result = {
            "name": self.name,
            "runs": self.runs,
            "balls": self.balls,
            "fours": self.fours,
            "sixes": self.sixes,
            "strike_rate": round(self.strike_rate, 2),
            "status": self.status,
        }
        if self.dismissal:
            result["dismissal"] = self.dismissal
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "BatsmanStats":
        """Create BatsmanStats from dictionary."""
        return cls(
            name=data["name"],
            runs=int(data["runs"]),
            balls=int(data["balls"]),
            fours=int(data["fours"]),
            sixes=int(data["sixes"]),
            status=data["status"],
            dismissal=data.get("dismissal"),
        )


@dataclass
class BowlerStats:
    """Individual bowler statistics."""
    name: str
    overs: float
    maidens: int
    runs: int
    wickets: int
    wides: int = 0
    no_balls: int = 0

    @property
    def economy(self) -> float:
        """Calculate economy rate: runs per over."""
        if self.overs == 0:
            return 0.0
        # Convert overs to total balls for accuracy
        completed_overs = int(self.overs)
        balls_in_current_over = int((self.overs % 1) * 10 + 0.5)
        total_overs = completed_overs + balls_in_current_over / 6
        return self.runs / total_overs if total_overs > 0 else 0.0

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "overs": self.overs,
            "maidens": self.maidens,
            "runs": self.runs,
            "wickets": self.wickets,
            "economy": round(self.economy, 2),
            "wides": self.wides,
            "no_balls": self.no_balls,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "BowlerStats":
        """Create BowlerStats from dictionary."""
        return cls(
            name=data["name"],
            overs=float(data["overs"]),
            maidens=int(data["maidens"]),
            runs=int(data["runs"]),
            wickets=int(data["wickets"]),
            wides=int(data.get("wides", 0)),
            no_balls=int(data.get("no_balls", 0)),
        )


@dataclass
class FallOfWicket:
    """Record of when a wicket fell."""
    wicket_number: int  # 1st, 2nd, etc.
    runs: int  # Team score when wicket fell
    overs: float  # Overs when wicket fell
    batsman: str  # Name of dismissed batsman

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "wicket_number": self.wicket_number,
            "runs": self.runs,
            "overs": self.overs,
            "batsman": self.batsman,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "FallOfWicket":
        """Create FallOfWicket from dictionary."""
        return cls(
            wicket_number=int(data["wicket_number"]),
            runs=int(data["runs"]),
            overs=float(data["overs"]),
            batsman=data["batsman"],
        )


@dataclass
class ScorecardExtras:
    """Breakdown of extras for an innings."""
    byes: int = 0
    leg_byes: int = 0
    wides: int = 0
    no_balls: int = 0
    penalty: int = 0

    @property
    def total(self) -> int:
        """Total extras."""
        return self.byes + self.leg_byes + self.wides + self.no_balls + self.penalty

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "byes": self.byes,
            "leg_byes": self.leg_byes,
            "wides": self.wides,
            "no_balls": self.no_balls,
            "penalty": self.penalty,
            "total": self.total,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ScorecardExtras":
        """Create ScorecardExtras from dictionary."""
        return cls(
            byes=int(data.get("byes", 0)),
            leg_byes=int(data.get("leg_byes", 0)),
            wides=int(data.get("wides", 0)),
            no_balls=int(data.get("no_balls", 0)),
            penalty=int(data.get("penalty", 0)),
        )


@dataclass
class ScorecardState:
    """
    Detailed batting and bowling statistics for an innings.
    
    Identity: (match_id, innings)
    """
    match_id: str
    innings: int
    batting: List[BatsmanStats]
    bowling: List[BowlerStats]
    extras: ScorecardExtras
    fall_of_wickets: List[FallOfWicket]
    timestamp: datetime
    team_name: str = ""  # Batting team name

    def __post_init__(self):
        """Validate the ScorecardState after initialization."""
        self._validate()

    def _validate(self):
        """Validate all fields."""
        if not self.match_id or not isinstance(self.match_id, str):
            raise ValueError("match_id must be a non-empty string")

        if self.innings not in (1, 2):
            raise ValueError(f"innings must be 1 or 2, got {self.innings}")

        if not isinstance(self.batting, list):
            raise ValueError("batting must be a list")

        if not isinstance(self.bowling, list):
            raise ValueError("bowling must be a list")

    @property
    def total_runs(self) -> int:
        """Total runs scored (batting runs + extras)."""
        batting_runs = sum(b.runs for b in self.batting)
        return batting_runs + self.extras.total

    @property
    def wickets_fallen(self) -> int:
        """Number of wickets fallen."""
        return len([b for b in self.batting if b.status == "out"])

    @property
    def current_batsmen(self) -> List[BatsmanStats]:
        """Get currently batting players."""
        return [b for b in self.batting if b.status == "batting"]

    @property
    def highest_scorer(self) -> Optional[BatsmanStats]:
        """Get the highest scorer."""
        if not self.batting:
            return None
        return max(self.batting, key=lambda b: b.runs)

    @property
    def best_bowler(self) -> Optional[BowlerStats]:
        """Get the best bowler (most wickets, then best economy)."""
        if not self.bowling:
            return None
        return max(self.bowling, key=lambda b: (b.wickets, -b.economy))

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "match_id": self.match_id,
            "innings": self.innings,
            "team_name": self.team_name,
            "batting": [b.to_dict() for b in self.batting],
            "bowling": [b.to_dict() for b in self.bowling],
            "extras": self.extras.to_dict(),
            "fall_of_wickets": [f.to_dict() for f in self.fall_of_wickets],
            "timestamp": self.timestamp.isoformat(),
            "total_runs": self.total_runs,
            "wickets_fallen": self.wickets_fallen,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ScorecardState":
        """Create ScorecardState from dictionary."""
        timestamp = data["timestamp"]
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

        return cls(
            match_id=data["match_id"],
            innings=int(data["innings"]),
            team_name=data.get("team_name", ""),
            batting=[BatsmanStats.from_dict(b) for b in data.get("batting", [])],
            bowling=[BowlerStats.from_dict(b) for b in data.get("bowling", [])],
            extras=ScorecardExtras.from_dict(data.get("extras", {})),
            fall_of_wickets=[FallOfWicket.from_dict(f) for f in data.get("fall_of_wickets", [])],
            timestamp=timestamp,
        )

    def diff(self, other: "ScorecardState") -> dict:
        """
        Calculate differences between two scorecard states.
        Returns a dict of changes for efficient partial updates.
        """
        if other.match_id != self.match_id or other.innings != self.innings:
            raise ValueError("Cannot diff scorecards from different matches/innings")

        changes = {
            "batting_changes": [],
            "bowling_changes": [],
            "new_wickets": [],
            "extras_changed": False,
        }

        # Track batsman changes
        other_batsmen = {b.name: b for b in other.batting}
        for batsman in self.batting:
            if batsman.name in other_batsmen:
                old = other_batsmen[batsman.name]
                if batsman.runs != old.runs or batsman.balls != old.balls:
                    changes["batting_changes"].append({
                        "name": batsman.name,
                        "runs_added": batsman.runs - old.runs,
                        "balls_added": batsman.balls - old.balls,
                    })
            else:
                changes["batting_changes"].append({
                    "name": batsman.name,
                    "new_batsman": True,
                })

        # Track new wickets
        old_wicket_count = len(other.fall_of_wickets)
        for wicket in self.fall_of_wickets[old_wicket_count:]:
            changes["new_wickets"].append(wicket.to_dict())

        # Check extras changes
        if self.extras.total != other.extras.total:
            changes["extras_changed"] = True

        return changes

    def __str__(self) -> str:
        """Human-readable string representation."""
        return f"Scorecard {self.match_id} Innings {self.innings}: {self.total_runs}/{self.wickets_fallen}"
