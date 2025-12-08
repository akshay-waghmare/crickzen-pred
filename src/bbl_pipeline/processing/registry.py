import yaml
from pathlib import Path
from typing import Dict, Optional, Any
from dataclasses import dataclass, field

@dataclass
class EntityRegistry:
    """
    In-memory representation of the entity registry.
    """
    players: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    teams: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    venues: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    @classmethod
    def load(cls, path: Path) -> 'EntityRegistry':
        """Load registry from a YAML file."""
        if not path.exists():
            return cls()
            
        with open(path, 'r') as f:
            data = yaml.safe_load(f) or {}
            
        return cls(
            players=data.get('players', {}) or {},
            teams=data.get('teams', {}) or {},
            venues=data.get('venues', {}) or {}
        )
    
    def save(self, path: Path) -> None:
        """Save registry to a YAML file."""
        data = {
            'players': self.players,
            'teams': self.teams,
            'venues': self.venues
        }
        with open(path, 'w') as f:
            yaml.dump(data, f, sort_keys=True)

    def get_player_id(self, name: str) -> Optional[str]:
        """Look up a player ID by name (exact match on canonical or alias)."""
        for pid, data in self.players.items():
            if data.get('name') == name:
                return pid
            if name in data.get('other_names', []):
                return pid
        return None

    def get_team_id(self, name: str) -> Optional[str]:
        """Look up a team ID by name."""
        for tid, data in self.teams.items():
            if data.get('name') == name:
                return tid
            if name in data.get('other_names', []):
                return tid
        return None

    def get_venue_id(self, name: str) -> Optional[str]:
        """Look up a venue ID by name."""
        for vid, data in self.venues.items():
            if data.get('name') == name:
                return vid
            if name in data.get('other_names', []):
                return vid
        return None
