from playwright.sync_api import sync_playwright
import logging
from dataclasses import dataclass, field
import json
import time

# Configure logging with in-depth logging capabilities
logging.basicConfig(
    filename='enhanced_match_data_with_detailed_logs.log',
    level=logging.DEBUG,  # Using DEBUG to capture all levels of logs
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Add console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
logging.getLogger('').addHandler(console_handler)

# Dismissal codes mapping
DISMISSAL_CODES = {
    "^2": "Caught Out",
    "^4": "Run Out",
    "B": "Bowled",
    "o": "Over",
    "bc": "Boundary Check",
    # Add more mappings as per API specifications
}

@dataclass
class Player:
    name: str
    runs: int = 0
    balls_faced: int = 0
    fours: int = 0
    sixes: int = 0
    on_strike: bool = False
    additional_stats: dict = field(default_factory=dict)
    stats: dict = None  # Existing stats (e.g., for bowler)

@dataclass
class Team:
    name: str
    short_name: str = None  # Optional short name

@dataclass
class MatchData:
    bowling_first_team: str
    teams: dict
    session_overs: list
    favorite_team: dict
    players: dict
    current_play: dict
    series: dict

def parse_runs_and_balls(value):
    """
    Parses the runs and balls faced from the given string.
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
    """
    parts = value.split('.') if value else []
    fours = int(parts[0]) if len(parts) > 0 and parts[0].isdigit() else 0
    sixes = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    # Capture additional unknown stats
    additional_stats = {
        'stat_3': parts[2] if len(parts) > 2 else 'Unknown',
        'stat_4': parts[3] if len(parts) > 3 else 'Unknown'
    }
    return fours, sixes, additional_stats

def categorize_local_storage_data(page):
    try:
        logging.debug("Attempting to extract local storage data...")
        local_storage = page.evaluate("() => window.localStorage")
        logging.info("Successfully extracted local storage data.")

        player_data = {k: v for k, v in local_storage.items() if k.startswith('p_')}
        team_data = {k: v for k, v in local_storage.items() if k.startswith('t_')}
        series_data = {k: v for k, v in local_storage.items() if k.startswith('s_')}

        logging.debug(f"Player Data Map: {player_data}")
        logging.debug(f"Team Data Map: {team_data}")
        logging.debug(f"Series Data Map: {series_data}")

        return {
            'player_data': player_data,
            'team_data': team_data,
            'series_data': series_data
        }
    except Exception as e:
        logging.error(f"Error extracting or mapping local storage: {e}", exc_info=True)
        return None

def match_data_to_dict(match_data):
    return {
        'bowling_first_team': match_data.bowling_first_team,
        'teams': {
            'team_1': match_data.teams['team_1'].__dict__,
            'team_2': match_data.teams['team_2'].__dict__
        },
        'session_overs': match_data.session_overs,
        'favorite_team': match_data.favorite_team,
        'players': {
            'batsman_1': match_data.players['batsman_1'].__dict__,
            'batsman_2': match_data.players['batsman_2'].__dict__,
            'bowler': match_data.players['bowler'].__dict__
        },
        'current_play': match_data.current_play,
        'series': match_data.series
    }

def intercept_network_calls_and_log_local_storage(url):
    try:
        with sync_playwright() as p:
            logging.debug("Starting Playwright browser...")

            browser = p.chromium.launch(headless=True)
            logging.info("Browser launched successfully.")

            context = browser.new_context()
            page = context.new_page()
            logging.info("New page created.")

            blocked_resource_types = ["image", "stylesheet", "font", "media", "other"]
            def block_unnecessary_resources(route, request):
                if request.resource_type in blocked_resource_types:
                    route.abort()
                else:
                    route.continue_()

            page.route("**/*", block_unnecessary_resources)

            def log_response(response):
                if "sV3.php" in response.url:
                    try:
                        # Check if the response has a successful status code
                        # Retry logic
                        max_retries = 3
                        retry_delay = 1  # seconds
                        for attempt in range(max_retries):
                            try:
                                if response.status != 200:
                                    if response.status in [502, 503, 504]:
                                        logging.warning(f"Transient error {response.status} from {response.url}, attempt {attempt + 1}")
                                        time.sleep(retry_delay)
                                        continue
                                    else:
                                        logging.error(f"API Response from {response.url} returned status code {response.status}")
                                        return

                                # Proceed with JSON parsing and processing
                                api_data = response.json()
                                # logging.info(f"API Response from {response.url}: {api_data}")
                            except Exception as e :
                                logging.error(f"Error processing API response from {response.url}: {e}", exc_info=True)
                                time.sleep(retry_delay)

                         # Attempt to parse the JSON regardless of Content-Type
                        try:
                            api_data = response.json()
                        except Exception as e:
                            # Log error and raw response
                            response_text = response.text()
                            logging.error(f"Failed to parse JSON from {response.url}: {e}")
                            logging.error(f"Response Body: {response_text}")
                            return
                        
                        logging.info(f"API Response from {response.url}: {api_data}")
                        

                        local_storage_data = categorize_local_storage_data(page)
                        if local_storage_data:
                            player_data = local_storage_data['player_data']
                            team_data = local_storage_data['team_data']
                            series_data = local_storage_data['series_data']

                            # Extract team identifiers
                            a_field = api_data.get('a', '')
                            team_ids = a_field.split('.') if a_field else []
                            team_1_id = team_ids[0] if len(team_ids) > 0 else None
                            team_2_id = team_ids[1] if len(team_ids) > 1 else None

                            team_1 = Team(
                                name=team_data.get(f't_{team_1_id}_name', 'Unknown Team 1'),
                                short_name=team_data.get(f't_{team_1_id}_short', None)
                            ) if team_1_id else Team(name='Unknown Team 1')

                            team_2 = Team(
                                name=team_data.get(f't_{team_2_id}_name', 'Unknown Team 2'),
                                short_name=team_data.get(f't_{team_2_id}_short', None)
                            ) if team_2_id else Team(name='Unknown Team 2')

                            # Bowling team
                            bowling_team_key = api_data.get('wp', '').split(',')[0] if 'wp' in api_data else None
                            bowling_first_team = team_data.get(f't_{bowling_team_key}_short', 'Unknown Bowling Team') if bowling_team_key else 'Bowling team not yet determined'

                            # Favorite team
                            favorite_team_key = api_data.get('F', '').replace('^', '')
                            favorite_team_name = team_data.get(f't_{favorite_team_key}_name', 'Unknown Team')

                            # Session overs and odds
                            session_overs = api_data.get('D', '')
                            session_odds = api_data.get('Z', '')

                            session_over_list = session_overs.split(',') if session_overs else []
                            session_odds_list = session_odds.split(',') if session_odds else []

                            session_data = [
                                {'over': over, 'odds': odds}
                                for over, odds in zip(session_over_list, session_odds_list)
                            ]

                            # Players
                            p_field = api_data.get('p', '')
                            p_split = p_field.split('.') if p_field else []

                            batsman1_id = p_split[0] if len(p_split) > 0 else None
                            batsman2_id = p_split[1] if len(p_split) > 1 else None

                            # Parsing batsman 1 stats
                            q_value = api_data.get('q', '')
                            batsman1_runs, batsman1_balls_faced, batsman1_on_strike = parse_runs_and_balls(q_value)
                            r_value = api_data.get('r', '')
                            batsman1_fours, batsman1_sixes, batsman1_additional_stats = parse_batsman_stats(r_value)

                            batsman1 = Player(
                                name=player_data.get(f'p_{batsman1_id}_name', 'Unknown Batsman 1'),
                                runs=batsman1_runs,
                                balls_faced=batsman1_balls_faced,
                                fours=batsman1_fours,
                                sixes=batsman1_sixes,
                                on_strike=batsman1_on_strike,
                                additional_stats=batsman1_additional_stats
                            )
                            
                            # Parsing batsman 2 stats
                            s_value = api_data.get('s', '')
                            batsman2_runs, batsman2_balls_faced, batsman2_on_strike = parse_runs_and_balls(s_value)
                            t_value = api_data.get('t', '')
                            batsman2_fours, batsman2_sixes, batsman2_additional_stats = parse_batsman_stats(t_value)

                            batsman2 = Player(
                                name=player_data.get(f'p_{batsman2_id}_name', 'Unknown Batsman 2'),
                                runs=batsman2_runs,
                                balls_faced=batsman2_balls_faced,
                                fours=batsman2_fours,
                                sixes=batsman2_sixes,
                                on_strike=batsman2_on_strike,
                                additional_stats=batsman2_additional_stats
                            )

                            # Bowler
                            bowler_id = api_data.get('b', '')
                            bowler_name = player_data.get(f'p_{bowler_id}_name', 'Unknown Bowler') if bowler_id else 'Unknown Bowler'

                            # Bowler stats
                            c_field = api_data.get('c', '')
                            bowler_stats_split = c_field.split('.') if c_field else []
                            bowler_stats = {
                                'runs_conceded': bowler_stats_split[0] if len(bowler_stats_split) > 0 and bowler_stats_split[0].isdigit() else 'Unknown',
                                'balls_bowled': bowler_stats_split[1] if len(bowler_stats_split) > 1 and bowler_stats_split[1].isdigit() else 'Unknown',
                                'wickets_taken': bowler_stats_split[2] if len(bowler_stats_split) > 2 and bowler_stats_split[2].isdigit() else 'Unknown',
                                'dot_balls': bowler_stats_split[3] if len(bowler_stats_split) > 3 and bowler_stats_split[3].isdigit() else 'Unknown'
                            }

                            bowler = Player(
                                name=bowler_name,
                                stats=bowler_stats
                            )

                            # Current play
                            current_over_balls = api_data.get('A', 'No current over info available')
                            current_ball_info = api_data.get('B', 'No current ball info available')

                            # Series data
                            series_name_key = next((key for key in series_data if key.endswith('_name')), None)
                            series_short_key = next((key for key in series_data if key.endswith('_short')), None)

                            series = {
                                'series_name': series_data.get(series_name_key, 'Unknown Series') if series_name_key else 'Unknown Series',
                                'series_short': series_data.get(series_short_key, 'Unknown Series Short') if series_short_key else 'Unknown Series Short'
                            }

                            # Construct match data using the dataclass
                            match_data = MatchData(
                                bowling_first_team=bowling_first_team,
                                teams={
                                    'team_1': team_1,
                                    'team_2': team_2
                                },
                                session_overs=session_data,
                                favorite_team={
                                    'name': favorite_team_name,
                                    'odds': api_data.get('R', '0+0')
                                },
                                players={
                                    'batsman_1': batsman1,
                                    'batsman_2': batsman2,
                                    'bowler': bowler
                                },
                                current_play={
                                    'current_over_balls': current_over_balls,
                                    'current_ball_info': current_ball_info
                                },
                                series=series
                            )

                            # Log the enhanced match data
                            logging.info(f"Enhanced Match Data: {match_data}")
                        else:
                            logging.warning("Local storage data was not available or could not be mapped.")
                    except ValueError as ve:
                        # JSON decoding failed
                        logging.error(f"JSON decoding failed for response from {response.url}: {ve}", exc_info=True)
                        # Log the raw response text for debugging
                        try:
                            response_text = response.text()
                            logging.error(f"Response Body: {response_text}")
                        except Exception as e:
                            logging.error(f"Failed to retrieve response text: {e}", exc_info=True)
                    except Exception as e:
                        # Catch-all for any other exceptions
                        logging.error(f"Error processing API response from {response.url}: {e}", exc_info=True)

            page.on("response", log_response)

            # Navigate to the match URL
            logging.info(f"Navigating to match URL: {url}")
            page.goto(url, timeout=60000)
            page.wait_for_load_state('networkidle')
            logging.debug("Page loaded.")

            # Initial local storage extraction
            logging.debug("Extracting and logging local storage after page load.")
            categorize_local_storage_data(page)

            # Keep listening for responses
            logging.debug("Listening for network responses.")
            page.wait_for_timeout(300000)  # Adjust time based on match duration

            logging.info("Closing the browser.")
            context.close()
            browser.close()

    except Exception as e:
        logging.error(f"Critical error in intercepting network calls: {e}", exc_info=True)

def retry(func, retries=3, delay=5):
    for attempt in range(retries):
        try:
            return func()
        except Exception as e:
            logging.warning(f"Attempt {attempt + 1} failed with error: {e}")
            time.sleep(delay)
    logging.error(f"All {retries} attempts failed.")
    return None

if __name__ == "__main__":
    try:
        logging.info("Script started.")
        # Implementing retry logic for the main function
        retry(lambda: intercept_network_calls_and_log_local_storage('https://crex.live/scoreboard/R29/1NM/Eliminator-1/Y4/Y5/lio-vs-sta-eliminator-1-champions-one-day-cup-2024/live'))
    except Exception as e:
        logging.critical(f"Uncaught error in main script execution: {e}", exc_info=True)
