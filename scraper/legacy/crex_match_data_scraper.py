import argparse
import asyncio
import functools
import os
import sys

import concurrent.futures
import threading
import requests
# Use batched version for better performance
import cricket_data_service
from playwright.sync_api import sync_playwright
import json
import logging
from shared import scraping_tasks 
from crex_info_url import scrape_match_info  # Import the modularized info scraper
import time
from urllib.parse import urlparse, parse_qs

# Initialize loggers
api_logger = logging.getLogger('api_logger')
api_logger.setLevel(logging.DEBUG)
scraper_logger = logging.getLogger('scraper_logger')
scraper_logger.setLevel(logging.WARN)

# File handlers
api_file_handler = logging.FileHandler('api.log',encoding='utf-8')
scraper_file_handler = logging.FileHandler('crex_scraper.log',encoding='utf-8')

# Console handler
console_handler = logging.StreamHandler()
api_file_handler.setLevel(logging.DEBUG)
scraper_file_handler.setLevel(logging.WARN)
console_handler.setLevel(logging.WARN)

# Define log formats
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
api_file_handler.setFormatter(formatter)
scraper_file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# Add handlers to the loggers
api_logger.addHandler(api_file_handler)
api_logger.addHandler(console_handler)  # Console handler for debugging in real-time
scraper_logger.addHandler(scraper_file_handler)
scraper_logger.addHandler(console_handler)  # Console handler for real-time feedback

# Initialize a ThreadPoolExecutor with a suitable number of workers
executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)  # Adjust as needed


def get_team_name(team_code, team_data):
    """
    Replaces the team code with the actual team name using the team_data mapping.

    Args:
        team_code (str): The team code (e.g., "OT").
        team_data (dict): The mapping of team codes to team names.

    Returns:
        str: The corresponding team name or the original code if not found.
    """
    team_key = f"t_{team_code}_name"
    team_name = team_data.get(team_key)
    if team_name:
        return team_name
    else:
        # Attempt to find by matching team name (case-insensitive)
        for key, value in team_data.items():
            if (
                key.endswith("_name")
                and value.strip().lower() == team_code.strip().lower()
            ):
                return value.strip()
        # If not found, return the original code with a warning
        logging.warning(
            f"Team code '{team_code}' not found in team_data. Using code as team name."
        )
        return team_code

def get_player_name(player_code, player_data):
    """
    Replaces the player code with the actual player name using the player_data mapping.

    Args:
        player_code (str): The player code (e.g., "FMM").
        player_data (dict): The mapping of player codes to player names.

    Returns:
        str: The corresponding player name or the original code if not found.
    """
    player_key = f"p_{player_code}_name"
    player_name = player_data.get(player_key)
    if player_name:
        return player_name
    else:
        # Attempt to find by matching player name (case-insensitive)
        for key, value in player_data.items():
            if (
                key.endswith("_name")
                and value.strip().lower() == player_code.strip().lower()
            ):
                return value.strip()
        # If not found, return the original code with a warning
        logging.warning(
            f"Player code '{player_code}' not found in player_data. Using code as player name."
        )
        return player_code


def categorize_local_storage_data(page):
    """
    Extracts and categorizes local storage data into player, team, and series maps.
    
    Args:
        page: The Playwright page object.
    
    Returns:
        A dictionary containing player_data, team_data, and series_data.
    """
    try:
        page.wait_for_load_state(state='domcontentloaded')
        local_storage = page.evaluate("() => Object.fromEntries(Object.entries(localStorage).map(([k, v]) => [k, v]))")
        scraper_logger.info("Successfully extracted local storage data.")

        # Categorize data
        player_data = {k: v for k, v in local_storage.items() if k.startswith('p_')}
        team_data = {k: v for k, v in local_storage.items() if k.startswith('t_')}
        series_data = {k: v for k, v in local_storage.items() if k.startswith('s_')}

        # [INVESTIGATION] Task 1.2: Log localStorage counts
        api_logger.info(f"[LOCALSTORAGE] Total entries: {len(local_storage)}")
        api_logger.info(f"[LOCALSTORAGE] Player entries (p_*): {len(player_data)}")
        api_logger.info(f"[LOCALSTORAGE] Team entries (t_*): {len(team_data)}")
        api_logger.info(f"[LOCALSTORAGE] Series entries (s_*): {len(series_data)}")
        
        # [INVESTIGATION] Task 1.2: Save localStorage dump for debugging
        try:
            import time
            timestamp = int(time.time())
            dump_file = f"localStorage_dump_{timestamp}.json"
            with open(dump_file, 'w', encoding='utf-8') as f:
                json.dump(local_storage, f, indent=2, ensure_ascii=False)
            api_logger.info(f"[LOCALSTORAGE] Saved dump to {dump_file}")
        except Exception as dump_error:
            api_logger.warning(f"[LOCALSTORAGE] Failed to save dump: {dump_error}")

        scraper_logger.info(f"Player Data Map: {player_data}")
        scraper_logger.info(f"Team Data Map: {team_data}")
        scraper_logger.debug(f"Series Data Map: {series_data}")

        return {'player_data': player_data, 'team_data': team_data, 'series_data': series_data}
    except Exception as e:
        scraper_logger.error(f"Error extracting or mapping local storage: {e}", exc_info=True)
        return None

def parse_runs_and_balls(value):
    """
    Parses the runs and balls faced from the given string.
    
    Args:
        value (str): The string containing runs and balls information.
    
    Returns:
        A tuple of (runs, balls_faced, on_strike).
    """
    if not value:
        return 0, 0, False
    on_strike = value.endswith('*')
    value = value.replace('*', '')
    parts = value.split('.')
    runs = int(parts[0]) if len(parts) > 0 and parts[0].isdigit() else 0
    balls_faced = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    return runs, balls_faced, on_strike

def extract_key_from_url(url):
    """
    Extracts the 'key' parameter from the given URL.
    
    Args:
        url (str): The URL containing the 'key' parameter.
    
    Returns:
        str: The value of the 'key' parameter, or None if not found.
    """
    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.query)
    key = query_params.get('key', [None])[0]
    return key

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

        # Log the extracted team information
        api_logger.debug(f"Inning {inning_number}: Team Code = {team_code}, Team Score = {team_score}")

        # Extract bowlers_stats from the 'a' attribute
        bowlers_stats = {}
        a_attribute = match_data.get("a", [])
        for bowler_str in a_attribute:
            bowler_code, stats = parse_bowler_string(bowler_str)
            if bowler_code and stats:
                bowlers_stats[bowler_code] = stats
                api_logger.debug(f"Inning {inning_number}: Bowler {bowler_code} stats = {stats}")

        # Extract batsman_stats from the 'b' attribute
        batsman_stats = {}
        b_attribute = match_data.get("b", [])
        for batsman_str in b_attribute:
            batsman_code, stats = parse_batsman_string(batsman_str)
            if batsman_code and stats:
                batsman_stats[batsman_code] = stats
                api_logger.debug(f"Inning {inning_number}: Batsman {batsman_code} stats = {stats}")

        # Consolidate all extracted data for the current inning
        innings_stats["innings"][inning_label] = {
            "team_code": team_code,
            "team_score": team_score,
            "bowlers_stats": bowlers_stats,
            "batsman_stats": batsman_stats
        }

    return innings_stats

