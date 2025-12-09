from typing import Protocol, Dict, Any, Optional
import pandas as pd
from pathlib import Path
import structlog
import difflib

logger = structlog.get_logger()

class FeatureStore(Protocol):
    def get_player_stats(self, player_name: str) -> Optional[Dict[str, Any]]:
        """Retrieve rolling stats for a player."""
        ...

    def get_venue_stats(self, venue_name: str) -> Optional[Dict[str, Any]]:
        """Retrieve stats for a venue."""
        ...

class InMemoryFeatureStore:
    def __init__(self, player_stats_path: str | Path, venue_stats_path: str | Path):
        self.player_stats_path = Path(player_stats_path)
        self.venue_stats_path = Path(venue_stats_path)
        self._player_stats: Dict[str, Dict[str, Any]] = {}
        self._venue_stats: Dict[str, Dict[str, Any]] = {}
        self._player_names_lower: Dict[str, str] = {}
        self._venue_names_lower: Dict[str, str] = {}
        self._loaded = False

    def load(self):
        """Load stats from parquet files into memory."""
        if self.player_stats_path.exists():
            df_player = pd.read_parquet(self.player_stats_path)
            # Assuming player_name is the index or a column
            if 'player_name' in df_player.columns:
                df_player = df_player.set_index('player_name')
            self._player_stats = df_player.to_dict(orient='index')
            # Create case-insensitive map
            self._player_names_lower = {k.lower(): k for k in self._player_stats.keys()}
        else:
            logger.warning(f"Player stats file not found: {self.player_stats_path}")

        if self.venue_stats_path.exists():
            df_venue = pd.read_parquet(self.venue_stats_path)
            if 'venue' in df_venue.columns:
                df_venue = df_venue.set_index('venue')
            self._venue_stats = df_venue.to_dict(orient='index')
            # Create case-insensitive map
            self._venue_names_lower = {k.lower(): k for k in self._venue_stats.keys()}
        else:
            logger.warning(f"Venue stats file not found: {self.venue_stats_path}")
        
        self._loaded = True

    def get_player_stats(self, player_name: str) -> Optional[Dict[str, Any]]:
        if not self._loaded:
            self.load()
        
        if not player_name:
            return None

        # 1. Exact match
        if player_name in self._player_stats:
            return self._player_stats[player_name]
            
        # 2. Case-insensitive match
        if player_name.lower() in self._player_names_lower:
            real_name = self._player_names_lower[player_name.lower()]
            return self._player_stats[real_name]
            
        # 3. Fuzzy match (e.g. "v. kohli" -> "V Kohli")
        matches = difflib.get_close_matches(player_name, self._player_stats.keys(), n=1, cutoff=0.6)
        if matches:
            match = matches[0]
            logger.info(f"Fuzzy matched player '{player_name}' to '{match}'")
            return self._player_stats[match]
            
        return None

    def get_venue_stats(self, venue_name: str) -> Optional[Dict[str, Any]]:
        if not self._loaded:
            self.load()
            
        if not venue_name:
            return None

        # 1. Exact match
        if venue_name in self._venue_stats:
            return self._venue_stats[venue_name]
            
        # 2. Case-insensitive match
        if venue_name.lower() in self._venue_names_lower:
            real_name = self._venue_names_lower[venue_name.lower()]
            return self._venue_stats[real_name]
            
        # 3. Fuzzy match
        matches = difflib.get_close_matches(venue_name, self._venue_stats.keys(), n=1, cutoff=0.6)
        if matches:
            match = matches[0]
            logger.info(f"Fuzzy matched venue '{venue_name}' to '{match}'")
            return self._venue_stats[match]
            
        return None
