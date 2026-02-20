from typing import Any, Dict, List, Tuple, Optional
import pandas as pd
from datetime import datetime
import structlog

# Import resolver type for type hinting only to avoid circular imports if any
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from bbl_pipeline.processing.resolution import EntityResolver

logger = structlog.get_logger()

def extract_match_metadata(match_data: Dict[str, Any], match_id: str, league_slug: Optional[str] = None) -> Dict[str, Any]:
    """Extract match-level metadata."""
    info = match_data.get('info', {})
    
    # Dates can be a list, take the first one
    dates = info.get('dates', [])
    date_str = dates[0] if dates else None
    
    # Teams
    teams = info.get('teams', [])
    team_a = teams[0] if len(teams) > 0 else None
    team_b = teams[1] if len(teams) > 1 else None
    
    # Winner
    outcome = info.get('outcome', {})
    winner = outcome.get('winner', None)
    
    # Toss info
    toss = info.get('toss', {})
    toss_winner = toss.get('winner', None)
    toss_decision = toss.get('decision', None)  # 'bat' or 'field'
    
    # Extract league from event.name if not provided
    event = info.get('event', {})
    event_name = event.get('name', '') if isinstance(event, dict) else ''
    detected_league = league_slug or _infer_league_from_event(event_name)
    
    return {
        'match_id': match_id,
        'season': str(info.get('season', 'unknown')),
        'date': pd.to_datetime(date_str) if date_str else None,
        'venue': info.get('venue', 'unknown'),
        'team_a': team_a,
        'team_b': team_b,
        'winner': winner,
        'gender': info.get('gender', 'unknown'),
        'match_type': info.get('match_type', 'unknown'),
        'toss_winner': toss_winner,
        'toss_decision': toss_decision,
        'league': detected_league,
        'event_name': event_name,
    }


def _infer_league_from_event(event_name: str) -> str:
    """Infer league slug from event name."""
    event_lower = event_name.lower()
    league_mapping = {
        'big bash league': 'bbl',
        'indian premier league': 'ipl',
        'pakistan super league': 'psl',
        'caribbean premier league': 'cpl',
        'sa20': 'sat',
        'bangladesh premier league': 'bpl',
        'lanka premier league': 'lpl',
        'international league t20': 'ilt',
        'major league cricket': 'mlc',
        'super smash': 'ssm',
        't20 blast': 'ntb',
        "women's big bash league": 'wbbl',
        "women's premier league": 'wpl',
        "women's caribbean premier league": 'wcpl',
    }
    for key, slug in league_mapping.items():
        if key in event_lower:
            return slug
    return 'unknown'

def resolve_entity(name: Optional[str], entity_type: str, resolver: Optional['EntityResolver']) -> str:
    """Helper to resolve entity name to ID."""
    if not name:
        return "unknown"
    
    if not resolver:
        return name
        
    if entity_type == 'player':
        pid, score = resolver.resolve_player(name)
        return pid if pid else name # Fallback to name if not found
    elif entity_type == 'team':
        tid, score = resolver.resolve_team(name)
        return tid if tid else name
    elif entity_type == 'venue':
        vid, score = resolver.resolve_venue(name)
        return vid if vid else name
        
    return name