def parse_bowler_string(bowler_str):
    """
    Parses a bowler's performance string and returns a dictionary of stats.

    Args:
        bowler_str (str): The bowler performance string (e.g., "T8.35.24.0.2")

    Returns:
        tuple: (bowler_code, stats_dict) or (None, None) if parsing fails
    """
    # [INVESTIGATION] Task 1.3: Log incoming bowler string
    api_logger.debug(f"[PARSE BOWLER] Parsing string: {bowler_str}")
    
    try:
        parts = bowler_str.split('.')
        if len(parts) < 5:
            # [INVESTIGATION] Task 1.3: Log parsing failure
            api_logger.warning(f"[PARSE BOWLER FAIL] Invalid format (expected 5+ parts, got {len(parts)}): {bowler_str}")
            print(f"Invalid bowler string format: {bowler_str}")
            return None, None

        bowler_code = parts[0]
        runs_conceded = int(parts[1])
        balls_bowled = int(parts[2])
        maidens = int(parts[3])
        wickets = int(parts[4])

        # Calculate overs bowled
        overs = balls_bowled // 6
        balls = balls_bowled % 6
        overs_decimal = overs + balls / 10  # Represent overs as decimal (e.g., 5 overs 5 balls → 5.5)

        bowler_stats = {
            "overs": overs_decimal,
            "runs": runs_conceded,
            "maidens": maidens,
            "wickets": wickets
        }

        # [INVESTIGATION] Task 1.3: Log successful parse
        api_logger.debug(f"[PARSE BOWLER SUCCESS] Code: {bowler_code}, Stats: {bowler_stats}")
        return bowler_code, bowler_stats
    except Exception as e:
        # [INVESTIGATION] Task 1.3: Log exception with full details
        api_logger.error(f"[PARSE BOWLER ERROR] Exception parsing '{bowler_str}': {e}", exc_info=True)
        print(f"Error parsing bowler string '{bowler_str}': {e}")
        return None, None

def parse_batsman_string(batsman_str):
    """
    Parses a batsman's performance string and returns a dictionary of stats, including batting status.

    Args:
        batsman_str (str): The batsman performance string (e.g., "37X.44.39.7.0.66.86.2.PP.389/25.29-184.30/")

    Returns:
        tuple: (batsman_code, stats_dict) or (None, None) if parsing fails
    """
    # [INVESTIGATION] Task 1.3: Log incoming batsman string
    api_logger.debug(f"[PARSE BATSMAN] Parsing string: {batsman_str}")
    
    try:
        # Split by '/' to separate main data from other details
        main_part = batsman_str.split('/')[0]  # e.g., "37X.44.39.7.0.66.86.2.PP.389"
        parts = main_part.split('.')

        batsman_code = parts[0] if len(parts) >= 1 else None

        # Determine batting status based on the number of segments
        if len(parts) == 1:
            # Only batsman code present
            status = "yet_to_bat"
        elif len(parts) == 5:
            # Batsman code followed by 4 statistics: Runs, Balls Faced, Fours, Sixes
            status = "currently_batting"
        elif len(parts) > 5:
            # Batsman code followed by more than 4 statistics: Dismissed
            status = "dismissed"
        else:
            # Undefined status for unexpected formats
            status = "unknown"
            # [INVESTIGATION] Task 1.3: Log unknown status
            api_logger.warning(f"[PARSE BATSMAN] Unknown status detected for '{batsman_str}' ({len(parts)} parts)")

        # Parse common fields
        runs = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
        balls_faced = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
        fours = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 0
        sixes = int(parts[4]) if len(parts) > 4 and parts[4].isdigit() else 0
        dismissal_over = parts[5] if len(parts) > 5 else None
        dismissal_runs_score = parts[6] if len(parts) > 6 else None
        dismissal_code = parts[7] if len(parts) > 7 else None
        bowler_code = parts[8] if len(parts) > 8 else None
        player_caught = parts[9] if len(parts) > 9 else None  # Optional field

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
            "status": status  # Added status field
        }

        # [INVESTIGATION] Task 1.3: Log successful parse with status
        api_logger.debug(f"[PARSE BATSMAN SUCCESS] Code: {batsman_code}, Status: {status}, Runs: {runs}/{balls_faced}")
        return batsman_code, batsman_stats
    except Exception as e:
        # [INVESTIGATION] Task 1.3: Log exception with full details
        api_logger.error(f"[PARSE BATSMAN ERROR] Exception parsing '{batsman_str}': {e}", exc_info=True)
        print(f"Error parsing batsman string '{batsman_str}': {e}")
        return None, None


def trigger_sC4_call_async(sc4_url, headers, data_store):
    """
    Asynchronously executes the synchronous trigger_sC4_call function
    using a ThreadPoolExecutor and attaches a callback to handle the result.
    
    Args:
        sc4_url (str): The full URL for the sC4 API call.
        headers (dict): The headers to include in the request.
        data_store (dict): The shared data storage for scraped data.
    
    Returns:
        None
    """
    # [INVESTIGATION] Task 2.2: Log executor task submission
    api_logger.info(f"[EXECUTOR] Submitting sC4 task for URL: {sc4_url}")
    future = executor.submit(trigger_sC4_call, sc4_url, headers)
    api_logger.info(f"[EXECUTOR] Task submitted, future ID: {id(future)}")
    future.add_done_callback(functools.partial(handle_sC4_result, data_store=data_store))
        
