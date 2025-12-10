import logging

logger = logging.getLogger(__name__)

def parse_runs_and_balls(value):
    """
    Parses the runs and balls faced from the given string.
    
    Args:
        value (str): The string containing runs and balls information.
    
    Returns:
        tuple: (runs, balls_faced, on_strike)
    """
    if not value:
        return 0, 0, False
    on_strike = value.endswith('*')
    value = value.replace('*', '')
    parts = value.split('.')
    runs = int(parts[0]) if len(parts) > 0 and parts[0].isdigit() else 0
    balls_faced = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    return runs, balls_faced, on_strike

def parse_batsman_stats(value):
    """
    Parses the batsman's stats (fours, sixes, and additional unknown stats).
    
    Args:
        value (str): The string containing batsman's stats.
    
    Returns:
        tuple: (fours, sixes, additional_stats)
    """
    parts = value.split('.') if value else []
    fours = int(parts[0]) if len(parts) > 0 and parts[0].isdigit() else 0
    sixes = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    additional_stats = {
        'stat_3': parts[2] if len(parts) > 2 else 'Unknown',
        'stat_4': parts[3] if len(parts) > 3 else 'Unknown'
    }
    return fours, sixes, additional_stats

def parse_bowler_string(bowler_str):
    """
    Parses a bowler's performance string and returns a dictionary of stats.

    Args:
        bowler_str (str): The bowler performance string (e.g., "T8.35.24.0.2")

    Returns:
        tuple: (bowler_code, stats_dict) or (None, None) if parsing fails
    """
    try:
        parts = bowler_str.split('.')
        if len(parts) < 5:
            logger.warning(f"Invalid bowler string format: {bowler_str}")
            return None, None

        bowler_code = parts[0]
        runs_conceded = int(parts[1])
        balls_bowled = int(parts[2])
        maidens = int(parts[3])
        wickets = int(parts[4])

        # Calculate overs bowled
        overs = balls_bowled // 6
        balls = balls_bowled % 6
        overs_decimal = overs + balls / 10

        bowler_stats = {
            "overs": overs_decimal,
            "runs": runs_conceded,
            "maidens": maidens,
            "wickets": wickets
        }

        return bowler_code, bowler_stats
    except Exception as e:
        logger.error(f"Error parsing bowler string '{bowler_str}': {e}")
        return None, None

def parse_batsman_string(batsman_str):
    """
    Parses a batsman's performance string and returns a dictionary of stats, including batting status.

    Args:
        batsman_str (str): The batsman performance string (e.g., "37X.44.39.7.0.66.86.2.PP.389/25.29-184.30/")

    Returns:
        tuple: (batsman_code, stats_dict) or (None, None) if parsing fails
    """
    try:
        # Split by '/' to separate main data from other details
        main_part = batsman_str.split('/')[0]
        parts = main_part.split('.')

        batsman_code = parts[0] if len(parts) >= 1 else None

        # Determine batting status based on the number of segments
        if len(parts) == 1:
            status = "yet_to_bat"
        elif len(parts) == 5:
            status = "currently_batting"
        elif len(parts) > 5:
            status = "dismissed"
        else:
            status = "unknown"

        # Parse common fields
        runs = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
        balls_faced = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
        fours = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 0
        sixes = int(parts[4]) if len(parts) > 4 and parts[4].isdigit() else 0
        dismissal_over = parts[5] if len(parts) > 5 else None
        dismissal_runs_score = parts[6] if len(parts) > 6 else None
        dismissal_code = parts[7] if len(parts) > 7 else None
        bowler_code = parts[8] if len(parts) > 8 else None
        player_caught = parts[9] if len(parts) > 9 else None

        batsman_stats = {
            "runs": runs,
            "balls_faced": balls_faced,
            "fours": fours,
            "sixes": sixes,
            "dismissal_over": dismissal_over,
            "dismissal_runs_score": dismissal_runs_score,
            "dismissal_code": dismissal_code,
            "bowler_code": bowler_code,
            "player_caught": player_caught,
            "status": status
        }

        return batsman_code, batsman_stats
    except Exception as e:
        logger.error(f"Error parsing batsman string '{batsman_str}': {e}")
        return None, None

def extract_match_stats_by_innings(response_json):
    """
    Extracts bowlers_stats, batsman_stats, innings team score, and team code from each innings in the JSON response.

    Args:
        response_json (list): The JSON response as a list of dictionaries, each representing an inning.

    Returns:
        dict: A dictionary with innings labels as keys and their respective team_code, team_score,
              bowlers_stats, and batsman_stats as values.
    """
    innings_stats = {"innings": {}}

    if not isinstance(response_json, list):
        logger.warning("response_json is not a list")
        return innings_stats

    for idx, match_data in enumerate(response_json):
        # Assign inning labels based on index with correct ordinal suffix
        inning_number = idx + 1
        if inning_number == 1:
            suffix = "st"
        elif inning_number == 2:
            suffix = "nd"
        elif inning_number == 3:
            suffix = "rd"
        else:
            suffix = "th"
        inning_label = f"{inning_number}{suffix}_inning"

        # Extract team_code and team_score from fields 'c' and 'd'
        team_code = match_data.get("c", "").strip()
        team_score = match_data.get("d", "").strip()

        # Extract bowlers_stats from the 'a' attribute
        bowlers_stats = {}
        a_attribute = match_data.get("a", [])
        for bowler_str in a_attribute:
            bowler_code, stats = parse_bowler_string(bowler_str)
            if bowler_code and stats:
                bowlers_stats[bowler_code] = stats

        # Extract batsman_stats from the 'b' attribute
        batsman_stats = {}
        b_attribute = match_data.get("b", [])
        for batsman_str in b_attribute:
            batsman_code, stats = parse_batsman_string(batsman_str)
            if batsman_code and stats:
                batsman_stats[batsman_code] = stats

        # Consolidate all extracted data for the current inning
        innings_stats["innings"][inning_label] = {
            "team_code": team_code,
            "team_score": team_score,
            "bowlers_stats": bowlers_stats,
            "batsman_stats": batsman_stats
        }

    return innings_stats
