from typing import Protocol, Dict, Any, Optional
import pandas as pd
from pathlib import Path
import structlog
import difflib

logger = structlog.get_logger()

# Venue alias mapping for handling different venue names
VENUE_ALIASES = {
    # Geelong (Simonds Stadium / Kardinia Park / GMHBA Stadium)
    'Simonds Stadium': 'Simonds Stadium, South Geelong, Victoria',
    'GMHBA Stadium': 'GMHBA Stadium, South Geelong, Victoria',
    'Kardinia Park': 'Simonds Stadium, South Geelong, Victoria',
    'Geelong Cricket Ground': 'Simonds Stadium, South Geelong, Victoria',
    
    # Melbourne Cricket Ground
    'MCG': 'Melbourne Cricket Ground',
    'Melbourne Cricket Ground': 'Melbourne Cricket Ground',
    
    # Sydney Cricket Ground
    'SCG': 'Sydney Cricket Ground',
    'Sydney Cricket Ground': 'Sydney Cricket Ground',
    
    # Perth (WACA / Optus Stadium)
    'WACA Ground': 'Perth Stadium',
    'W.A.C.A. Ground': 'Perth Stadium',
    'Optus Stadium': 'Perth Stadium',
    'Perth Stadium': 'Perth Stadium',
    
    # The Gabba
    'The Gabba': 'Brisbane Cricket Ground',
    'Brisbane Cricket Ground': 'Brisbane Cricket Ground',
    'Gabba': 'Brisbane Cricket Ground',
    
    # Adelaide Oval
    'Adelaide Oval': 'Adelaide Oval',
    
    # Docklands/Marvel Stadium
    'Docklands Stadium': 'Docklands',
    'Marvel Stadium': 'Docklands',
    'Colonial Stadium': 'Docklands',
    'Etihad Stadium': 'Docklands',
    'Docklands': 'Docklands',
    
    # Bellerive Oval
    'Bellerive Oval': 'Bellerive Oval',
    'Blundstone Arena': 'Bellerive Oval',
    
    # Manuka Oval
    'Manuka Oval': 'Manuka Oval',
    
    # Carrara / Metricon Stadium
    'Carrara Oval': 'Carrara Oval',
    'Metricon Stadium': 'Carrara Oval',
    
    # North Sydney Oval
    'North Sydney Oval': 'North Sydney Oval',
    
    # Junction Oval
    'Junction Oval': 'Junction Oval',
    
    # Traeger Park
    'Traeger Park': 'Traeger Park',
    
    # ILT20 Venues
    'Dubai International Cricket Stadium': 'Dubai International Cricket Stadium',
    'Sheikh Zayed Stadium': 'Sheikh Zayed Stadium',
    'Sharjah Cricket Stadium': 'Sharjah Cricket Stadium',
}

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
        self._team_stats: Dict[str, Dict[str, Any]] = {}
        self._player_names_lower: Dict[str, str] = {}
        self._venue_names_lower: Dict[str, str] = {}
        self._team_names_lower: Dict[str, str] = {}
        
        # Player-venue and player-vs-team lookup tables
        self._player_venue_batting: Dict[tuple, Dict[str, Any]] = {}
        self._player_vs_team_batting: Dict[tuple, Dict[str, Any]] = {}
        self._player_venue_bowling: Dict[tuple, Dict[str, Any]] = {}
        self._player_vs_team_bowling: Dict[tuple, Dict[str, Any]] = {}
        
        # Cache for fuzzy-matched names
        self._player_name_cache: Dict[str, str] = {}
        self._venue_name_cache: Dict[str, str] = {}
        self._team_name_cache: Dict[str, str] = {}
        
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
            
        # Load team stats
        team_stats_path = self.player_stats_path.parent / "team_ratings.parquet"
        if team_stats_path.exists():
            try:
                df_team = pd.read_parquet(team_stats_path)
                # Get latest rating for each team
                if 'date' in df_team.columns:
                    df_team = df_team.sort_values('date').groupby('team').last().reset_index()
                
                if 'team' in df_team.columns:
                    df_team = df_team.set_index('team')
                    
                self._team_stats = df_team.to_dict(orient='index')
                self._team_names_lower = {k.lower(): k for k in self._team_stats.keys()}
            except Exception as e:
                logger.error(f"Error loading team stats: {e}")
        
        # Load player-venue and player-vs-team lookup tables
        self._load_player_venue_tables()
        
        self._loaded = True
    
    def _load_player_venue_tables(self):
        """Load player-venue and player-vs-team lookup tables."""
        store_dir = self.player_stats_path.parent
        
        # Player-venue batting stats
        pv_batting_path = store_dir / "player_venue_batting.parquet"
        if pv_batting_path.exists():
            df = pd.read_parquet(pv_batting_path)
            for _, row in df.iterrows():
                key = (row['player'], row['venue'])
                self._player_venue_batting[key] = {
                    'batsman_venue_avg': row['batsman_venue_avg'],
                    'batsman_venue_sr': row['batsman_venue_sr']
                }
            logger.info(f"Loaded {len(self._player_venue_batting)} player-venue batting entries")
        
        # Player-vs-team batting stats
        pvt_batting_path = store_dir / "player_vs_team_batting.parquet"
        if pvt_batting_path.exists():
            df = pd.read_parquet(pvt_batting_path)
            for _, row in df.iterrows():
                key = (row['player'], row['opponent'])
                self._player_vs_team_batting[key] = {
                    'batsman_vs_team_avg': row['batsman_vs_team_avg']
                }
            logger.info(f"Loaded {len(self._player_vs_team_batting)} player-vs-team batting entries")
        
        # Player-venue bowling stats
        pv_bowling_path = store_dir / "player_venue_bowling.parquet"
        if pv_bowling_path.exists():
            df = pd.read_parquet(pv_bowling_path)
            for _, row in df.iterrows():
                key = (row['player'], row['venue'])
                self._player_venue_bowling[key] = {
                    'bowler_venue_econ': row['bowler_venue_econ'],
                    'bowler_venue_sr': row['bowler_venue_sr']
                }
            logger.info(f"Loaded {len(self._player_venue_bowling)} player-venue bowling entries")
        
        # Player-vs-team bowling stats
        pvt_bowling_path = store_dir / "player_vs_team_bowling.parquet"
        if pvt_bowling_path.exists():
            df = pd.read_parquet(pvt_bowling_path)
            for _, row in df.iterrows():
                key = (row['player'], row['opponent'])
                self._player_vs_team_bowling[key] = {
                    'bowler_vs_team_econ': row['bowler_vs_team_econ']
                }
            logger.info(f"Loaded {len(self._player_vs_team_bowling)} player-vs-team bowling entries")

    # Team abbreviation mappings for various tournaments
    TEAM_ABBREVIATIONS = {
        # SMA (Syed Mushtaq Ali Trophy) - Indian domestic T20
        'MUM': 'Mumbai', 'HYD': 'Hyderabad (India)', 'KAR': 'Karnataka', 'DEL': 'Delhi',
        'GUJ': 'Gujarat', 'RAJ': 'Rajasthan', 'TN': 'Tamil Nadu', 'KER': 'Kerala',
        'MP': 'Madhya Pradesh', 'MAH': 'Maharashtra', 'PUN': 'Punjab', 'HAR': 'Haryana',
        'UP': 'Uttar Pradesh', 'BEN': 'Bengal', 'VID': 'Vidarbha', 'SAU': 'Saurashtra',
        'BAR': 'Baroda', 'GOA': 'Goa', 'JHA': 'Jharkhand', 'ODI': 'Odisha',
        'ASM': 'Assam', 'TRI': 'Tripura', 'SER': 'Services', 'HP': 'Himachal Pradesh',
        'HIM': 'Himachal', 'CHG': 'Chhattisgarh', 'JK': 'Jammu & Kashmir', 'AND': 'Andhra',
        'RLY': 'Railways', 'MEG': 'Meghalaya', 'NAG': 'Nagaland', 'MIZ': 'Mizoram',
        'SKM': 'Sikkim', 'MNP': 'Manipur', 'ARN': 'Arunachal Pradesh', 'BIH': 'Bihar',
        'CHD': 'Chandigarh', 'PON': 'Puducherry', 'UTT': 'Uttarakhand',
        # BBL (Big Bash League)
        'SYS-W': 'Sydney Sixers', 'PRS-W': 'Perth Scorchers', 'ADL-W': 'Adelaide Strikers',
        'BRH-W': 'Brisbane Heat', 'MLR-W': 'Melbourne Renegades', 'MLS-W': 'Melbourne Stars',
        'HBH-W': 'Hobart Hurricanes', 'STR-W': 'Sydney Thunder',
        'SYS': 'Sydney Sixers', 'PRS': 'Perth Scorchers', 'ADS': 'Adelaide Strikers',
        'BRH': 'Brisbane Heat', 'MLR': 'Melbourne Renegades', 'MLS': 'Melbourne Stars',
        'HBH': 'Hobart Hurricanes', 'STH': 'Sydney Thunder',
        'SIX': 'Sydney Sixers', 'SCO': 'Perth Scorchers', 'STK': 'Adelaide Strikers',
        'HEA': 'Brisbane Heat', 'REN': 'Melbourne Renegades', 'STA': 'Melbourne Stars',
        'HUR': 'Hobart Hurricanes', 'THU': 'Sydney Thunder',
        # ILT20 (International League T20)
        'DUB': 'Dubai Capitals', 'ABD': 'Abu Dhabi Knight Riders', 'SHA': 'Sharjah Warriors',
        'DSG': 'Desert Vipers', 'GUL': 'Gulf Giants', 'MIC': 'MI Emirates',
        # ILT20 alternate abbreviations (from CREX scraper)
        'DV': 'Desert Vipers', 'GG': 'Gulf Giants', 'MIE': 'MI Emirates',
        'DC': 'Dubai Capitals', 'ADKR': 'Abu Dhabi Knight Riders', 'SW': 'Sharjah Warriors',
    }

    def get_team_stats(self, team_name: str) -> Optional[Dict[str, Any]]:
        if not self._loaded:
            self.load()
            
        if not team_name:
            return None
        
        # 0. Check abbreviation map first
        if team_name.upper() in self.TEAM_ABBREVIATIONS:
            full_name = self.TEAM_ABBREVIATIONS[team_name.upper()]
            if full_name in self._team_stats:
                logger.info(f"Mapped team abbreviation '{team_name}' to '{full_name}'")
                return self._team_stats[full_name]
            
        # 1. Exact match
        if team_name in self._team_stats:
            return self._team_stats[team_name]
            
        # 2. Case-insensitive match
        if team_name.lower() in self._team_names_lower:
            real_name = self._team_names_lower[team_name.lower()]
            return self._team_stats[real_name]
            
        # 3. Fuzzy match
        matches = difflib.get_close_matches(team_name, self._team_stats.keys(), n=1, cutoff=0.6)
        if matches:
            match = matches[0]
            logger.info(f"Fuzzy matched team '{team_name}' to '{match}'")
            return self._team_stats[match]
            
        return None

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

        # 0. Check venue alias mapping first
        if venue_name in VENUE_ALIASES:
            canonical_name = VENUE_ALIASES[venue_name]
            logger.info(f"Resolved venue alias '{venue_name}' to '{canonical_name}'")
            venue_name = canonical_name

        # 1. Exact match
        if venue_name in self._venue_stats:
            logger.info(f"Using venue stats for '{venue_name}'")
            return self._venue_stats[venue_name]
            
        # 2. Case-insensitive match
        if venue_name.lower() in self._venue_names_lower:
            real_name = self._venue_names_lower[venue_name.lower()]
            logger.info(f"Using venue stats for '{real_name}' (case-insensitive match)")
            return self._venue_stats[real_name]
            
        # 3. Fuzzy match (increased cutoff to 0.8 for stricter matching)
        matches = difflib.get_close_matches(venue_name, self._venue_stats.keys(), n=1, cutoff=0.8)
        if matches:
            match = matches[0]
            logger.info(f"Fuzzy matched venue '{venue_name}' to '{match}'")
            return self._venue_stats[match]
        
        logger.warning(f"No venue stats found for '{venue_name}'")
        return None

    def _fuzzy_match_player(self, player_name: str) -> Optional[str]:
        """Fuzzy match a player name to a known player in the store."""
        if not player_name:
            return None
            
        # Check cache first
        if player_name in self._player_name_cache:
            return self._player_name_cache[player_name]
        
        # Get all known player names from the lookup tables
        all_players = set(k[0] for k in self._player_venue_batting.keys())
        all_players.update(k[0] for k in self._player_vs_team_batting.keys())
        all_players.update(k[0] for k in self._player_venue_bowling.keys())
        all_players.update(k[0] for k in self._player_vs_team_bowling.keys())
        all_players.update(self._player_stats.keys())
        
        # 1. Exact match
        if player_name in all_players:
            self._player_name_cache[player_name] = player_name
            return player_name
        
        # 2. Case-insensitive match
        lower_map = {p.lower(): p for p in all_players}
        if player_name.lower() in lower_map:
            match = lower_map[player_name.lower()]
            self._player_name_cache[player_name] = match
            return match
        
        # 3. Fuzzy match
        matches = difflib.get_close_matches(player_name, list(all_players), n=1, cutoff=0.6)
        if matches:
            match = matches[0]
            logger.info(f"Fuzzy matched player '{player_name}' to '{match}'")
            self._player_name_cache[player_name] = match
            return match
        
        return None

    def _fuzzy_match_venue(self, venue_name: str) -> Optional[str]:
        """Fuzzy match a venue name to a known venue in the store."""
        if not venue_name:
            return None
            
        # Check cache first
        if venue_name in self._venue_name_cache:
            return self._venue_name_cache[venue_name]
        
        # Get all known venue names
        all_venues = set(k[1] for k in self._player_venue_batting.keys())
        all_venues.update(k[1] for k in self._player_venue_bowling.keys())
        all_venues.update(self._venue_stats.keys())
        
        # 1. Exact match
        if venue_name in all_venues:
            self._venue_name_cache[venue_name] = venue_name
            return venue_name
        
        # 2. Case-insensitive match
        lower_map = {v.lower(): v for v in all_venues}
        if venue_name.lower() in lower_map:
            match = lower_map[venue_name.lower()]
            self._venue_name_cache[venue_name] = match
            return match
        
        # 3. Check venue aliases
        if venue_name in VENUE_ALIASES:
            canonical = VENUE_ALIASES[venue_name]
            logger.info(f"Resolved venue alias '{venue_name}' to '{canonical}'")
            self._venue_name_cache[venue_name] = canonical
            return canonical
        
        # 4. Fuzzy match (increased cutoff to 0.8)
        matches = difflib.get_close_matches(venue_name, list(all_venues), n=1, cutoff=0.8)
        if matches:
            match = matches[0]
            logger.info(f"Fuzzy matched venue '{venue_name}' to '{match}'")
            self._venue_name_cache[venue_name] = match
            return match
        
        return None

    def _fuzzy_match_team(self, team_name: str) -> Optional[str]:
        """Fuzzy match a team name to a known team in the store."""
        if not team_name:
            return None
        
        # Team abbreviation mapping for WBBL/BBL
        TEAM_ABBREV_MAP = {
            # WBBL abbreviations
            'SYS-W': 'Sydney Sixers',
            'STW': 'Sydney Thunder',
            'STH-W': 'Sydney Thunder',
            'PRS-W': 'Perth Scorchers',
            'HBH-W': 'Hobart Hurricanes',
            'BRH-W': 'Brisbane Heat',
            'MLR-W': 'Melbourne Renegades',
            'MLS-W': 'Melbourne Stars',
            'ADS-W': 'Adelaide Strikers',
            # BBL abbreviations
            'SYS': 'Sydney Sixers',
            'STH': 'Sydney Thunder',
            'PRS': 'Perth Scorchers',
            'HBH': 'Hobart Hurricanes',
            'BRH': 'Brisbane Heat',
            'MLR': 'Melbourne Renegades',
            'MLS': 'Melbourne Stars',
            'ADS': 'Adelaide Strikers',
            # Full names with Women suffix
            'Sydney Sixers Women': 'Sydney Sixers',
            'Sydney Thunder Women': 'Sydney Thunder',
            'Perth Scorchers Women': 'Perth Scorchers',
            'Hobart Hurricanes Women': 'Hobart Hurricanes',
            'Brisbane Heat Women': 'Brisbane Heat',
            'Melbourne Renegades Women': 'Melbourne Renegades',
            'Melbourne Stars Women': 'Melbourne Stars',
            'Adelaide Strikers Women': 'Adelaide Strikers',
        }
        
        # Check abbreviation map first
        if team_name in TEAM_ABBREV_MAP:
            full_name = TEAM_ABBREV_MAP[team_name]
            self._team_name_cache[team_name] = full_name
            return full_name
            
        # Check cache
        if team_name in self._team_name_cache:
            return self._team_name_cache[team_name]
        
        # Get all known team names
        all_teams = set(k[1] for k in self._player_vs_team_batting.keys())
        all_teams.update(k[1] for k in self._player_vs_team_bowling.keys())
        all_teams.update(self._team_stats.keys())
        
        # 1. Exact match
        if team_name in all_teams:
            self._team_name_cache[team_name] = team_name
            return team_name
        
        # 2. Case-insensitive match
        lower_map = {t.lower(): t for t in all_teams}
        if team_name.lower() in lower_map:
            match = lower_map[team_name.lower()]
            self._team_name_cache[team_name] = match
            return match
        
        # 3. Fuzzy match
        matches = difflib.get_close_matches(team_name, list(all_teams), n=1, cutoff=0.6)
        if matches:
            match = matches[0]
            logger.info(f"Fuzzy matched team '{team_name}' to '{match}'")
            self._team_name_cache[team_name] = match
            return match
        
        return None

    def get_player_venue_batting_stats(self, player_name: str, venue_name: str) -> Optional[Dict[str, Any]]:
        """Get batsman stats at a specific venue with fuzzy matching."""
        if not self._loaded:
            self.load()
        
        matched_player = self._fuzzy_match_player(player_name)
        matched_venue = self._fuzzy_match_venue(venue_name)
        
        if matched_player and matched_venue:
            key = (matched_player, matched_venue)
            if key in self._player_venue_batting:
                return self._player_venue_batting[key]
        
        return None

    def get_player_vs_team_batting_stats(self, player_name: str, opponent_team: str) -> Optional[Dict[str, Any]]:
        """Get batsman stats against a specific team with fuzzy matching."""
        if not self._loaded:
            self.load()
        
        matched_player = self._fuzzy_match_player(player_name)
        matched_team = self._fuzzy_match_team(opponent_team)
        
        if matched_player and matched_team:
            key = (matched_player, matched_team)
            if key in self._player_vs_team_batting:
                return self._player_vs_team_batting[key]
        
        return None

    def get_player_venue_bowling_stats(self, player_name: str, venue_name: str) -> Optional[Dict[str, Any]]:
        """Get bowler stats at a specific venue with fuzzy matching."""
        if not self._loaded:
            self.load()
        
        matched_player = self._fuzzy_match_player(player_name)
        matched_venue = self._fuzzy_match_venue(venue_name)
        
        if matched_player and matched_venue:
            key = (matched_player, matched_venue)
            if key in self._player_venue_bowling:
                return self._player_venue_bowling[key]
        
        return None

    def get_player_vs_team_bowling_stats(self, player_name: str, batting_team: str) -> Optional[Dict[str, Any]]:
        """Get bowler stats against a specific team with fuzzy matching."""
        if not self._loaded:
            self.load()
        
        matched_player = self._fuzzy_match_player(player_name)
        matched_team = self._fuzzy_match_team(batting_team)
        
        if matched_player and matched_team:
            key = (matched_player, matched_team)
            if key in self._player_vs_team_bowling:
                return self._player_vs_team_bowling[key]
        
        return None