def trigger_sC4_call(sc4_url, headers):
    """
    Makes a GET request to sC4.php with the provided key and headers,
    extracts bowler statistics by innings using extract_bowlers_stats_by_innings,
    logs the stats, and returns them for further processing.

    Args:
        sc4_url (str): The full URL for the sC4 API call.
        headers (dict): The headers to include in the request.

    Returns:
        dict: Extracted bowlers_stats organized by innings if successful, else None.
    """
    try:
        response = requests.get(sc4_url, headers=headers, timeout=10)
        if response.status_code == 200:
            try:
                sc4_data = response.json()
                
                # [INVESTIGATION] Task 1.1: Log full sC4 response for data completeness validation
                api_logger.info(f"[SC4_RESPONSE] Full response received from {sc4_url}")
                api_logger.info(f"[SC4_RESPONSE] Response size: {len(json.dumps(sc4_data))} bytes")
                api_logger.debug(f"[SC4_RESPONSE] Full JSON: {json.dumps(sc4_data, indent=2)}")
                
                # [INVESTIGATION] Task 1.1: Validate innings count
                innings_count = len(sc4_data) if isinstance(sc4_data, list) else 0
                api_logger.info(f"[SC4_RESPONSE] Number of innings in response: {innings_count}")
                
                # [INVESTIGATION] Task 1.1: Log array sizes for batsmen and bowlers per innings
                for idx, inning_data in enumerate(sc4_data) if isinstance(sc4_data, list) else []:
                    bowlers_array = inning_data.get('a', [])
                    batsmen_array = inning_data.get('b', [])
                    team_code = inning_data.get('c', 'Unknown')
                    api_logger.info(f"[SC4_RESPONSE] Innings {idx+1} (Team: {team_code}): {len(bowlers_array)} bowlers, {len(batsmen_array)} batsmen")
                    api_logger.debug(f"[SC4_RESPONSE] Innings {idx+1} bowlers array: {bowlers_array}")
                    api_logger.debug(f"[SC4_RESPONSE] Innings {idx+1} batsmen array: {batsmen_array}")

                # Extract bowlers_stats by innings using the provided function
                bowlers_stats_by_innings = extract_match_stats_by_innings(sc4_data)

                # Log the extracted bowlers_stats
                api_logger.info(
                    f"Extracted Bowlers Stats by Innings:{bowlers_stats_by_innings}"
                )

                return bowlers_stats_by_innings
            except json.JSONDecodeError:
                api_logger.error("Failed to decode JSON from sC4 response.")
                return None
            except Exception as e:
                api_logger.error(f"Unexpected error while processing sC4 response: {e}")
                return None
        else:
            api_logger.error(
                f"Failed to fetch sC4 data. Status Code: {response.status_code}"
            )
            return None
    except requests.RequestException as e:
        api_logger.error(f"Exception during sC4 API call: {e}")
        return None
        
def parse_batsman_stats(value):
    """
    Parses the batsman's stats (fours, sixes, and additional unknown stats).
    
    Args:
        value (str): The string containing batsman's stats.
    
    Returns:
        A tuple of (fours, sixes, additional_stats).
    """
    parts = value.split('.') if value else []
    fours = int(parts[0]) if len(parts) > 0 and parts[0].isdigit() else 0
    sixes = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    additional_stats = {
        'stat_3': parts[2] if len(parts) > 2 else 'Unknown',
        'stat_4': parts[3] if len(parts) > 3 else 'Unknown'
    }
    return fours, sixes, additional_stats

def handle_sC4_result(future, data_store):
    """
    Callback function to handle the result of trigger_sC4_call.
    
    Args:
        future (concurrent.futures.Future): The future object representing the async call.
        data_store (dict): The shared data storage for scraped data.
    
    Returns:
        None
    """
    # [INVESTIGATION] Task 2.1: Track callback execution
    api_logger.info(f"[CALLBACK START] Processing sC4 result callback")
    
    try:
        with data_store['lock']:
         match_stats_by_innings = future.result()
         if match_stats_by_innings:
            # [FIX] Ensure localStorage is available before decoding
            if not data_store.get('local_storage_data'):
                api_logger.error(f"[CALLBACK ERROR] localStorage not available in data_store, cannot decode player names")
                api_logger.warning(f"[CALLBACK] Proceeding without name decoding - player codes will be used as-is")
                # Store raw data without decoding
                data_store['sC4_stats'] = match_stats_by_innings
                return
            
            team_data = data_store.get('local_storage_data', {}).get('team_data', {})
            player_data = data_store.get('local_storage_data', {}).get('player_data', {})
            
            # [FIX] Verify localStorage has player data
            if not player_data:
                api_logger.warning(f"[CALLBACK] localStorage exists but player_data is empty")
            else:
                api_logger.info(f"[CALLBACK] localStorage available with {len(player_data)} player codes")
            
            for inning_label, inning_stats in match_stats_by_innings.get('innings', {}).items():
                api_logger.debug(f"Processing {inning_label}: {inning_stats}")
                
                # Replace team_code
                original_team_code = inning_stats.get('team_code')
                if original_team_code:
                    # [INVESTIGATION] Task 1.2: Check if team code exists in localStorage
                    team_key = f"t_{original_team_code}_name"
                    if team_key not in team_data:
                        api_logger.warning(f"[MISSING CODE] Team code '{original_team_code}' not found in localStorage")
                    
                    team_name = get_team_name(original_team_code, team_data)
                    inning_stats['team_code'] = team_name
                    api_logger.info(f"Replaced team_code '{original_team_code}' with '{team_name}' in {inning_label}")
                
                # Replace bowler_codes in bowlers_stats safely
                bowlers_stats = inning_stats.get('bowlers_stats', {})
                api_logger.debug(f"Original bowlers_stats: {bowlers_stats}")
                for bowler_code in list(bowlers_stats.keys()):
                    # [INVESTIGATION] Task 1.2: Check if bowler code exists in localStorage
                    player_key = f"p_{bowler_code}_name"
                    if player_key not in player_data:
                        api_logger.warning(f"[MISSING CODE] Bowler code '{bowler_code}' not found in localStorage")
                    
                    bowler_stats = bowlers_stats[bowler_code]
                    player_name = get_player_name(bowler_code, player_data)
                    bowlers_stats[player_name] = bowler_stats
                    del bowlers_stats[bowler_code]
                    api_logger.info(f"Replaced bowler_code '{bowler_code}' with '{player_name}' in {inning_label}")
                api_logger.debug(f"Updated bowlers_stats: {bowlers_stats}")
                
                # Replace batsman_codes in batsman_stats safely
                batsman_stats = inning_stats.get('batsman_stats', {})
                api_logger.debug(f"Original batsman_stats: {batsman_stats}")
                for batsman_code in list(batsman_stats.keys()):
                    # [INVESTIGATION] Task 1.2: Check if batsman code exists in localStorage
                    player_key = f"p_{batsman_code}_name"
                    if player_key not in player_data:
                        api_logger.warning(f"[MISSING CODE] Batsman code '{batsman_code}' not found in localStorage")
                    
                    batsman = batsman_stats[batsman_code]
                    player_name = get_player_name(batsman_code, player_data)
                    batsman_stats[player_name] = batsman
                    del batsman_stats[batsman_code]
                    api_logger.info(f"Replaced batsman_code '{batsman_code}' with '{player_name}' in {inning_label}")
                api_logger.debug(f"Updated batsman_stats: {batsman_stats}")
                    
            data_store['sC4_stats'] = match_stats_by_innings
            
            # [INVESTIGATION] Task 2.1: Log callback completion
            innings_processed = len(match_stats_by_innings.get('innings', {}))
            api_logger.info(f"[CALLBACK END] Successfully processed {innings_processed} innings")
            api_logger.info("sC4 stats successfully retrieved and stored.")
            
            # Retrieve the bearer token
            token = cricket_data_service.get_bearer_token()
            if not token:
                api_logger.error("Failed to obtain bearer token. Cannot send sC4 stats to backend.")
                return    
            
            # Define the backend endpoint URL for sC4 stats
            # It's good practice to define this in environment variables for flexibility
            sc4_endpoint_url = os.getenv('API_ENDPOINT_SC4', 'http://127.0.0.1:8099/cricket-data/sC4-stats/save')
            #sc4_endpoint_url = os.getenv('API_ENDPOINT_SC4', 'http://spring-security-jwt-app:8099/cricket-data/sC4-stats/save')

            # Prepare the payload
            sc4_payload = {
                "match_stats_by_innings": match_stats_by_innings,
                "url": data_store.get('url', 'Unknown URL')  # Include the URL for reference
            }
            
            # Send the data to the backend
            success = cricket_data_service.send_data_to_api_endpoint(
                data=sc4_payload,
                bearer_token=token,
                url=data_store.get('url', 'Unknown URL'),  # Optional, depending on your backend requirements
                api_endpoint=sc4_endpoint_url
            )
            
            if success:
                api_logger.info("sC4 stats successfully sent to the backend.")
            else:
                api_logger.error("Failed to send sC4 stats to the backend.")
            
    except Exception as e:
        # [INVESTIGATION] Task 2.1: Log full exception with stack trace
        api_logger.error(f"[CALLBACK ERROR] Error handling sC4 call result: {e}", exc_info=True)

        
