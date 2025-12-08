from rapidfuzz import process, fuzz
from typing import Optional, Tuple, List
from bbl_pipeline.processing.registry import EntityRegistry
import structlog

logger = structlog.get_logger()

class EntityResolver:
    """
    Resolves entity names to canonical IDs using exact and fuzzy matching.
    """
    def __init__(self, registry: EntityRegistry):
        self.registry = registry
        self._build_lookup_lists()

    def _build_lookup_lists(self):
        """Build flattened lists of names for fuzzy matching."""
        self.player_names: List[str] = []
        self.player_ids: List[str] = []
        for pid, data in self.registry.players.items():
            self.player_names.append(data['name'])
            self.player_ids.append(pid)
            for alias in data.get('other_names', []):
                self.player_names.append(alias)
                self.player_ids.append(pid)
                
        self.team_names: List[str] = []
        self.team_ids: List[str] = []
        for tid, data in self.registry.teams.items():
            self.team_names.append(data['name'])
            self.team_ids.append(tid)
            for alias in data.get('other_names', []):
                self.team_names.append(alias)
                self.team_ids.append(tid)
                
        self.venue_names: List[str] = []
        self.venue_ids: List[str] = []
        for vid, data in self.registry.venues.items():
            self.venue_names.append(data['name'])
            self.venue_ids.append(vid)
            for alias in data.get('other_names', []):
                self.venue_names.append(alias)
                self.venue_ids.append(vid)

    def resolve_player(self, name: str, threshold: int = 90) -> Tuple[Optional[str], float]:
        """
        Resolve a player name to an ID.
        Returns (id, score). If id is None, it's a new entity (or below threshold).
        """
        if not name:
            return None, 0.0
            
        # Exact match
        pid = self.registry.get_player_id(name)
        if pid:
            return pid, 100.0
            
        # Fuzzy match
        if not self.player_names:
            return None, 0.0
            
        match = process.extractOne(name, self.player_names, scorer=fuzz.token_sort_ratio)
        if match:
            best_name, score, index = match
            if score >= threshold:
                return self.player_ids[index], score
            return None, score
                
        return None, 0.0

    def resolve_team(self, name: str, threshold: int = 90) -> Tuple[Optional[str], float]:
        """Resolve a team name to an ID."""
        if not name:
            return None, 0.0
            
        tid = self.registry.get_team_id(name)
        if tid:
            return tid, 100.0
            
        if not self.team_names:
            return None, 0.0
            
        match = process.extractOne(name, self.team_names, scorer=fuzz.token_sort_ratio)
        if match:
            best_name, score, index = match
            if score >= threshold:
                return self.team_ids[index], score
            return None, score
            
        return None, 0.0

    def resolve_venue(self, name: str, threshold: int = 90) -> Tuple[Optional[str], float]:
        """Resolve a venue name to an ID."""
        if not name:
            return None, 0.0
            
        vid = self.registry.get_venue_id(name)
        if vid:
            return vid, 100.0
            
        if not self.venue_names:
            return None, 0.0
            
        match = process.extractOne(name, self.venue_names, scorer=fuzz.token_sort_ratio)
        if match:
            best_name, score, index = match
            if score >= threshold:
                return self.venue_ids[index], score
            return None, score
            
        return None, 0.0