def flatten_delivery(
    delivery: Dict[str, Any], 
    meta: Dict[str, Any], 
    inning_meta: Dict[str, Any], 
    over_num: int,
    ball_num: int,
    resolver: Optional['EntityResolver'] = None
) -> Dict[str, Any]:
    """Flatten a single delivery into a dictionary row."""
    
    runs = delivery.get('runs', {})
    extras = delivery.get('extras', {})
    wicket = delivery.get('wickets', [{}])[0] if delivery.get('wickets') else {}
    
    # Resolve entities
    venue_id = resolve_entity(meta['venue'], 'venue', resolver)
    batting_team_id = resolve_entity(inning_meta['team'], 'team', resolver)
    
    bowling_team_name = meta['team_b'] if inning_meta['team'] == meta['team_a'] else meta['team_a']
    bowling_team_id = resolve_entity(bowling_team_name, 'team', resolver)
    
    # Add raw team names for easier debugging/mapping later
    batting_team_name = inning_meta['team']
    
    batter_id = resolve_entity(delivery.get('batter'), 'player', resolver)
    bowler_id = resolve_entity(delivery.get('bowler'), 'player', resolver)
    non_striker_id = resolve_entity(delivery.get('non_striker'), 'player', resolver)
    player_out_id = resolve_entity(wicket.get('player_out'), 'player', resolver) if wicket.get('player_out') else None
    
    row = {
        # Match Meta
        'match_id': meta['match_id'],
        'season': meta['season'],
        'date': meta['date'],
        'venue_id': venue_id,
        'batting_team_id': batting_team_id,
        'bowling_team_id': bowling_team_id,
        'batting_team': batting_team_name,
        'winner': meta['winner'],
        'toss_winner': meta.get('toss_winner'),
        'toss_decision': meta.get('toss_decision'),
        'league': meta.get('league', 'unknown'),
        'gender': meta.get('gender', 'unknown'),
        
        # Inning Meta
        'innings': inning_meta['innings_num'],
        'is_super_over': inning_meta['is_super_over'],
        
        # Ball Meta
        'over': over_num,
        'ball': ball_num,
        
        # Players
        'batter_id': batter_id,
        'bowler_id': bowler_id,
        'non_striker_id': non_striker_id,
        
        # Runs
        'runs_batter': runs.get('batter', 0),
        'runs_extras': runs.get('extras', 0),
        'runs_total': runs.get('total', 0),
        
        # Wicket
        'wicket_type': wicket.get('kind'),
        'player_out_id': player_out_id,
    }
    return row

def should_skip_match(match_data: Dict[str, Any], match_id: str) -> Tuple[bool, str]:
    """
    Check if a match should be skipped for training purposes.
    
    Skip matches where:
    - No clear winner (tie decided by super over, no result, abandoned, etc.)
    - The outcome is determined by something other than normal play
    
    Returns:
        Tuple of (should_skip, reason)
    """
    info = match_data.get('info', {})
    outcome = info.get('outcome', {})
    
    # Skip if no outcome at all
    if not outcome:
        return True, "no_outcome"
    
    # Skip 'no result' matches (rain, abandoned, etc.)
    if outcome.get('result') == 'no result':
        return True, "no_result"
    
    # Skip tie matches (decided by super over or eliminator)
    # These have outcome.result='tie' with an 'eliminator' key
    if outcome.get('result') == 'tie':
        return True, "tie_super_over"
    
    # Skip if no winner specified (shouldn't happen for normal completed matches)
    if not outcome.get('winner') and outcome.get('result') not in ['runs', 'wickets']:
        # Some matches have 'by' key without 'winner' for DLS etc.
        if 'by' not in outcome:
            return True, "no_winner"
    
    return False, ""


def process_match(
    match_data: Dict[str, Any], 
    match_id: str,
    resolver: Optional['EntityResolver'] = None,
    league_slug: Optional[str] = None
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Process a single match into a list of flat records.
    
    Args:
        match_data: The raw match JSON data.
        match_id: Unique match identifier (filename without extension).
        resolver: Optional entity resolver for name normalization.
        league_slug: Optional league identifier (e.g., 'bbl', 'ipl').
    
    Returns:
        Tuple of (main_records, super_over_records)
        Returns empty lists if match should be skipped (tie/no result/etc.)
    """
    # Check if match should be skipped
    skip, reason = should_skip_match(match_data, match_id)
    if skip:
        logger.info("Skipping match", match_id=match_id, reason=reason)
        return [], []
    
    meta = extract_match_metadata(match_data, match_id, league_slug)
    
    main_records = []
    super_over_records = []
    
    innings_list = match_data.get('innings', [])
    
    for i, inning in enumerate(innings_list):
        is_super_over = False
        if 'super_over' in inning and inning['super_over']:
            is_super_over = True
        elif i >= 2 and meta['match_type'] in ['T20', 'IT20', 'BBL']:
             is_super_over = True
             
        inning_meta = {
            'team': inning.get('team'),
            'innings_num': i + 1,
            'is_super_over': is_super_over
        }
        
        for over_data in inning.get('overs', []):
            over_num = over_data.get('over')
            
            for j, delivery in enumerate(over_data.get('deliveries', [])):
                ball_num = j + 1
                
                row = flatten_delivery(delivery, meta, inning_meta, over_num, ball_num, resolver)
                
                if is_super_over:
                    super_over_records.append(row)
                else:
                    main_records.append(row)
                    
    return main_records, super_over_records