def handle_api_responses(response, data_store):
    """
    Intercepts API responses to extract current ball info, favorite team, and odds.
    
    Args:
        response: The Playwright response object.
        data_store (dict): The shared data storage for scraped data.
    """
    if "sV3.php" in response.url:
        try:
            api_data = response.json()
            api_logger.debug(f"API data: {api_data}")  # Log the raw API data

            with data_store['lock']:
                # Extract 'B' (current ball info)
                current_ball_info = api_data.get('B', 'No current ball info available')
                data_store['current_ball_info'] = current_ball_info
                api_logger.debug(f"Current Ball Info: {current_ball_info}")

                # Extract 'F' (favorite team)
                favorite_team_raw = api_data.get('F')
                if favorite_team_raw:
                    favorite_team = favorite_team_raw.replace('^', "")
                    data_store['favorite_team'] = favorite_team
                    api_logger.debug(f"Extracted favorite team: {favorite_team}")
                else:
                    favorite_team = 'Unknown Team'
                    data_store['favorite_team'] = favorite_team
                    api_logger.warning("Favorite team 'F' field is missing or empty in API response.")

                # Extract 'R' (odds of the favorite team)
                favorite_team_odds_raw = api_data.get('R')
                if favorite_team_odds_raw:
                    favorite_team_odds = favorite_team_odds_raw
                    data_store['favorite_team_odds'] = favorite_team_odds
                    api_logger.debug(f"Extracted favorite team odds: {favorite_team_odds}")
                else:
                    favorite_team_odds = '0+0'
                    data_store['favorite_team_odds'] = favorite_team_odds
                    api_logger.warning("Favorite team odds 'R' field is missing or empty in API response.")

                # Extract session overs and odds
                session_overs_raw = api_data.get('D')
                session_odds_raw = api_data.get('Z')

                api_logger.debug(f"Type of 'D': {type(session_overs_raw)}, Value: {session_overs_raw}")
                api_logger.debug(f"Type of 'Z': {type(session_odds_raw)}, Value: {session_odds_raw}")

                session_overs = str(session_overs_raw) if session_overs_raw is not None else ''
                session_odds = str(session_odds_raw) if session_odds_raw is not None else ''

                session_over_list = session_overs.split(',') if session_overs else []
                session_odds_list = session_odds.split(',') if session_odds else []

                session_data = []

                for over, odds in zip(session_over_list, session_odds_list):
                    odds_parts = odds.split('+')
                    back_odds = odds_parts[0] if len(odds_parts) > 0 else '0'
                    lay_difference = odds_parts[1] if len(odds_parts) > 1 else '0'

                    try:
                        lay_odds_value = int(back_odds) + int(lay_difference)
                        lay_odds = str(lay_odds_value)
                    except ValueError:
                        lay_odds = back_odds  # Default to back_odds if conversion fails

                    back_odds = '-' if back_odds == '0' else back_odds
                    lay_odds = '-' if lay_odds == '0' else lay_odds

                    session_data.append({
                        'sessionName': over,
                        'odds': [
                            {'value': back_odds},
                            {'value': lay_odds}
                        ]
                    })

                data_store['session_data'] = session_data
                api_logger.debug(f"Session Data: {session_data}")

                # Extract Players
                p_field = api_data.get('p', '')
                p_split = p_field.split('.') if p_field else []

                batsman1_id = p_split[0] if len(p_split) > 0 else None
                batsman2_id = p_split[1] if len(p_split) > 1 else None

                # Batsman 1
                q_value = api_data.get('q', '')               
                batsman1_runs, batsman1_balls_faced, batsman1_on_strike = parse_runs_and_balls(q_value)

                r_value = api_data.get('r', '')
                batsman1_fours, batsman1_sixes, batsman1_additional_stats = parse_batsman_stats(r_value) 

                batsman_1_stats = {
                    'name': batsman1_id,
                    'runs': batsman1_runs,
                    'balls_faced': batsman1_balls_faced,
                    'fours': batsman1_fours,
                    'sixes': batsman1_sixes,
                    'on_strike': batsman1_on_strike,
                    'additional_stats': batsman1_additional_stats
                }
                data_store['batsman_1_stats'] = batsman_1_stats
                api_logger.debug(f"Batsman 1 Stats: {batsman_1_stats}")

                # Batsman 2
                s_value = api_data.get('s', '')
                batsman2_runs, batsman2_balls_faced, batsman2_on_strike = parse_runs_and_balls(s_value)

                t_value = api_data.get('t', '')
                batsman2_fours, batsman2_sixes, batsman2_additional_stats = parse_batsman_stats(t_value)

                batsman_2_stats = {
                    'name': batsman2_id,
                    'runs': batsman2_runs,
                    'balls_faced': batsman2_balls_faced,
                    'fours': batsman2_fours,
                    'sixes': batsman2_sixes,
                    'on_strike': batsman2_on_strike,
                    'additional_stats': batsman2_additional_stats
                }
                data_store['batsman_2_stats'] = batsman_2_stats
                api_logger.debug(f"Batsman 2 Stats: {batsman_2_stats}")

                # Bowler
                bowler_id = api_data.get('b', '')

                c_field = api_data.get('c', '')
                bowler_stats_split = c_field.split('.') if c_field else []

                bowler_stats = {
                    'name': bowler_id,
                    'runs_conceded': bowler_stats_split[0] if len(bowler_stats_split) > 0 and bowler_stats_split[0].isdigit() else 'Unknown',
                    'balls_bowled': bowler_stats_split[1] if len(bowler_stats_split) > 1 and bowler_stats_split[1].isdigit() else 'Unknown',
                    'wickets_taken': bowler_stats_split[2] if len(bowler_stats_split) > 2 and bowler_stats_split[2].isdigit() else 'Unknown',
                    'dot_balls': bowler_stats_split[3] if len(bowler_stats_split) > 3 and bowler_stats_split[3].isdigit() else 'Unknown'
                }
                data_store['bowler_stats'] = bowler_stats
                api_logger.debug(f"Bowler Stats: {bowler_stats}")

                # Log captured information
                api_logger.debug(f"Current Ball Info: {current_ball_info}")
                api_logger.debug(f"Favorite Team: {data_store.get('favorite_team', 'Unknown Team')}")
                api_logger.debug(f"Favorite Team Odds: {data_store.get('favorite_team_odds', '0+0')}")
                api_logger.debug(f"Session Data: {data_store.get('session_data', [])}")
                api_logger.debug(f"batsman_1_stats Data: {data_store.get('batsman_1_stats', {})}")
                api_logger.debug(f"batsman_2_stats Data: {data_store.get('batsman_2_stats', {})}")
                api_logger.debug(f"bowler_stats Data: {data_store.get('bowler_stats', {})}")

                # Retrieve and store local storage data if not already done
                # [FIX] Check if localStorage was already extracted from scorecard page
                if not data_store.get('local_storage_data'):
                    api_logger.info("[LOCALSTORAGE] Not found in data_store, attempting to extract from live page")
                    try:
                        if response.frame and response.frame.page:
                            page = response.frame.page
                            local_storage_data = categorize_local_storage_data(page)
                            if local_storage_data:
                                data_store['local_storage_data'] = local_storage_data
                                api_logger.info("[LOCALSTORAGE] Extracted from live page and stored in data_store")
                            else:
                                data_store['local_storage_data'] = {}
                                api_logger.warning("[LOCALSTORAGE] Could not be retrieved from live page")
                        else:
                            api_logger.warning("[LOCALSTORAGE] Response frame or page is None, cannot retrieve")
                            data_store['local_storage_data'] = {}
                    except Exception as e:
                        api_logger.error(f"[LOCALSTORAGE] Error retrieving from live page: {e}")
                        data_store['local_storage_data'] = {}
                else:
                    api_logger.info("[LOCALSTORAGE] Already available in data_store (from scorecard page), skipping live page extraction")
                        
                key_parameter = extract_key_from_url(response.url)
                if not key_parameter:
                    api_logger.warning("key parameter 'key' not found in sV3 response.")
                
                sc4_url = f"https://api-v1.com/v10/sC4.php?key={key_parameter}"
                api_logger.info(f"Triggering sC4 API call with URL: {sc4_url}")
                
                # Extract headers from the original sV3 request
                request_headers = response.request.headers
                filtered_headers = {
                    'accept': request_headers.get('accept', ''),
                    'authorization': request_headers.get('authorization', ''),
                    'referer': request_headers.get('referer', ''),
                    'sec-ch-ua': request_headers.get('sec-ch-ua', ''),
                    'sec-ch-ua-mobile': request_headers.get('sec-ch-ua-mobile', ''),
                    'sec-ch-ua-platform': request_headers.get('sec-ch-ua-platform', ''),
                    'user-agent': request_headers.get('user-agent', ''),
                }
                
                api_logger.info(f"filtered_headers: {filtered_headers}") 
                
                # [FIX] Ensure localStorage is available before making sC4 call
                if not data_store.get('local_storage_data'):
                    api_logger.warning("[SC4_CALL] localStorage not yet available, sC4 call will proceed but decoding may fail")
                else:
                    player_count = len(data_store['local_storage_data'].get('player_data', {}))
                    api_logger.info(f"[SC4_CALL] localStorage available with {player_count} player codes")
                
                # Make the sC4 API call asynchronously
                # Uncomment the synchronous call if needed
                # trigger_sC4_call(sc4_url, filtered_headers)
                trigger_sC4_call_async(sc4_url, filtered_headers, data_store)

                # Optionally, process the sC4_data if needed
                # Example: store in data_store or send to backend
                
        except Exception as e:
            api_logger.error(f"Error processing API response: {e}", exc_info=True)


