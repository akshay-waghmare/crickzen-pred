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
    
    # International Sports Stadium, Coffs Harbour (BBL regional venue)
    'International Sports Stadium': 'International Sports Stadium, Coffs Harbour',
    'International Sports Stadium, Coffs Harbour': 'International Sports Stadium, Coffs Harbour',
    'C.ex Coffs International Stadium': 'International Sports Stadium, Coffs Harbour',
    'Coffs Harbour Stadium': 'International Sports Stadium, Coffs Harbour',
    
    # ILT20 Venues
    'Dubai International Cricket Stadium': 'Dubai International Cricket Stadium',
    'Sheikh Zayed Stadium': 'Zayed Cricket Stadium, Abu Dhabi',
    'Sharjah Cricket Stadium': 'Sharjah Cricket Stadium',
    'Zayed Cricket Stadium': 'Zayed Cricket Stadium, Abu Dhabi',

    # SA20 Venues
    'Kingsmead': 'Kingsmead, Durban',
    'Kingsmead, Durban': 'Kingsmead, Durban',
    'Durban Hollywoodbets Kingsmead Cricket Stadium': 'Kingsmead, Durban',
    'Hollywoodbets Kingsmead Stadium': 'Kingsmead, Durban',
    'Hollywoodbets Kingsmead': 'Kingsmead, Durban',
    'Newlands': 'Newlands, Cape Town',
    'Newlands, Cape Town': 'Newlands, Cape Town',
    'Newlands Cricket Ground': 'Newlands, Cape Town',
    'Boland Park': 'Boland Park, Paarl',
    'Boland Park, Paarl': 'Boland Park, Paarl',
    'Boland Park Paarl': 'Boland Park, Paarl',
    "St George's Park": "St George's Park, Gqeberha",
    "St George's Park, Gqeberha": "St George's Park, Gqeberha",
    'St Georges Park': "St George's Park, Gqeberha",
    'SuperSport Park': 'SuperSport Park, Centurion',
    'SuperSport Park, Centurion': 'SuperSport Park, Centurion',
    'SuperSport Park Centurion': 'SuperSport Park, Centurion',
    'The Wanderers Stadium': 'The Wanderers Stadium, Johannesburg',
    'The Wanderers Stadium, Johannesburg': 'The Wanderers Stadium, Johannesburg',
    'Wanderers': 'The Wanderers Stadium, Johannesburg',
    'Wanderers Stadium': 'The Wanderers Stadium, Johannesburg',
    'Wanderers, Johannesburg': 'The Wanderers Stadium, Johannesburg',
    
    # BPL Venues (Bangladesh Premier League)
    'Shere Bangla National Stadium': 'Shere Bangla National Stadium, Mirpur',
    'Shere Bangla National Stadium, Mirpur': 'Shere Bangla National Stadium, Mirpur',
    'Mirpur Stadium': 'Shere Bangla National Stadium, Mirpur',
    'Sylhet International Cricket Stadium': 'Sylhet International Cricket Stadium',
    'Sylhet Stadium': 'Sylhet International Cricket Stadium',
    'Zahur Ahmed Chowdhury Stadium': 'Zahur Ahmed Chowdhury Stadium, Chattogram',
    'Zahur Ahmed Chowdhury Stadium, Chattogram': 'Zahur Ahmed Chowdhury Stadium, Chattogram',
    'Zahur Ahmed Chowdhury Stadium, Chittagong': 'Zahur Ahmed Chowdhury Stadium, Chattogram',
    'Chittagong Stadium': 'Zahur Ahmed Chowdhury Stadium, Chattogram',
    'Chattogram Stadium': 'Zahur Ahmed Chowdhury Stadium, Chattogram',
    'Sheikh Abu Naser Stadium': 'Sheikh Abu Naser Stadium, Khulna',
    'Sheikh Abu Naser Stadium, Khulna': 'Sheikh Abu Naser Stadium, Khulna',
    'Khulna Stadium': 'Sheikh Abu Naser Stadium, Khulna',
    'MA Aziz Stadium': 'MA Aziz Stadium, Chittagong',
    'MA Aziz Stadium, Chittagong': 'MA Aziz Stadium, Chittagong',
    
    # New Zealand Venues (Super Smash)
    'Basin Reserve': 'Basin Reserve, Wellington',
    'Basin Reserve, Wellington': 'Basin Reserve, Wellington',
    'Eden Park': 'Eden Park, Auckland',
    'Eden Park, Auckland': 'Eden Park, Auckland',
    'Eden Park Outer Oval': 'Eden Park Outer Oval, Auckland',
    'Eden Park Outer Oval, Auckland': 'Eden Park Outer Oval, Auckland',
    'Hagley Oval': 'Hagley Oval, Christchurch',
    'Hagley Oval, Christchurch': 'Hagley Oval, Christchurch',
    'Seddon Park': 'Seddon Park, Hamilton',
    'Seddon Park, Hamilton': 'Seddon Park, Hamilton',
    'Bay Oval': 'Bay Oval, Mount Maunganui',
    'Bay Oval, Mount Maunganui': 'Bay Oval, Mount Maunganui',
    'McLean Park': 'McLean Park, Napier',
    'McLean Park, Napier': 'McLean Park, Napier',
    'University Oval': 'University Oval, Dunedin',
    'University Oval, Dunedin': 'University Oval, Dunedin',
    'University of Otago Oval': 'University Oval, Dunedin',  # Same venue, different name
    'University of Otago Oval, Dunedin': 'University Oval, Dunedin',  # Same venue, different name
    'Saxton Oval': 'Saxton Oval, Nelson',
    'Saxton Oval, Nelson': 'Saxton Oval, Nelson',
    'Pukekura Park': 'Pukekura Park, New Plymouth',
    'Pukekura Park, New Plymouth': 'Pukekura Park, New Plymouth',
    'Molyneux Park': 'Molyneux Park, Alexandra',
    'Molyneux Park, Alexandra': 'Molyneux Park, Alexandra',
    'John Davies Oval': 'John Davies Oval, Queenstown',
    'John Davies Oval, Queenstown': 'John Davies Oval, Queenstown',
    'Fitzherbert Park': 'Fitzherbert Park, Palmerston North',
    'Fitzherbert Park, Palmerston North': 'Fitzherbert Park, Palmerston North',
    'Cobham Oval': 'Cobham Oval (New), Whangarei',
    'Cobham Oval (New), Whangarei': 'Cobham Oval (New), Whangarei',
    
    # WPL (Women's Premier League - India) Venues
    'Arun Jaitley Stadium': 'Arun Jaitley Stadium, Delhi',
    'Arun Jaitley Stadium, Delhi': 'Arun Jaitley Stadium, Delhi',
    'Feroz Shah Kotla': 'Arun Jaitley Stadium, Delhi',
    'M Chinnaswamy Stadium': 'M Chinnaswamy Stadium, Bengaluru',
    'M Chinnaswamy Stadium, Bengaluru': 'M Chinnaswamy Stadium, Bengaluru',
    'Chinnaswamy Stadium': 'M Chinnaswamy Stadium, Bengaluru',
    'Brabourne Stadium': 'Brabourne Stadium, Mumbai',
    'Brabourne Stadium, Mumbai': 'Brabourne Stadium, Mumbai',
    'CCI Brabourne Stadium': 'Brabourne Stadium, Mumbai',
    'Dr DY Patil Sports Academy': 'Dr DY Patil Sports Academy, Mumbai',
    'Dr DY Patil Sports Academy, Mumbai': 'Dr DY Patil Sports Academy, Mumbai',
    'DY Patil Stadium': 'Dr DY Patil Sports Academy, Mumbai',
    'Bharat Ratna Shri Atal Bihari Vajpayee Ekana Cricket Stadium': 'Bharat Ratna Shri Atal Bihari Vajpayee Ekana Cricket Stadium, Lucknow',
    'Bharat Ratna Shri Atal Bihari Vajpayee Ekana Cricket Stadium, Lucknow': 'Bharat Ratna Shri Atal Bihari Vajpayee Ekana Cricket Stadium, Lucknow',
    'Ekana Cricket Stadium': 'Bharat Ratna Shri Atal Bihari Vajpayee Ekana Cricket Stadium, Lucknow',
    'Ekana Stadium': 'Bharat Ratna Shri Atal Bihari Vajpayee Ekana Cricket Stadium, Lucknow',
    'Lucknow Stadium': 'Bharat Ratna Shri Atal Bihari Vajpayee Ekana Cricket Stadium, Lucknow',
    'Kotambi Stadium': 'Kotambi Stadium, Vadodara',
    'Kotambi Stadium, Vadodara': 'Kotambi Stadium, Vadodara',
    'Vadodara Stadium': 'Kotambi Stadium, Vadodara',
    
    # T20 International Venues (India)
    'Wankhede Stadium': 'Wankhede Stadium, Mumbai',
    'Wankhede Stadium, Mumbai': 'Wankhede Stadium, Mumbai',
    'Eden Gardens': 'Eden Gardens, Kolkata',
    'Eden Gardens, Kolkata': 'Eden Gardens, Kolkata',
    'MA Chidambaram Stadium': 'MA Chidambaram Stadium, Chepauk, Chennai',
    'MA Chidambaram Stadium, Chepauk, Chennai': 'MA Chidambaram Stadium, Chepauk, Chennai',
    'Chepauk': 'MA Chidambaram Stadium, Chepauk, Chennai',
    'Punjab Cricket Association IS Bindra Stadium': 'Punjab Cricket Association IS Bindra Stadium, Mohali',
    'Punjab Cricket Association IS Bindra Stadium, Mohali': 'Punjab Cricket Association IS Bindra Stadium, Mohali',
    'Punjab Cricket Association IS Bindra Stadium, Mohali, Chandigarh': 'Punjab Cricket Association IS Bindra Stadium, Mohali',
    'Mohali Stadium': 'Punjab Cricket Association IS Bindra Stadium, Mohali',
    'PCA Stadium': 'Punjab Cricket Association IS Bindra Stadium, Mohali',
    'Rajiv Gandhi International Stadium': 'Rajiv Gandhi International Stadium, Uppal, Hyderabad',
    'Rajiv Gandhi International Stadium, Uppal, Hyderabad': 'Rajiv Gandhi International Stadium, Uppal, Hyderabad',
    'Rajiv Gandhi International Stadium, Hyderabad': 'Rajiv Gandhi International Stadium, Uppal, Hyderabad',
    'Uppal Stadium': 'Rajiv Gandhi International Stadium, Uppal, Hyderabad',
    'Narendra Modi Stadium': 'Narendra Modi Stadium, Ahmedabad',
    'Narendra Modi Stadium, Ahmedabad': 'Narendra Modi Stadium, Ahmedabad',
    'Motera Stadium': 'Narendra Modi Stadium, Ahmedabad',
    'Sardar Patel Stadium': 'Narendra Modi Stadium, Ahmedabad',
    'Sawai Mansingh Stadium': 'Sawai Mansingh Stadium, Jaipur',
    'Sawai Mansingh Stadium, Jaipur': 'Sawai Mansingh Stadium, Jaipur',
    'Jaipur Stadium': 'Sawai Mansingh Stadium, Jaipur',
    'Maharashtra Cricket Association Stadium': 'Maharashtra Cricket Association Stadium, Pune',
    'Maharashtra Cricket Association Stadium, Pune': 'Maharashtra Cricket Association Stadium, Pune',
    'MCA Stadium': 'Maharashtra Cricket Association Stadium, Pune',
    'Pune Stadium': 'Maharashtra Cricket Association Stadium, Pune',
    'Himachal Pradesh Cricket Association Stadium': 'Himachal Pradesh Cricket Association Stadium, Dharamsala',
    'Himachal Pradesh Cricket Association Stadium, Dharamsala': 'Himachal Pradesh Cricket Association Stadium, Dharamsala',
    'HPCA Stadium': 'Himachal Pradesh Cricket Association Stadium, Dharamsala',
    'Dharamsala Stadium': 'Himachal Pradesh Cricket Association Stadium, Dharamsala',
    'Holkar Cricket Stadium': 'Holkar Cricket Stadium, Indore',
    'Holkar Cricket Stadium, Indore': 'Holkar Cricket Stadium, Indore',
    'Indore Stadium': 'Holkar Cricket Stadium, Indore',
    'Vidarbha Cricket Association Stadium': 'Vidarbha Cricket Association Stadium, Jamtha, Nagpur',
    'Vidarbha Cricket Association Stadium, Jamtha, Nagpur': 'Vidarbha Cricket Association Stadium, Jamtha, Nagpur',
    'VCA Stadium': 'Vidarbha Cricket Association Stadium, Jamtha, Nagpur',
    'Nagpur Stadium': 'Vidarbha Cricket Association Stadium, Jamtha, Nagpur',
    'Saurashtra Cricket Association Stadium': 'Saurashtra Cricket Association Stadium, Rajkot',
    'Saurashtra Cricket Association Stadium, Rajkot': 'Saurashtra Cricket Association Stadium, Rajkot',
    'SCA Stadium': 'Saurashtra Cricket Association Stadium, Rajkot',
    'Rajkot Stadium': 'Saurashtra Cricket Association Stadium, Rajkot',
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
        'HBH': 'Hobart Hurricanes', 'STH': 'Sydney Thunder', 'SYT': 'Sydney Thunder',
        'SIX': 'Sydney Sixers', 'SCO': 'Perth Scorchers', 'STK': 'Adelaide Strikers',
        'HEA': 'Brisbane Heat', 'REN': 'Melbourne Renegades', 'STA': 'Melbourne Stars',
        'HUR': 'Hobart Hurricanes', 'THU': 'Sydney Thunder',
        # ILT20 (International League T20)
        'DUB': 'Dubai Capitals', 'ABD': 'Abu Dhabi Knight Riders', 'SHA': 'Sharjah Warriors',
        'DES': 'Desert Vipers', 'GUL': 'Gulf Giants', 'MIC': 'MI Emirates',
        # ILT20 alternate abbreviations (from CREX scraper)
        'DV': 'Desert Vipers', 'GG': 'Gulf Giants', 'MIE': 'MI Emirates',
        'DC': 'Dubai Capitals', 'ADKR': 'Abu Dhabi Knight Riders', 'SW': 'Sharjah Warriors',
        
        # SA20 (South Africa T20)
        'DSG': "Durban's Super Giants",
        'MICT': 'MI Cape Town',
        'PR': 'Paarl Royals',
        'JSK': 'Joburg Super Kings',
        'PC': 'Pretoria Capitals',
        'SEC': 'Sunrisers Eastern Cape',
        'SUNE': 'Sunrisers Eastern Cape',
        
        # SSM (Super Smash - New Zealand)
        'OTG': 'Otago',
        'NB': 'Northern Districts',
        'AKL': 'Auckland',
        'CD': 'Central Districts',
        'CK': 'Canterbury',
        'WEL': 'Wellington',
        'ND': 'Northern Districts',
        
        # Women's Super Smash (New Zealand - CREX codes)
        'AHW': 'Auckland',  # Auckland Hearts Women
        'OSW': 'Otago',      # Otago Sparks Women
        'WBW': 'Wellington', # Wellington Blaze Women
        'CMW': 'Canterbury', # Canterbury Magicians Women
        'CSW': 'Central Districts',  # Central Hinds Women (alt code)
        'CHW': 'Central Districts',  # Central Hinds Women
        'NDW': 'Northern Districts', # Northern Brave Women
        'NBW': 'Northern Districts', # Northern Brave Women (alt code)
        
        # WPL (Women's Premier League - India)
        'MIW': 'Mumbai Indians',           # Mumbai Indians Women
        'RCBW': 'Royal Challengers Bengaluru',  # RCB Women (now Bengaluru)
        'DCW': 'Delhi Capitals',           # Delhi Capitals Women
        'GGW': 'Gujarat Giants',           # Gujarat Giants Women
        'UPW': 'UP Warriorz',              # UP Warriorz Women
        'MI-W': 'Mumbai Indians',          # Alternate format
        'RCB-W': 'Royal Challengers Bengaluru',
        'DC-W': 'Delhi Capitals',
        'GG-W': 'Gujarat Giants',
        'UP-W': 'UP Warriorz',
        
        # BPL (Bangladesh Premier League)
        'CV': 'Comilla Victorians',
        'RR': 'Rangpur Riders',
        'FB': 'Fortune Barishal',
        'KT': 'Khulna Tigers',
        'DD': 'Dhaka Dominators',
        'DCa': 'Dhaka Capitals',  # BPL 2025-26 (was DC - conflicts with Dubai Capitals)
        'DuD': 'Durdanto Dhaka',
        'DurD': 'Durbar Rajshahi',
        'DurR': 'Duronto Rajshahi',
        'DR': 'Durbar Rajshahi',  # BPL 2025
        'SS': 'Sylhet Strikers',
        'CKi': 'Chittagong Kings',  # was CK - conflicts with Canterbury
        'CC': 'Chattogram Challengers',
        # BPL 2025-26 new teams
        'NE': 'Noakhali Express',
        'RW': 'Rajshahi Warriors',
        'BB': 'Barisal Bulls',
        'MGD': 'Minister Group Dhaka',
        'DG': 'Dhaka Gladiators',
        'SSS': 'Sylhet Super Stars',
        'SR': 'Sylhet Royals',
        'SyS': 'Sylhet Sunrisers',  # was SYS - conflicts with Sydney Sixers
        
        # T20 International Teams
        'IND': 'India', 'AUS': 'Australia', 'ENG': 'England', 'NZ': 'New Zealand',
        'NZL': 'New Zealand', 'SA': 'South Africa', 'PAK': 'Pakistan', 'WI': 'West Indies',
        'SL': 'Sri Lanka', 'BAN': 'Bangladesh', 'AFG': 'Afghanistan', 'IRE': 'Ireland',
        'SCO': 'Scotland', 'ZIM': 'Zimbabwe', 'UAE': 'United Arab Emirates', 'NED': 'Netherlands',
        'NAM': 'Namibia', 'NEP': 'Nepal', 'OMA': 'Oman', 'PNG': 'Papua New Guinea',
        'HK': 'Hong Kong', 'KEN': 'Kenya', 'UGA': 'Uganda', 'GER': 'Germany',
        'JER': 'Jersey', 'USA': 'United States of America', 'CAN': 'Canada',
    }

    # Team aliases for mapping new/renamed teams to historical equivalents
    TEAM_ALIASES = {
        # Rajshahi lineage: Duronto Rajshahi (2012-13) → Rajshahi Kings (2016-19) → Rajshahi Royals (2019-20) → Durbar Rajshahi (2024) → Rajshahi Warriors (2025)
        'Rajshahi Warriors': 'Durbar Rajshahi',  # 2025 successor of Durbar Rajshahi
        'Durbar Rajshahi': 'Rajshahi Royals',  # 2024 successor of Rajshahi Royals
        'Rajshahi Royals': 'Rajshahi Kings',  # 2019-20 successor of Rajshahi Kings
        'Rajshahi Kings': 'Duronto Rajshahi',  # 2016 successor of Duronto Rajshahi
        # Dhaka lineage
        'Dhaka Capitals': 'Durdanto Dhaka',  # 2025 Dhaka successor
        # Map new teams to lowest performing historical team
        'Noakhali Express': 'Durdanto Dhaka',  # New team -> worst performer (8.3% win rate)
    }
    
    # =====================================================================
    # CONFIGURATION - Toggle between historical data and season overrides
    # =====================================================================
    USE_SEASON_OVERRIDES = True  # Set to False to use historical feature store data only
    
    # =====================================================================
    # VENUE SITUATION STATS - Bat/Bowl first win rates from current venue
    # Auto-populated by crex_live_predictor from match info page
    # =====================================================================
    VENUE_SITUATION_STATS = {
        # Auto-populated: {'bat_first_wr': 0.45, 'bowl_first_wr': 0.53, 'matches': 66}
    }
    
    # =====================================================================
    # SEASON OVERRIDES - Current season stats (takes precedence over historical)
    # This is auto-populated by crex_live_predictor from the match info page
    # Can also be manually updated. Format:
    # 'Team Name': {'win_rate': X, 'matches': N, 'avg_score': Y, ...}
    # =====================================================================
    SEASON_OVERRIDES = {
        # Auto-populated from CREX match info page during live prediction
        # Example entry (added automatically):
        # 'Rajshahi Warriors': {'win_rate': 0.60, 'matches': 10, 'avg_score': 148, ...}
    }
    # =====================================================================
    
    # Default stats for completely new teams (treat as lower performing)
    # New teams typically struggle in their first season due to lack of team cohesion,
    # unfamiliar conditions, and untested squad combinations
    DEFAULT_TEAM_STATS = {
        'win_rate': 0.40,  # New teams perform below average historically
        'matches': 0,
        'bat_first_wr': 0.40,
        'bowl_first_wr': 0.40,
    }
    
    # Teams that should use default average stats (none currently - all mapped)
    NEW_TEAMS = set()

    def _resolve_team_alias(self, team_name: str, max_depth: int = 5) -> Optional[str]:
        """Follow alias chain to find a team that exists in the feature store."""
        current = team_name
        chain = [team_name]
        
        for _ in range(max_depth):
            if current in self._team_stats:
                if len(chain) > 1:
                    logger.info(f"Resolved team chain: {' → '.join(chain)}")
                return current
            
            if current in self.TEAM_ALIASES:
                current = self.TEAM_ALIASES[current]
                chain.append(current)
            else:
                break
        
        # Final check
        if current in self._team_stats:
            logger.info(f"Resolved team chain: {' → '.join(chain)}")
            return current
        
        return None

    def get_team_stats(self, team_name: str) -> Optional[Dict[str, Any]]:
        if not self._loaded:
            self.load()
            
        if not team_name:
            return None
        
        # 0. Check abbreviation map first and resolve full name
        full_name = team_name
        if team_name.upper() in self.TEAM_ABBREVIATIONS:
            full_name = self.TEAM_ABBREVIATIONS[team_name.upper()]
        
        # 0.1 CHECK SEASON OVERRIDES FIRST (if enabled)
        if self.USE_SEASON_OVERRIDES and full_name in self.SEASON_OVERRIDES:
            season_stats = self.SEASON_OVERRIDES[full_name].copy()
            # Log what we're using
            bat_wr = season_stats.get('bat_first_wr', season_stats['win_rate'])
            bowl_wr = season_stats.get('bowl_first_wr', season_stats['win_rate'])
            logger.info(f"📊 Using SEASON stats for '{full_name}': {season_stats['matches']} matches, {season_stats['win_rate']*100:.0f}% win rate (bat_first={bat_wr:.0%}, bowl_first={bowl_wr:.0%})")
            return season_stats
        
        # 0.2 Check if this is a new team that should use default stats
        if full_name in self.NEW_TEAMS:
            logger.warning(f"⚠️ Using DEFAULT stats for new team '{full_name}' (no historical data)")
            return self.DEFAULT_TEAM_STATS.copy()
            
        # 0.3 Try to resolve through alias chain
        resolved = self._resolve_team_alias(full_name)
        if resolved:
            # Warn if using a proxy team (not same as original)
            if resolved != full_name:
                logger.warning(f"⚠️ Using PROXY stats: '{full_name}' → '{resolved}' (no direct data for this team)")
            if team_name != full_name:
                logger.info(f"Mapped team abbreviation '{team_name}' → '{full_name}' → '{resolved}'")
            return self._team_stats[resolved]
            
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

        # Start with base stats (either from historical data or defaults)
        base_stats = None
        
        # 1. Exact match
        if venue_name in self._venue_stats:
            logger.info(f"Using venue stats for '{venue_name}'")
            base_stats = self._venue_stats[venue_name].copy()
            
        # 2. Case-insensitive match
        elif venue_name.lower() in self._venue_names_lower:
            real_name = self._venue_names_lower[venue_name.lower()]
            logger.info(f"Using venue stats for '{real_name}' (case-insensitive match)")
            base_stats = self._venue_stats[real_name].copy()
            
        # 3. Fuzzy match (increased cutoff to 0.8 for stricter matching)
        else:
            matches = difflib.get_close_matches(venue_name, self._venue_stats.keys(), n=1, cutoff=0.8)
            if matches:
                match = matches[0]
                logger.info(f"Fuzzy matched venue '{venue_name}' to '{match}'")
                base_stats = self._venue_stats[match].copy()
        
        # 4. If no historical data found, create default stats
        if base_stats is None:
            logger.warning(f"No venue stats found for '{venue_name}', using defaults")
            base_stats = {
                'venue_avg_score': 160.0,
                'venue_avg_wickets': 6.0,
                'venue_bat_first_win_rate': 0.5,
            }
        
        # 5. Override with live VENUE_SITUATION_STATS from CREX if available
        # This ensures we use the actual venue avg from the current match info page
        # for consistency with what's displayed on CREX
        if self.VENUE_SITUATION_STATS:
            if 'avg_1st_inns' in self.VENUE_SITUATION_STATS:
                # Use avg_1st_inns as venue_avg_score (consistent with training which uses first innings avg)
                base_stats['venue_avg_score'] = float(self.VENUE_SITUATION_STATS['avg_1st_inns'])
                logger.info(f"Overrode venue_avg_score with CREX avg_1st_inns: {base_stats['venue_avg_score']}")
            if 'bat_first_wr' in self.VENUE_SITUATION_STATS:
                base_stats['venue_bat_first_win_rate'] = float(self.VENUE_SITUATION_STATS['bat_first_wr'])
        
        return base_stats

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
            
            # SA20
            'PC': 'Pretoria Capitals',
            'SEC': 'Sunrisers Eastern Cape',
            'DSG': "Durban's Super Giants",
            'JSK': 'Joburg Super Kings',
            'MICT': 'MI Cape Town',
            'PR': 'Paarl Royals',
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
