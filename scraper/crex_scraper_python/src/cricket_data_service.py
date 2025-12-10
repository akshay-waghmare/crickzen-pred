import requests
import os
import time
from typing import Dict, Any, Optional
from .loggers.adapters import get_logger
from .core.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError
from .core.retry_utils import RetryConfig, retryable, RetryError

logger = get_logger(component="cricket_data_service")

# Circuit breakers for external dependencies
_auth_breaker = CircuitBreaker.from_settings("backend_auth")
_api_breaker = CircuitBreaker.from_settings("backend_api")

# Track fast update timestamps per match URL to avoid stale regular pushes overwriting fresh data
# Key: source_url, Value: timestamp of last fast update
_fast_update_timestamps: Dict[str, float] = {}

# How long (seconds) after a fast update should we skip regular pushes
FAST_UPDATE_GRACE_PERIOD = 5.0

class CricketDataService:
    BASE_URL = os.getenv('BACKEND_URL', 'http://127.0.0.1:8099')
    TOKEN_URL = os.getenv('TOKEN_URL', 'http://127.0.0.1:8099/token/generate-token')

    @staticmethod
    def get_bearer_token():
        """Fetches the bearer token for authentication from local backend."""
        logger.info("auth.token.start")
        
        credentials = {
            "username": os.getenv('BACKEND_USERNAME', 'tanmay'),
            "password": os.getenv('BACKEND_PASSWORD', 'tanmay')
        }
        
        def _fetch_token():
            response = requests.post(CricketDataService.TOKEN_URL, json=credentials, timeout=2)
            response.raise_for_status()
            return response.json().get("token")
        
        try:
            token = _auth_breaker.call(_fetch_token)
            logger.info("auth.token.success")
            return token
        except CircuitBreakerOpenError:
            logger.warning("auth.token.circuit_open", metadata={"breaker": "backend_auth"})
            return None
        except Exception as e:
            logger.error("auth.token.error", metadata={"error": str(e)})
            return None  # Don't raise, just return None so scraping can continue

    @staticmethod
    def add_live_matches(urls, token):
        """Adds live match URLs to the local backend service."""
        # NOTE: /cricket-data/add-live-matches endpoint is public (permitAll in WebSecurityConfig)
        # No token required, but we still accept it for backwards compatibility
        logger.info("matches.add.start", metadata={"url_count": len(urls)})
        
        add_matches_url = os.getenv('ADD_LIVE_MATCHES_URL', 'http://127.0.0.1:8099/cricket-data/add-live-matches')
        
        def _post_matches():
            headers = {"Content-Type": "application/json"}
            if token:
                headers["Authorization"] = f"Bearer {token}"
            response = requests.post(add_matches_url, json=urls, headers=headers, timeout=2)
            response.raise_for_status()
            return response
        
        try:
            _api_breaker.call(_post_matches)
            logger.info("matches.add.success", metadata={"url_count": len(urls)})
        except CircuitBreakerOpenError:
            logger.warning("matches.add.circuit_open", metadata={"breaker": "backend_api"})
        except Exception as e:
            logger.error("matches.add.error", metadata={"error": str(e), "url": add_matches_url})
            # Don't raise - allow scraping to continue even if backend sync fails

    @staticmethod
    def fetch_match_data(match_id, token):
        """Fetches data for a specific match."""
        logger.info("matches.fetch.start", metadata={"match_id": match_id})
        try:
            headers = {"Authorization": f"Bearer {token}"}
            response = requests.get(f"{CricketDataService.BASE_URL}/matches/{match_id}", headers=headers)
            response.raise_for_status()
            match_data = response.json()
            logger.info("matches.fetch.success", metadata={"match_id": match_id})
            return match_data
        except Exception as e:
            logger.error("matches.fetch.error", metadata={"error": str(e), "match_id": match_id})
            raise

    @staticmethod
    def push_match_data(data, token, source_url):
        """
        Pushes match data to the backend service.
        
        Uses exponential backoff with jitter for retries (Feature 007).
        Skips push if a fast update was sent recently to avoid stale data overwriting fresh data.
        """
        # Check if a fast update was sent recently - skip stale regular push
        last_fast_update = _fast_update_timestamps.get(source_url, 0)
        time_since_fast = time.time() - last_fast_update
        if time_since_fast < FAST_UPDATE_GRACE_PERIOD:
            logger.debug("matches.push.skipped_stale", metadata={
                "url": source_url,
                "time_since_fast_update": round(time_since_fast, 2),
                "grace_period": FAST_UPDATE_GRACE_PERIOD
            })
            return True  # Return success but skip the push
        
        logger.info("matches.push.start", metadata={"url": source_url})
        start_time = time.time()
        
        service_url = os.getenv('SERVICE_URL', 'http://127.0.0.1:8099/cricket-data')
        
        # Retry config for push operations (Feature 007)
        push_retry_config = RetryConfig(
            max_attempts=3,
            base_delay=0.5,
            max_delay=4.0,
            jitter=0.25,
            retry_exceptions=(requests.RequestException, requests.Timeout, ConnectionError),
        )
        
        @retryable(config=push_retry_config, on_retry=lambda attempt, exc, delay: logger.warning(
            "matches.push.retry",
            metadata={"attempt": attempt, "error": str(exc), "delay": delay, "url": source_url}
        ))
        def _push_with_retry():
            headers = {"Content-Type": "application/json"}
            if token:
                headers["Authorization"] = f"Bearer {token}"
            
            # Transform data to match backend DTO structure
            try:
                payload = {
                    "url": source_url,
                    "match_update": {
                        "crr": data.get("run_rate"),
                        "final_result_text": data.get("result") if isinstance(data.get("result"), str) else (data.get("result")[0] if data.get("result") else None)
                    },
                    "overs_data": []
                }

                # Map Overs
                if data.get("overs_data"):
                    payload["overs_data"] = []
                    for o in data["overs_data"]:
                        if isinstance(o, dict):
                            payload["overs_data"].append({
                                "overNumber": o.get("overNumber"),
                                "balls": o.get("balls"),
                                "totalRuns": o.get("totalRuns", "").replace("= ", "") if o.get("totalRuns") else "0"
                            })
                        else:
                            logger.warning(f"Skipping invalid over data: {type(o)} {o}")
                elif data.get("overs"): # Fallback for legacy format
                    payload["overs_data"] = []
                    for o in data["overs"]:
                        if isinstance(o, dict):
                            payload["overs_data"].append({
                                "overNumber": o.get("over"),
                                "balls": o.get("balls"),
                                "totalRuns": o.get("total", "").replace("= ", "") if o.get("total") else "0"
                            })
                        else:
                            logger.warning(f"Skipping invalid over data: {type(o)} {o}")

                # Map Score (Batting Team)
                teams = data.get("teams", [])
                if teams:
                    # Use the first team as the primary batting team
                    batting_team = teams[0]
                    
                    if not isinstance(batting_team, dict):
                        logger.error(f"Invalid batting_team data: {type(batting_team)} {batting_team}")
                        batting_team = {} # Fallback

                    # Clean over string for nested score object
                    raw_over = batting_team.get("overs", "")
                    clean_over_str = raw_over
                    if raw_over:
                        # Remove parentheses if present e.g. (113.3) -> 113.3
                        clean_over_str = raw_over.replace("(", "").replace(")", "").strip()

                    payload["match_update"]["score"] = {
                        "teamName": batting_team.get("name"),
                        "score": batting_team.get("runs"),
                        "over": clean_over_str
                    }
                    
                    # Set root level fields for backward compatibility
                    payload["score"] = batting_team.get("runs")
                    payload["batting_team"] = batting_team.get("name")
                    
                    # Clean and set over
                    if clean_over_str:
                        try:
                            # Extract numeric part if mixed with text
                            import re
                            match = re.search(r"(\d+(\.\d+)?)", clean_over_str)
                            if match:
                                payload["over"] = float(match.group(1))
                        except (ValueError, TypeError):
                            pass

                # Map Odds (from DOM)
                odds = data.get("odds", [])
                if odds:
                    payload["firstTeamData"] = []
                    for odd in odds:
                        vals = odd.get("values", [])
                        if len(vals) >= 2:
                            payload["firstTeamData"].append({
                                "teamName": odd.get("team"),
                                "backOdds": vals[0],
                                "layOdds": vals[1]
                            })
                
                # Map Live API Data (Odds, Session, Runs on Ball)
                if data.get("team_odds"):
                    payload["team_odds"] = data["team_odds"]
                    if "favTeam" in data["team_odds"]:
                        payload["fav_team"] = data["team_odds"]["favTeam"]
                
                if data.get("session_odds"):
                    payload["session_odds"] = data["session_odds"]
                
                if data.get("runs_on_ball") is not None:
                    payload["runs_on_ball"] = data["runs_on_ball"]
                
                if data.get("overs_data"):
                    payload["overs_data"] = data["overs_data"]

                if data.get("current_ball"):
                    # Backend expects 'score_update' for current_ball field
                    cb = data["current_ball"]
                    if cb == 'e':
                        payload["score_update"] = "player entering"
                    elif cb == 'B':
                        payload["score_update"] = "ball start"
                    else:
                        payload["score_update"] = cb

                # Map Batsman Data
                if data.get("batsman_data"):
                    payload["batsman_data"] = data["batsman_data"]

                # Map Bowler Data
                # Backend expects a single object for bowler_data, but scraper provides a list.
                # We take the first bowler from the list.
                if data.get("bowler_data"):
                    bowlers = data["bowler_data"]
                    if isinstance(bowlers, list) and len(bowlers) > 0:
                        payload["bowler_data"] = bowlers[0]
                    elif isinstance(bowlers, dict):
                        payload["bowler_data"] = bowlers
                    else:
                        logger.warning(f"Unexpected bowler_data format: {type(bowlers)}")
                
                # Include raw data for debugging or other fields
                # payload["raw_data"] = data

                logger.info("matches.push.payload", metadata={"payload": payload})

                response = requests.post(service_url, json=payload, headers=headers)
                response.raise_for_status()
                return response
            except Exception as e:
                logger.error("matches.push.mapping_error", metadata={"error": str(e), "data_keys": list(data.keys())})
                raise e

        try:
            _api_breaker.call(_push_with_retry)
            elapsed = time.time() - start_time
            logger.info("matches.push.success", metadata={"url": source_url, "elapsed_ms": elapsed * 1000})
            return True
        except CircuitBreakerOpenError:
            logger.warning("matches.push.circuit_open", metadata={"breaker": "backend_api"})
            return False
        except RetryError as e:
            elapsed = time.time() - start_time
            logger.error("matches.push.retry_exhausted", metadata={
                "error": str(e), 
                "url": source_url,
                "elapsed_ms": elapsed * 1000,
            })
            return False
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error("matches.push.error", metadata={"error": str(e), "url": service_url, "elapsed_ms": elapsed * 1000})
            return False

    @staticmethod
    def push_match_info(data, token, source_url):
        """Pushes match info (static data) to the backend service."""
        logger.info("matches.push_info.start", metadata={"url": source_url})
        
        service_url = os.getenv('API_ENDPOINT', 'http://127.0.0.1:8099/cricket-data/match-info/save')
        
        def _push():
            headers = {"Content-Type": "application/json"}
            if token:
                headers["Authorization"] = f"Bearer {token}"
            
            # The legacy code copies data and adds url
            payload = data.copy()
            payload["url"] = source_url
            
            logger.info("matches.push_info.payload", metadata={"payload": payload})

            response = requests.post(service_url, json=payload, headers=headers)
            response.raise_for_status()
            return response

        try:
            _api_breaker.call(_push)
            logger.info("matches.push_info.success", metadata={"url": source_url})
            return True
        except CircuitBreakerOpenError:
            logger.warning("matches.push_info.circuit_open", metadata={"breaker": "backend_api"})
            return False
        except Exception as e:
            logger.error("matches.push_info.error", metadata={"error": str(e), "url": service_url})
            return False

    @staticmethod
    def push_sc4_stats(data: Dict[str, Any], token: str, source_url: str) -> bool:
        """
        Pushes full scorecard (sC4) stats to the backend.
        Endpoint: /cricket-data/sC4-stats/save
        """
        logger.info("matches.push_sc4.start", metadata={"url": source_url})
        
        # Use env var for endpoint, default to localhost for dev
        service_url = os.getenv('API_ENDPOINT_SC4', 'http://127.0.0.1:8099/cricket-data/sC4-stats/save')
        # In Docker, use the service name
        if os.getenv('DOCKER_ENV'):
             service_url = 'http://backend:8099/cricket-data/sC4-stats/save'
        
        def _push():
            headers = {"Content-Type": "application/json"}
            if token:
                headers["Authorization"] = f"Bearer {token}"
            
            # Construct payload matching legacy format
            # The backend expects the raw sC4 stats object + url
            # Legacy code wrapped it in "match_stats_by_innings"
            payload = {
                "match_stats_by_innings": data,
                "url": source_url
            }
            
            # Log payload size rather than content as it can be large
            logger.info("matches.push_sc4.payload_size", metadata={"size_bytes": len(str(payload))})

            response = requests.post(service_url, json=payload, headers=headers)
            response.raise_for_status()
            return response

        try:
            _api_breaker.call(_push)
            logger.info("matches.push_sc4.success", metadata={"url": source_url})
            return True
        except CircuitBreakerOpenError:
            logger.warning("matches.push_sc4.circuit_open", metadata={"breaker": "backend_api"})
            return False
        except Exception as e:
            logger.error("matches.push_sc4.error", metadata={"error": str(e), "url": service_url})
            return False

    @staticmethod
    def get_live_matches(token):
        """Fetches list of live matches from backend."""
        logger.info("matches.list.start")
        url = f"{CricketDataService.BASE_URL}/cricket-data/live-matches"
        
        def _fetch():
            headers = {}
            if token:
                headers["Authorization"] = f"Bearer {token}"
            response = requests.get(url, headers=headers, timeout=5)
            response.raise_for_status()
            return response.json()

        try:
            matches = _api_breaker.call(_fetch)
            logger.info("matches.list.success", metadata={"count": len(matches)})
            return matches
        except Exception as e:
            logger.error("matches.list.error", metadata={"error": str(e)})
            return []

    @staticmethod
    def push_immediate_sv3(api_data: dict, token: str, source_url: str, local_storage: dict = None) -> bool:
        """
        Push sV3 data immediately for fast updates.
        
        Sends only the fast-changing fields that the backend merges:
        - team_odds: {backOdds, layOdds}
        - over: current over number
        - runs_on_ball: current ball outcome
        - current_ball / score_update: ball event description
        - fav_team: favorite team name (decoded from localStorage)
        - session_odds: session betting odds
        - overs_data: recent over breakdowns
        
        Args:
            api_data: Raw sV3 API data
            token: Auth token
            source_url: Match URL
            local_storage: Cached localStorage dict with team/player name mappings
        
        Feature: 007-fast-updates
        """
        import time
        start_time = time.time()
        
        service_url = os.getenv('SERVICE_URL', 'http://127.0.0.1:8099/cricket-data')
        
        # Special codes mapping for B field
        SPECIAL_CODES = {
            "^2": "Caught Out",
            "^4": "Run Out",
            "B": "Ball Start",
            "o": "Over",
            "bc": "Boundary Check",
            "wd": "Wide",
            "nb": "No Ball",
            "w": "Wicket",
            "e": "player entering",
            "fh": "Free Hit",
            "d": "Drizzle",
            "u": "Third Umpire",
            "ba": "Ball In Air",
        }
        
        try:
            headers = {"Content-Type": "application/json"}
            if token:
                headers["Authorization"] = f"Bearer {token}"
            
            # Build payload matching CricketDataDTO exactly
            payload = {
                "url": source_url,
            }
            
            # Extract over: field 'v' contains current over like "15.3"
            if api_data.get("v"):
                try:
                    payload["over"] = float(api_data["v"])
                except (ValueError, TypeError):
                    pass
            
            # Extract current ball info: field 'B' contains ball event
            # Special codes: ^2=Caught, ^4=Run Out, B=Ball Start, wd=Wide, etc.
            if api_data.get("B"):
                raw_b = str(api_data["B"])
                
                if raw_b in SPECIAL_CODES:
                    payload["score_update"] = SPECIAL_CODES[raw_b]
                    payload["current_ball"] = SPECIAL_CODES[raw_b]
                elif raw_b.lower() in SPECIAL_CODES:
                    payload["score_update"] = SPECIAL_CODES[raw_b.lower()]
                    payload["current_ball"] = SPECIAL_CODES[raw_b.lower()]
                else:
                    # Clean up the value (remove '^' prefix)
                    clean_b = raw_b.replace('^', '')
                    payload["score_update"] = clean_b
                    payload["current_ball"] = clean_b
                    
                    # Try to extract runs if numeric
                    if clean_b.isdigit():
                        payload["runs_on_ball"] = int(clean_b)
            
            # Extract runs from 'A' field as fallback
            if "runs_on_ball" not in payload and api_data.get("A"):
                ball_val = api_data["A"]
                if isinstance(ball_val, int):
                    payload["runs_on_ball"] = ball_val
                elif str(ball_val) in ('0', '1', '2', '3', '4', '5', '6'):
                    payload["runs_on_ball"] = int(ball_val)
            
            # Extract team odds: field 'R' contains "back+diff" format e.g. "65+2"
            # Also decode favorite team name for team_odds.favTeam
            fav_team_code = None
            fav_team_name = None
            if api_data.get("F"):
                fav_team_code = str(api_data["F"]).replace("^", "").strip()
                fav_team_name = fav_team_code  # Default to code
                
                # Try to decode team name from localStorage cache
                if local_storage and fav_team_code:
                    team_key = f"t_{fav_team_code}_name"
                    if team_key in local_storage:
                        fav_team_name = local_storage[team_key]
                        logger.debug(f"Decoded team {fav_team_code} -> {fav_team_name}")
            
            if api_data.get("R"):
                r_val = str(api_data["R"])
                back_odds = "0"
                lay_odds = "0"
                
                if "+" in r_val:
                    parts = r_val.split("+")
                    back_odds = parts[0]
                    try:
                        lay_odds = str(int(back_odds) + int(parts[1]))
                    except (ValueError, IndexError):
                        lay_odds = back_odds
                else:
                    back_odds = r_val
                    lay_odds = r_val
                
                payload["team_odds"] = {
                    "backOdds": back_odds,
                    "layOdds": lay_odds,
                    "favTeam": fav_team_name or fav_team_code or "",
                }
            
            # Set fav_team at root level too
            if fav_team_name:
                payload["fav_team"] = fav_team_name
            
            # Extract current score from rb (recent balls) - last object has current over
            # rb[-1] contains: bt=batting team code, ts=total score, o=over number, b=balls array
            # o is the over being bowled (e.g., 25 means bowling 25th over)
            # b array has balls with d=delivery number (1-6)
            # Actual over = (o-1) + (last_ball_d / 10), e.g., o=25, d=5 -> 24.5
            batting_team_code = None
            current_score_str = None
            calculated_over = None
            
            rb_data = api_data.get("rb")
            if rb_data and isinstance(rb_data, list) and len(rb_data) > 0:
                # Use the LAST object - it's the current over
                last_rb = rb_data[-1]
                if isinstance(last_rb, dict):
                    batting_team_code = last_rb.get("bt")
                    current_score_str = last_rb.get("ts")  # e.g., "112/3"
                    over_number = last_rb.get("o")  # e.g., 25 (means bowling 25th over)
                    balls = last_rb.get("b", [])
                    
                    # Find the last ball bowled (highest d value that was actually bowled)
                    last_ball_delivery = 0
                    if balls and isinstance(balls, list):
                        for ball in balls:
                            if isinstance(ball, dict):
                                d = ball.get("d", 0)
                                # Check if ball was actually bowled (has some activity)
                                # u field contains the runs/result, even "0" means ball was bowled
                                if "u" in ball and d > last_ball_delivery:
                                    last_ball_delivery = d
                    
                    # Calculate actual over: (over_number - 1) + (balls / 10)
                    # o=25, d=5 -> 24.5 (24 completed + 5 balls)
                    # o=25, d=6 -> 25.0 (25 completed, over finished)
                    if over_number:
                        if last_ball_delivery == 6:
                            # Over completed
                            calculated_over = float(over_number)
                        elif last_ball_delivery > 0:
                            # Mid-over: (over-1).balls
                            calculated_over = float(over_number - 1) + (last_ball_delivery / 10.0)
                        else:
                            # No balls bowled yet in this over
                            calculated_over = float(over_number - 1) if over_number > 0 else 0.0
            
            # Decode batting team name and short name from localStorage
            batting_team_name = batting_team_code or ""
            batting_team_short = batting_team_code or ""  # Default to code if short name not found
            if local_storage and batting_team_code:
                # Look up full name: t_{code}_name
                name_key = f"t_{batting_team_code}_name"
                if name_key in local_storage:
                    batting_team_name = local_storage[name_key]
                # Look up short name: t_{code}_short (e.g., "KARB", "MAS-W", "SA")
                short_key = f"t_{batting_team_code}_short"
                if short_key in local_storage:
                    batting_team_short = local_storage[short_key]
            
            # Build score object from rb data - wrap in match_update for proper backend handling
            # Backend's JacksonCustomCricketDeserializer expects match_update.score as an object
            if current_score_str:
                # Format: "112/3" -> score="112-3"
                score_display = current_score_str.replace("/", "-")
                
                # Use 'v' field first (most accurate), then calculated over from rb
                over_val = api_data.get("v")
                if over_val is None and calculated_over is not None:
                    over_val = calculated_over
                
                # Wrap in match_update so backend deserializer handles the object correctly
                # Use short name (e.g., "KARB", "MAS-W") for teamName in score
                payload["match_update"] = {
                    "score": {
                        "teamName": batting_team_short,  # Short name like "KARB", "MAS-W", "SA"
                        "score": score_display,
                        "over": str(over_val) if over_val is not None else ""
                    }
                }
                payload["batting_team"] = batting_team_name  # Full name for batting_team field
            
            # Extract session odds: fields 'D' (overs) and 'Z' (odds)
            if api_data.get("D") and api_data.get("Z"):
                d_val = str(api_data["D"])
                z_val = str(api_data["Z"])
                
                overs = d_val.split(",") if d_val else []
                odds_strs = z_val.split(",") if z_val else []
                
                session_odds = []
                for i, over in enumerate(overs):
                    if i < len(odds_strs):
                        odd_str = odds_strs[i]
                        back = "0"
                        lay = "0"
                        if "+" in odd_str:
                            parts = odd_str.split("+")
                            back = parts[0]
                            try:
                                lay = str(int(back) + int(parts[1]))
                            except (ValueError, IndexError):
                                lay = back
                        else:
                            back = odd_str
                            lay = odd_str
                        
                        session_odds.append({
                            "sessionOver": over.strip(),
                            "sessionBackOdds": back,
                            "sessionLayOdds": lay,
                        })
                
                if session_odds:
                    payload["session_odds"] = session_odds
            
            # Extract recent overs from rb field (recent balls breakdown)
            if api_data.get("rb"):
                overs_data = []
                for over_obj in api_data["rb"]:
                    if isinstance(over_obj, dict) and "b" in over_obj:
                        balls = []
                        for b in over_obj["b"]:
                            if isinstance(b, dict):
                                balls.append(str(b.get("u", "0")))
                            else:
                                balls.append(str(b))
                        overs_data.append({
                            "overNumber": str(over_obj.get("o", "")),
                            "balls": balls,
                            "totalRuns": str(over_obj.get("r", 0)),
                        })
                if overs_data:
                    payload["overs_data"] = overs_data
            
            # Log payload with key values for debugging (to debug file)
            match_update_data = payload.get("match_update", {})
            print(f"[FAST-PUSH] url={source_url}")
            print(f"[FAST-PUSH] match_update={match_update_data}")
            print(f"[FAST-PUSH] team_odds={payload.get('team_odds')}")
            print(f"[FAST-PUSH] fav_team={payload.get('fav_team')}")
            print(f"[FAST-PUSH] batting_team={payload.get('batting_team')}")
            print(f"[FAST-PUSH] over={payload.get('over')}")
            print(f"[FAST-PUSH] score_update={payload.get('score_update')}")
            
            logger.debug("matches.push_immediate.payload", metadata={
                "url": source_url, 
                "fields": list(payload.keys()),
                "fav_team": payload.get("fav_team"),
                "match_update": match_update_data,
                "team_odds": payload.get("team_odds"),
                "score_update": payload.get("score_update"),
                "over": payload.get("over"),
                "batting_team": payload.get("batting_team"),
            })
            
            response = requests.post(service_url, json=payload, headers=headers, timeout=2.0)
            response.raise_for_status()
            
            # Record fast update timestamp to prevent stale regular pushes from overwriting
            _fast_update_timestamps[source_url] = time.time()
            
            elapsed = time.time() - start_time
            logger.info("matches.push_immediate.success", metadata={
                "url": source_url, 
                "elapsed_ms": elapsed * 1000,
            })
            return True
            
        except Exception as e:
            elapsed = time.time() - start_time
            logger.warning("matches.push_immediate.error", metadata={
                "error": str(e), 
                "url": source_url,
                "elapsed_ms": elapsed * 1000,
            })
            return False