def block_unnecessary_resources(route, request):
    """
    Blocks unnecessary resources like images and fonts to optimize scraping performance.

    Args:
        route: The route object.
        request: The request object.
    """
    resource_type = request.resource_type
    url = request.url
    if resource_type in ["image", "font"]:
        # Uncomment the following line to log blocked resources
        # scraper_logger.debug(f"Blocking resource: {url} ({resource_type})")
        route.abort()
    else:
        route.continue_()

def printUpdatedText(updatedTexts, token, url):
    """
    Sends updated text content to the backend.
    
    Args:
        updatedTexts (list): List of updated text strings.
        token (str): Bearer token for authentication.
        url (str): The URL being observed.
    """
    for text in updatedTexts:
        score_update = {'score_update': text}
        cricket_data_service.send_cricket_data_to_service(score_update, token, url)
        scraper_logger.info(score_update)

def fetchData(url, context=None):
    """
    Fetches data from a given URL using Playwright library.
    
    Args:
        url (str): The URL to fetch data from.
        context: Optional ScraperContext for monitoring and restart management.
    
    Returns:
        None
    """
    scraper_logger.info(f"Starting fetchData for URL: {url}")
    if context:
        scraper_logger.info(f"ScraperContext provided for {url}, restart logic enabled")
    
    # Create a new data store for this thread
    data_store = {
        'current_ball_info': 'No current ball info available',
        'favorite_team': 'Unknown Team',
        'favorite_team_odds': '0+0',
        'session_data': [],
        'batsman_1_stats': {},
        'batsman_2_stats': {},
        'bowler_stats': {},
        'url':url,
        'lock': threading.Lock()  # Added lock        
        # 'local_storage_data' will be added by handle_api_responses
    }
    
    # Scrape match info before proceeding to live scraping
    info_url = url.replace('/live', '/info')
    scraper_logger.info(f"Fetching match info from URL: {info_url}")
    
    # Determine if the match is a test match
    is_test_match = 'test' in url.lower()
    scraper_logger.info(f"Is test match: {is_test_match}")
    
    # Scrape match info using the crex_info_url.py module
    try:
        match_info_json = scrape_match_info(info_url)
        scraper_logger.info(f"Scraped match info: {match_info_json}")
        
        # Send match info to backend (once)
        token = cricket_data_service.get_bearer_token()
        # endpoint_url = os.getenv('API_ENDPOINT', 'http://spring-security-jwt-app:8099/cricket-data/match-info/save')
        endpoint_url = os.getenv('API_ENDPOINT', 'http://127.0.0.1:8099/cricket-data/match-info/save')

        cricket_data_service.send_data_to_api_endpoint(match_info_json, token, info_url, endpoint_url)
    except Exception as e:
        scraper_logger.error(f"Error scraping match info from {info_url}: {e}")
    
    with sync_playwright() as p:
        try:
            scraper_logger.info("Launching browser")
            headless = os.getenv('PLAYWRIGHT_HEADLESS', 'true').lower() not in ('0', 'false')
            browser = p.chromium.launch(
                headless=headless,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--no-first-run',
                    '--disable-infobars',
                    '--disable-extensions',  # Disable browser extensions
                    '--disable-plugins',     # Disable plugins
                    '--disable-images',      # Disable image loading for performance
                    '--disable-javascript-harmony-shipping',  # Disable experimental JS features
                    '--disable-background-networking',  # Disable background network requests
                    '--disable-default-apps',  # Disable default apps
                    '--disable-sync',  # Disable Chrome sync
                    '--metrics-recording-only',  # Reduce overhead
                    '--mute-audio',  # No audio needed
                    '--disable-web-security',  # Can help with CORS but use cautiously
                    '--disable-features=IsolateOrigins,site-per-process',  # Reduce process isolation overhead
                ]
            )
            scraper_logger.info("Browser launched successfully with optimized resource usage")
            browser_context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
                extra_http_headers={
                    'sec-ch-ua': '"Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"',
                    'sec-ch-ua-mobile': '?0',
                    'sec-ch-ua-platform': '"Windows"',
                }
            )
            page = browser_context.new_page()
            page.route("**/*", block_unnecessary_resources)

            scraper_logger.info("Browser context and page created")

            # **Step 1: Open /scorecard in a new tab to trigger localStorage population**
            scorecard_url = url.replace('/live', '/scorecard')
            scraper_logger.info(f"Opening scorecard URL in a new tab: {scorecard_url}")
            api_logger.info(f"[SCORECARD_TAB] Triggering scorecard page to populate localStorage")
            
            try:
                scorecard_page = browser_context.new_page()
                scorecard_page.route("**/*", block_unnecessary_resources)
                scraper_logger.info(f"Attempting to navigate to: {scorecard_url}")
                response = scorecard_page.goto(scorecard_url, timeout=30000, wait_until="networkidle")
                scraper_logger.info(f"Scorecard page loaded with status: {response.status if response else 'unknown'}")
                
                # **CRITICAL FIX: Extract localStorage from scorecard page after it loads**
                # This page has all player data populated in localStorage
                # Wait for network idle, then additional time for JS to populate localStorage
                api_logger.info(f"[SCORECARD_TAB] Waiting 5 seconds for localStorage to fully populate")
                time.sleep(5)  # Wait for JavaScript to populate localStorage
                
                try:
                    scorecard_local_storage_data = categorize_local_storage_data(scorecard_page)
                    data_store['local_storage_data'] = scorecard_local_storage_data
                    api_logger.info(f"[SCORECARD_TAB] Successfully extracted complete localStorage from scorecard page")
                    api_logger.info(f"[SCORECARD_TAB] Player codes available: {len(scorecard_local_storage_data.get('player_data', {}))} players")
                except Exception as storage_error:
                    api_logger.error(f"[SCORECARD_TAB] Failed to extract localStorage: {storage_error}")
                    
            except Exception as e:
                scraper_logger.error(f"Failed to load scorecard page {scorecard_url}: {e}")
                # Skip scorecard page and continue with main scraping
                scraper_logger.info("Skipping scorecard page, continuing with live page scraping...")
                scorecard_page = None
            
            # **Step 2: Extract cookies from the browser context**
            cookies = browser_context.cookies()
            scraper_logger.debug(f"Extracted cookies: {cookies}")
            
            # Close the scorecard tab if it was opened successfully
            if scorecard_page:
                try:
                    scorecard_page.close()
                    scraper_logger.info("Scorecard tab closed")
                    api_logger.info(f"[SCORECARD_TAB] Scorecard tab closed, localStorage preserved in browser context")
                except Exception as e:
                    scraper_logger.warning(f"Error closing scorecard tab: {e}")
            
            # Navigate to the page first to ensure it is loaded
            scraper_logger.info(f"Navigating to live page URL: {url}")
            try:
                response = page.goto(url, timeout=45000, wait_until="domcontentloaded")
                scraper_logger.info(f"Live page loaded successfully with status: {response.status if response else 'unknown'}")
            except Exception as e:
                scraper_logger.error(f"Failed to load live page {url}: {e}")
                raise  # Re-raise to be caught by outer exception handler

            # Attach API response listener to capture current ball info
            page.on("response", lambda response: handle_api_responses(response, data_store))

            # Add a listener for page errors
            page.on('error', lambda error: scraper_logger.error(f"Uncaught error: {error.name}: {error.message}"))
            
            
            # Get the token before entering the observation loop
            if 'token' not in locals():
                token = cricket_data_service.get_bearer_token()
                scraper_logger.info(f"Bearer token obtained: {token}")

            # Retry logic for finding and clicking the Odds View button only for test matches
            isButtonFoundFlag = False
            max_retries = 3  # Maximum number of retries
            retry_count = 0

            if is_test_match:
                while retry_count < max_retries and not isButtonFoundFlag:
                    try:
                        scraper_logger.info(f"Attempting to find and click the Odds View button, attempt {retry_count + 1}")
                        isButtonFoundFlag = search_and_click_odds_button(page)
                        if isButtonFoundFlag:
                            scraper_logger.info(f"Button found on attempt {retry_count + 1}")
                        else:
                            retry_count += 1
                            scraper_logger.warning(f"Retrying... {retry_count}/{max_retries}")
                            if retry_count >= max_retries:
                                scraper_logger.info("Max retries exceeded, skipping odds fetching.")
                    except Exception as e:
                        scraper_logger.error(f"Error during navigation or odds button attempt: {e}")
                        retry_count += 1
            else:
                scraper_logger.info("Not a test match, skipping Odds View button click.")

            # Start the observation loop in the main thread
            observeTextChanges(page, isButtonFoundFlag, token, url, retry_count, max_retries, data_store, is_test_match, context)

        except Exception as e:
            scraper_logger.error(f"Uncaught error: {e}", exc_info=True)
        finally:
            # NOTE: Batched data flushing removed - using non-batched service
            # No pending data to flush since we send immediately
            
            browser.close()
            scraper_logger.info("Browser closed.")
            # NOTE: Do NOT shutdown the global executor here - it's shared across all scraper instances
            # The executor will be cleaned up when the Flask app shuts down
            # executor.shutdown(wait=True)
            # scraper_logger.info("ThreadPoolExecutor shutdown completed.")

def search_and_click_odds_button(page):
    """
    Searches for the "Odds View" button on the page and clicks on it.
    
    Args:
        page: The Playwright page object.
    
    Returns:
        True if the button is found and clicked successfully, False otherwise.
    """
    try:
        # Wait for the "Odds View" button to appear in the DOM
        page.wait_for_selector('.odds-view-btn .view:nth-child(2)', timeout=3000)
        
        # Run JavaScript on the page to click on the "Odds View" button
        page.evaluate('''
            () => {
                const oddsViewButton = document.querySelector('.odds-view-btn .view:nth-child(2)');
                if (oddsViewButton) {
                    oddsViewButton.click();
                }
            }
        ''')
        scraper_logger.info("Clicked on the Odds View button")
        return True
    except Exception as e:
        scraper_logger.error(f"Odds View button not found within the specified timeout period: {e}")
        return False

def observeTextChanges(page, isButtonFoundFlag, token, url, retry_count, max_retries, data_store, is_test_match, context=None):
    """
    Observes text changes on a web page and sends updated data to the backend.
    
    Args:
        page: The Playwright page object.
        isButtonFoundFlag (bool): Flag indicating if the Odds View button was found.
        token (str): Bearer token for authentication.
        url (str): The URL being observed.
        retry_count (int): Current retry count for button clicks.
        max_retries (int): Maximum number of retries allowed.
        data_store (dict): Shared data storage for scraped data.
        is_test_match (bool): Flag indicating if the match is a test match.
        context: Optional ScraperContext for monitoring and restart management.
    
    Returns:
        None
    """
    scraper_logger.info("Starting observation of text changes")
    if context:
        scraper_logger.info(f"Context monitoring enabled for {url}")

    try:
        running = True
        previousTexts = set()
        previousData = []
        previousScore = []
        iteration_count = 0
        
        while running:
            iteration_count += 1
            
            # Check if context requests restart (memory/age/errors exceeded)
            if context and context.should_restart():
                scraper_logger.warning(
                    f"Context requesting restart for {url}: "
                    f"reason={context.restart_reason}, "
                    f"uptime={context.uptime_seconds}s, "
                    f"memory_mb={context.memory_bytes / (1024 * 1024):.1f}, "
                    f"errors={context.error_count}"
                )
                # Request restart so _finalize_context will automatically restart the scraper
                context.request_restart(reason=context.restart_reason or "automatic_lifetime_restart")
                running = False
                break
            
            # Check if the task is marked for stopping
            if scraping_tasks.get(url, {}).get('status') == 'stopping':
                scraper_logger.info(f'Stopping scraping task for url: {url}')
                running = False
                break

            try:
                # Refresh local storage data
                try:
                    local_storage_data = categorize_local_storage_data(page)
                    if local_storage_data:
                        data_store['local_storage_data'] = local_storage_data
                        scraper_logger.warning("Local storage data refreshed and stored in data_store.")
                    else:
                        data_store['local_storage_data'] = {}
                        scraper_logger.warning("Local storage data could not be refreshed.")
                except Exception as e:
                    scraper_logger.error(f"Error refreshing local storage data in observeTextChanges: {e}")
                    data_store['local_storage_data'] = {}
                    
                # Extract and send batsman and bowler data
                try:
                    batsman_1_stats = data_store.get('batsman_1_stats', {})
                    batsman_2_stats = data_store.get('batsman_2_stats', {})
                    bowler_stats = data_store.get('bowler_stats', {})

                    scraper_logger.warning(f"Using API extracted batsman and bowler data: \nBatsman 1: {batsman_1_stats} \nBatsman 2: {batsman_2_stats} \nBowler: {bowler_stats}")
                    scraper_logger.warning(f"All data from local storage: {json.dumps(data_store.get('local_storage_data', {}), indent=2)}")
                    # Retrieve local storage data from data_store
                    if data_store.get('local_storage_data'):
                        scraper_logger.debug("Local storage data is available, attempting to retrieve team data...")
                        player_data = data_store['local_storage_data'].get('player_data', {})
                        scraper_logger.warning(f"Player data from local storage: {json.dumps(player_data, indent=2)}")
                        scraper_logger.debug(f"Team data from local storage: {json.dumps(data_store['local_storage_data'].get('team_data', {}), indent=2)}")
                        
                        # Update batsman and bowler names from local storage values 
                        batsman_1_stats['name'] = player_data.get(f"p_{batsman_1_stats.get('name', '')}_name", 'Unknown Batsman 1')
                        batsman_2_stats['name'] = player_data.get(f"p_{batsman_2_stats.get('name', '')}_name", 'Unknown Batsman 2')
                        bowler_stats['name'] = player_data.get(f"p_{bowler_stats.get('name', '')}_name", 'Unknown Bowler')

                    # Prepare data to send to the backend
                    batsman_and_bowler_data = {
                        "batsman_data": [
                            batsman_1_stats,  # Send batsman 1 data
                            batsman_2_stats    # Send batsman 2 data
                        ],
                        "bowler_data": bowler_stats,  # Send bowler data
                        "url": url
                    }
                    
                    # Send batsman and bowler data
                    cricket_data_service.send_cricket_data_to_service(batsman_and_bowler_data, token, url)
                    scraper_logger.info(f"Batsman and Bowler data sent: {batsman_and_bowler_data}")

                except Exception as e:
                    scraper_logger.error(f"Error during batsman and bowler data extraction: {e}")   

                # Evaluate JavaScript on the page to get updated texts
                updatedTexts = page.evaluate('''
                    () => {
                        const spans = document.querySelectorAll('.result-box span');
                        return Array.from(spans).map(span => span.textContent.trim());
                    }
                ''')
                scraper_logger.debug(f"Updated texts: {updatedTexts}")
                
                # Extract CRR
                crr = page.evaluate('''
                    () => {
                        const crrElement = document.querySelector('.team-run-rate .data');
                        return crrElement ? crrElement.textContent.trim() : 'CRR not found';
                    }
                ''')
                scraper_logger.debug(f"CRR: {crr}")
                
                # Extract the "KAR need 277 runs to win" text
                final_result_text = page.evaluate('''
                    () => {
                        const finalResultElement = document.querySelector('.final-result.m-none');
                        return finalResultElement ? finalResultElement.textContent.trim() : 'Final result text not found';
                    }
                ''')
                scraper_logger.debug(f"Final Result Text: {final_result_text}")
                
                # Extract Score
                score = page.evaluate('''
                    () => {
                        const teamDivs = Array.from(document.querySelectorAll('.team-content'));
                        return teamDivs.map(div => {
                            const teamNameElement = div.querySelector('.team-name');
                            const runsElement = div.querySelector('.runs span:nth-child(1)');
                            const overElement = div.querySelector('.runs span:nth-child(2)');
                            const teamName = teamNameElement ? teamNameElement.textContent.trim() : 'Unknown Team';
                            const score = runsElement ? runsElement.textContent : '0/0';
                            const over = overElement ? overElement.textContent : '0.0';
                            return {
                                teamName,
                                score,
                                over,
                            };
                        });
                    }
                ''')
                scraper_logger.debug(f"Score: {score}")

                # Extract Overs Data
                overs_data = page.evaluate('''() => {
                    const overs = [];
                    document.querySelectorAll('div#slideOver .overs-slide').forEach(overElement => {
                        const overNumber = overElement.querySelector('span').textContent;
                        const balls = Array.from(overElement.querySelectorAll('.over-ball')).map(ball => ball.textContent);
                        const totalRuns = overElement.querySelector('.total').textContent;

                        overs.push({
                            overNumber: overNumber.trim(),
                            balls: balls,
                            totalRuns: totalRuns.trim()
                        });
                    });
                    return overs;
                }''')
                scraper_logger.debug(f"Overs data: {overs_data}")

                # Log extracted data
                for over in overs_data:
                    scraper_logger.debug(f"{over['overNumber']}: {' '.join(over['balls'])} (Total: {over['totalRuns']})")

                # Prepare match update data
                data_to_send = {
                    "match_update": {
                        "score": score[0] if score else {},  # Send the first score object or an empty dict if no score
                        "crr": crr,
                        "final_result_text": final_result_text
                    },
                    "overs_data": overs_data if overs_data else [],
                }
                if score != previousScore:
                    scraper_logger.info(f"Sending match update data: {data_to_send['match_update']}")
                    cricket_data_service.send_cricket_data_to_service(data_to_send, token, url)
                    previousScore = score

                # Handle Odds Data for Test Matches
                if isButtonFoundFlag and is_test_match:
                    scraper_logger.info(f"Button found, searching for odds in test for url: {url}")

                    # Extract odds data for test matches
                    odds_data = page.evaluate('''
                        () => {
                            const teamDivs = Array.from(document.querySelectorAll('.fav-odd .d-flex'));
                            return teamDivs.map(div => {
                                const teamName = div.querySelector('.team-name span').textContent;
                                const odds = Array.from(div.querySelectorAll('.odd div')).map(div => div.textContent);
                                return {
                                    teamName,
                                    backOdds: odds[0],
                                    layOdds: odds[1],
                                };
                            });
                        }
                    ''')

                    # Compare data to previous data and if not the same then send
                    if odds_data != previousData:
                        scraper_logger.info(f"Odds data changed: {odds_data}")
                        # Prepare and send odds data
                        odds_payload = {
                            "odds_data": odds_data,
                            "url": url
                        }
                        cricket_data_service.send_cricket_data_to_service(odds_payload, token, url)
                        previousData = odds_data

                # Handle Odds Data for Non-Test Matches
                if not is_test_match:
                    try:
                        # Prepare the data structure to match your previous format
                        odds = data_store.get('favorite_team_odds', '0+0').split('+')  # Assuming odds are in the format 'X+Y'
                        back_odds = odds[0] if len(odds) > 0 else '0'
                        lay_odds = str(int(back_odds) + int(odds[1])) if len(odds) > 1 else back_odds
                        
                        # Fetch the favorite team name from local storage
                        favorite_team = data_store.get('favorite_team', 'Unknown Team')
                        scraper_logger.debug(f"Favorite team from data_store: {favorite_team}")

                        if data_store.get('local_storage_data'):
                            scraper_logger.debug("Local storage data is available, attempting to retrieve team data...")
                            team_data = data_store['local_storage_data'].get('team_data', {})
                            scraper_logger.debug(f"Team data from local storage: {json.dumps(team_data, indent=2)}")

                            # First, try to get team name using team code (e.g., 'Y4')
                            team_key_name = f't_{favorite_team}_name'
                            teamNameFromLocalStorage = team_data.get(team_key_name)
                            if teamNameFromLocalStorage:
                                teamName = teamNameFromLocalStorage
                                scraper_logger.info(f"Favorite team from local storage by code: {teamName}")
                            else:
                                # If not found by code, try to find by matching team name
                                for key, value in team_data.items():
                                    if key.endswith('_name') and value.strip().lower() == favorite_team.strip().lower():
                                        teamName = value.strip()
                                        scraper_logger.info(f"Favorite team found in team_data by name: {teamName}")
                                        break
                                else:
                                    teamName = favorite_team
                                    scraper_logger.warning(f"Favorite team '{favorite_team}' not found in team_data. Using code as team name.")
                        else:
                            scraper_logger.warning("Local storage data not available. Using team name from data_store.")  
                            
                        odds_payload = {
                            'firstTeamData': [
                                {
                                    'teamName': teamName,  # Map the favorite team
                                    'backOdds': back_odds,  # Use the first value for back odds
                                    'layOdds': lay_odds  # Use the second value for lay odds
                                }
                            ],
                            'sessionData': data_store.get('session_data', [])  # Leave this empty or add relevant data if available
                        }
                        
                        # Log and send the API-fetched odds data
                        scraper_logger.info(f"Sending formatted odds data: {odds_payload}")
                        cricket_data_service.send_cricket_data_to_service(odds_payload, token, url)

                    except Exception as e:
                        scraper_logger.error(f"Error during odds evaluation or sending: {e}")

                # Only print if the text content has changed
                if set(updatedTexts) != previousTexts:
                    scraper_logger.info(f"Text content changed: {updatedTexts}")
                    printUpdatedText(updatedTexts, token, url)
                    previousTexts = set(updatedTexts)

            except Exception as e:
                scraper_logger.error(f"Error during DOM manipulation: {e}", exc_info=True)
                # Record error in context if available
                if context:
                    context.record_error()

            # Update resource usage periodically (every 10 iterations ~25 seconds)
            if context and iteration_count % 10 == 0:
                try:
                    context.update_resource_usage()
                    scraper_logger.debug(
                        f"Resource update: memory={context.memory_bytes / (1024 * 1024):.1f}MB, "
                        f"cpu={context.cpu_percent:.1f}%, "
                        f"uptime={context.uptime_seconds}s, "
                        f"errors={context.error_count}"
                    )
                except Exception as e:
                    scraper_logger.warning(f"Failed to update resource usage: {e}")

            # Wait for 2.5 seconds before the next iteration
            try:
                time.sleep(2.5)
            except KeyboardInterrupt:
                running = False
                scraper_logger.info("Observation loop stopped by user.")
                sys.exit(0)  # Exit the script with a status code of 0 (success)

    except Exception as e:
        scraper_logger.error(f"Uncaught error in observeTextChanges: {e}", exc_info=True)

# Main function invocation
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch and observe data from a given URL.")
    parser.add_argument("url", type=str, help="The URL to observe")

    args = parser.parse_args()
    fetchData(args.url)
