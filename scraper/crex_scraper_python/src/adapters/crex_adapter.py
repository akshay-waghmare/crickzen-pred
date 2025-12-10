"""
Crex Source Adapter.
"""

import logging
import asyncio
import json
import os
from typing import Callable, Dict, Any, Optional
from urllib.parse import urlparse, parse_qs
from playwright.async_api import BrowserContext, Page, Response
from bs4 import BeautifulSoup

from .base import SourceAdapter
from ..dom_match_extract import extract_match_dom_fields
from ..parsers.crex_parser import extract_match_stats_by_innings, parse_runs_and_balls, parse_batsman_stats
from ..config import get_settings
from ..cricket_data_service import CricketDataService
from ..cache import ScrapeCache

logger = logging.getLogger(__name__)

class CrexAdapter(SourceAdapter):
    """
    Adapter for scraping Crex.
    """

    def __init__(
        self,
        on_sv3_update: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        on_sc4_update: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        auth_token_provider: Optional[Callable[[], Optional[str]]] = None,
        cache: Optional[ScrapeCache] = None,
    ):
        """
        Initialize the CrexAdapter.
        
        Args:
            on_sv3_update: Callback fired immediately when sV3 data is received.
                          Signature: (match_id: str, data: dict) -> None
            on_sc4_update: Callback fired when sC4 scorecard data is received.
                          Signature: (match_id: str, data: dict) -> None
            auth_token_provider: Callback to get current auth token for immediate pushes.
                                Signature: () -> Optional[str]
            cache: ScrapeCache instance for localStorage caching (Feature 007).
        
        Feature: 007-fast-updates
        """
        super().__init__()  # Initialize base class (reliability tracker)
        self.on_sv3_update = on_sv3_update
        self.on_sc4_update = on_sc4_update
        self._auth_token_provider = auth_token_provider
        self._settings = get_settings()
        self._cache = cache

    @property
    def domain(self) -> str:
        return "crex"

    def get_canonical_id(self, raw_id: str) -> str:
        return f"crex:{raw_id}"

    def _extract_match_id_from_url(self, url: str) -> Optional[str]:
        """
        Extract match ID from Crex URL.
        
        Expected formats:
        - https://crex.com/scoreboard/WJR/1VB/37th-Match/GV/H9/kar-vs-raj-37th-match.../live
        - https://crex.live/match/1234567/live (legacy)
        
        Returns:
            Match ID string or None if not found
        """
        try:
            # New URL format: /scoreboard/{codes}/{slug}/live
            # Extract the slug (e.g., "kar-vs-raj-37th-match-...")
            if "/scoreboard/" in url:
                # Split and get the slug part before /live or /scorecard
                parts = url.split("/scoreboard/")[1].split("/")
                # The slug is typically the 6th part (0-indexed: code/code/match-num/code/code/slug)
                if len(parts) >= 6:
                    slug = parts[5].split("/")[0]  # Remove trailing /live etc
                    return f"crex:{slug}"
            
            # Legacy URL pattern: /match/{id}/...
            parts = url.split("/match/")
            if len(parts) >= 2:
                match_part = parts[1].split("/")[0]
                return self.get_canonical_id(match_part)
        except Exception as e:
            logger.warning(f"Failed to extract match_id from URL {url}: {e}")
        return None

    async def fetch_match(self, context: BrowserContext, url: str) -> Dict[str, Any]:
        """
        Fetch match data from Crex.
        
        Performance optimized (Feature 007):
        - CACHE localStorage to skip pre-fetch on subsequent scrapes (NEW)
        - Pre-fetches Scorecard/Info pages in PARALLEL if needed
        - Reduced wait times from 5s to 2s
        """
        data_store: Dict[str, Any] = {
            "sC4_stats": None,
            "api_data": {},
            "local_storage": {}
        }

        # Extract match_id early for cache key
        match_id = self._extract_match_id_from_url(url)
        
        # Try to get cached localStorage first (Feature 007: Fast updates)
        cached_ls = None
        if self._cache and match_id:
            try:
                cached_ls = await self._cache.get_local_storage(match_id)
                if cached_ls and len(cached_ls) > 5:
                    data_store["local_storage"] = cached_ls
                    logger.info(f"[FAST] Using cached localStorage ({len(cached_ls)} items) for {match_id}")
            except Exception as e:
                logger.warning(f"Failed to get cached localStorage: {e}")

        # Only pre-fetch if we don't have cached localStorage
        if "/live" in url and not cached_ls:
            scorecard_url = url.replace("/live", "/scorecard")
            info_url = url.replace("/live", "/info")
            
            async def fetch_scorecard_ls():
                try:
                    scorecard_page = await context.new_page()
                    try:
                        await scorecard_page.goto(scorecard_url, wait_until="domcontentloaded", timeout=20000)
                        await scorecard_page.wait_for_timeout(2000)  # Reduced from 5000
                        return await self._extract_local_storage(scorecard_page)
                    finally:
                        await scorecard_page.close()
                except Exception as e:
                    logger.warning(f"Failed to pre-fetch Scorecard LS: {e}")
                    return {}
            
            async def fetch_info_ls():
                try:
                    info_page = await context.new_page()
                    try:
                        await info_page.goto(info_url, wait_until="domcontentloaded", timeout=20000)
                        await info_page.wait_for_timeout(2000)  # Reduced from 5000
                        return await self._extract_local_storage(info_page)
                    finally:
                        await info_page.close()
                except Exception as e:
                    logger.warning(f"Failed to pre-fetch Info LS: {e}")
                    return {}
            
            # Run both pre-fetches in PARALLEL (saves ~5+ seconds)
            logger.info(f"Pre-fetching localStorage from Scorecard+Info in parallel for {url}")
            scorecard_ls, info_ls = await asyncio.gather(
                fetch_scorecard_ls(),
                fetch_info_ls()
            )
            data_store["local_storage"].update(scorecard_ls)
            data_store["local_storage"].update(info_ls)
            logger.info(f"Pre-fetched {len(scorecard_ls)} + {len(info_ls)} localStorage items in parallel")
            
            # Cache the localStorage for future scrapes (Feature 007)
            if self._cache and match_id and len(data_store["local_storage"]) > 5:
                try:
                    await self._cache.set_local_storage(match_id, data_store["local_storage"])
                    logger.info(f"[FAST] Cached localStorage for {match_id}")
                except Exception as e:
                    logger.warning(f"Failed to cache localStorage: {e}")

        page = await context.new_page()

        try:
            # Extract match_id from URL for callbacks
            match_id = self._extract_match_id_from_url(url)
            
            # Setup network interception with match_id and source_url for immediate push
            # Returns an event that signals when sV3 data is fully processed
            sv3_ready = await self._setup_network_interception(page, data_store, match_id, url)

            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            
            # Wait for key element to ensure dynamic content loaded
            try:
                await page.wait_for_selector(".match-header", timeout=3000)  # Reduced from 5000
            except Exception:
                pass # Proceed anyway, parser handles missing data

            # Wait for sV3 response to be fully processed
            try:
                # Wait up to 5 seconds for sV3 data (reduced from 8s after parallelization)
                await asyncio.wait_for(sv3_ready.wait(), timeout=5.0)
                logger.debug(f"[{match_id}] sV3 data ready in data_store")
                
                # Feature 007: Minimal wait for sC4 to complete in parallel
                await asyncio.sleep(0.3)  # Reduced from 0.5/2.0
            except asyncio.TimeoutError:
                logger.warning(f"Timeout waiting for sV3 response on {url}")

            # Extract localStorage
            current_ls = await self._extract_local_storage(page)
            data_store["local_storage"].update(current_ls)

            content = await page.content()
            dom_data = extract_match_dom_fields(content)
            
            # Merge data
            final_data = {**dom_data}
            final_data["source_url"] = url
            final_data["adapter"] = self.domain
            
            # Add rich data
            if data_store["sC4_stats"]:
                logger.info(f"sC4 stats present. LocalStorage items: {len(data_store['local_storage'])}")
                # Decode player names using localStorage if available
                if data_store["local_storage"]:
                     self._decode_sc4_stats(data_store["sC4_stats"], data_store["local_storage"])
                final_data["match_stats"] = data_store["sC4_stats"]
            else:
                logger.info("sC4 stats NOT present in data_store")
            
            if data_store["api_data"]:
                final_data["live_data"] = data_store["api_data"]
                # Debug: print available keys
                print(f"[OVERS-DEBUG] API data keys: {list(data_store['api_data'].keys())[:15]}")
                print(f"[OVERS-DEBUG] rb present: {'rb' in data_store['api_data']}, l present: {'l' in data_store['api_data']}")
                self._process_live_data(final_data, data_store["api_data"], data_store["local_storage"])

            # Fallback/Override: If result_box is present and indicates match end, use it
            # Or if current_ball is missing, use result_box
            # Also check 'result' field (from .final-result) as fallback
            result_text = final_data.get("result_box") or final_data.get("result", "")
            
            if result_text:
                # Check for common match end phrases
                is_match_end = any(x in result_text.lower() for x in ["won by", "won the", "draw", "tie", "abandoned", "no result"])
                
                if is_match_end:
                     final_data["current_ball"] = result_text
                     logger.info(f"Match end detected. Setting current_ball to: {result_text}")
                elif not final_data.get("current_ball"):
                     final_data["current_ball"] = result_text
                     logger.info(f"current_ball missing. Fallback to result text: {result_text}")

            # Add player/team maps from localStorage
            if data_store["local_storage"]:
                final_data["player_map"] = {k: v for k, v in data_store["local_storage"].items() if k.startswith('p_')}
                final_data["team_map"] = {k: v for k, v in data_store["local_storage"].items() if k.startswith('t_')}

            # Enrich with sC4 data if DOM extraction failed
            if (not final_data.get("batsman_data") or not final_data.get("bowler_data")) and data_store["sC4_stats"]:
                self._enrich_from_sc4(final_data, data_store["sC4_stats"], data_store["local_storage"])

            return final_data
        finally:
            await page.close()

    def _decode_sc4_stats(self, sc4_stats: Dict[str, Any], local_storage: Dict[str, str]):
        """
        Decodes player names in sC4 stats using localStorage mapping.
        Replaces player codes with names in the keys.
        """
        try:
            innings = sc4_stats.get("innings", {})
            logger.info(f"Decoding sC4 stats. LocalStorage has {len(local_storage)} items.")
            
            for inning_key, inning_data in innings.items():
                # Decode Team Name
                team_code = inning_data.get("team_code")
                if team_code:
                    team_name = local_storage.get(f"t_{team_code}_name")
                    if team_name:
                        inning_data["team_name"] = team_name
                        inning_data["teamName"] = team_name
                        inning_data["team_code"] = team_name  # Overwrite code with name for frontend compatibility
                        logger.info(f"Decoded team {team_code} -> {team_name}")
                    else:
                        logger.warning(f"Could not find name for team code: {team_code}")
                        inning_data["team_name"] = team_code

                # Decode Batsmen
                batsman_stats = inning_data.get("batsman_stats", {})
                decoded_batsmen = {}
                for code, stats in batsman_stats.items():
                    name = local_storage.get(f"p_{code}_name", code)
                    stats["player_name"] = name
                    decoded_batsmen[name] = stats
                inning_data["batsman_stats"] = decoded_batsmen
                
                # Decode Bowlers
                bowlers_stats = inning_data.get("bowlers_stats", {})
                decoded_bowlers = {}
                for code, stats in bowlers_stats.items():
                    name = local_storage.get(f"p_{code}_name", code)
                    stats["player_name"] = name
                    decoded_bowlers[name] = stats
                inning_data["bowlers_stats"] = decoded_bowlers
                
        except Exception as e:
            logger.error(f"Error decoding sC4 stats: {e}")

    def _enrich_from_sc4(self, final_data: Dict[str, Any], sc4_stats: Dict[str, Any], local_storage: Dict[str, str]):
        """
        Enrich final_data with stats from sC4 if available.
        """
        try:
            innings = sc4_stats.get("innings", {})
            if not innings:
                return

            # Determine current inning (last one)
            # Keys are like "1st_inning", "2nd_inning"
            # Sort by numeric prefix
            sorted_keys = sorted(innings.keys(), key=lambda k: int(k.split('_')[0][:-2]) if k[0].isdigit() else 0)
            if not sorted_keys:
                return
            
            current_inning_key = sorted_keys[-1]
            current_inning = innings[current_inning_key]
            
            # Map Batsman Data
            if not final_data.get("batsman_data"):
                batsman_list = []
                for code, stats in current_inning.get("batsman_stats", {}).items():
                    # Resolve name
                    name = local_storage.get(f"p_{code}_name", code)
                    
                    # Calculate SR
                    runs = int(stats.get("runs", 0))
                    balls = int(stats.get("balls_faced", 0))
                    sr = "{:.2f}".format((runs / balls) * 100) if balls > 0 else "0.00"
                    
                    batsman_list.append({
                        "name": name,
                        "score": str(runs),
                        "runs": str(runs), # Legacy support
                        "ballsFaced": str(balls),
                        "balls_faced": str(balls), # Legacy support
                        "fours": str(stats.get("fours", 0)),
                        "sixes": str(stats.get("sixes", 0)),
                        "strikeRate": sr,
                        "onStrike": stats.get("status") == "currently_batting",
                        "on_strike": stats.get("status") == "currently_batting" # Legacy support
                    })
                final_data["batsman_data"] = batsman_list
                logger.info(f"Enriched {len(batsman_list)} batsmen from sC4")

            # Map Bowler Data
            if not final_data.get("bowler_data"):
                bowler_list = []
                for code, stats in current_inning.get("bowlers_stats", {}).items():
                    # Resolve name
                    name = local_storage.get(f"p_{code}_name", code)
                    
                    # Calculate Economy
                    runs = int(stats.get("runs", 0))
                    overs = float(stats.get("overs", 0))
                    # Convert overs to balls for accurate econ
                    # 1.3 overs = 1*6 + 3 = 9 balls
                    o_int = int(overs)
                    o_dec = int(round((overs - o_int) * 10))
                    total_balls = o_int * 6 + o_dec
                    
                    econ = "{:.2f}".format((runs / total_balls) * 6) if total_balls > 0 else "0.00"
                    
                    bowler_list.append({
                        "name": name,
                        "score": str(runs),
                        "runs_conceded": str(runs), # Legacy support
                        "ballsBowled": total_balls,
                        "balls_bowled": total_balls, # Legacy support
                        "wicketsTaken": str(stats.get("wickets", 0)),
                        "wickets_taken": str(stats.get("wickets", 0)), # Legacy support
                        "economyRate": econ,
                        "dotBalls": "0",
                        "dot_balls": "0" # Legacy support
                    })
                final_data["bowler_data"] = bowler_list
                logger.info(f"Enriched {len(bowler_list)} bowlers from sC4")

        except Exception as e:
            logger.error(f"Error enriching from sC4: {e}")

    async def _extract_local_storage(self, page: Page) -> Dict[str, str]:
        try:
            return await page.evaluate("() => Object.fromEntries(Object.entries(localStorage).map(([k, v]) => [k, v]))")
        except Exception as e:
            logger.error(f"Error extracting localStorage: {e}")
            return {}

    async def _setup_network_interception(self, page: Page, data_store: Dict[str, Any], match_id: Optional[str] = None, source_url: Optional[str] = None) -> asyncio.Event:
        """
        Setup network interception for sV3 and sC4 API calls.
        
        Feature 007: Added match_id for immediate push callbacks.
        Returns an asyncio.Event that is set when sV3 data is fully processed.
        """
        sv3_ready = asyncio.Event()
        
        async def handle_response(response: Response):
            if "sV3" in response.url:
                try:
                    await self._handle_api_response(response, data_store, page, match_id, source_url)
                except Exception as e:
                    logger.error(f"Error handling API response: {e}")
                finally:
                    sv3_ready.set()

        page.on("response", handle_response)
        return sv3_ready

    async def _handle_api_response(
        self,
        response: Response,
        data_store: Dict[str, Any],
        page: Page,
        match_id: Optional[str] = None,
        source_url: Optional[str] = None,
    ):
        try:
            api_data = await response.json()
            data_store["api_data"] = api_data
            
            # Feature 007: Immediate push of sV3 data directly to backend
            # DISABLED: The immediate push sends partial data that overwrites 
            # good data in the backend. Need to fix backend to handle partial updates
            # or ensure immediate push only sends additive fields.
            # if self._settings.enable_fast_updates and self._settings.enable_immediate_push:
            #     # Get auth token for push
            #     auth_token = None
            #     if self._auth_token_provider:
            #         auth_token = self._auth_token_provider()
            #     
            #     if auth_token and source_url:
            #         try:
            #             # Push immediately in a separate thread to not block
            #             import asyncio
            #             asyncio.create_task(asyncio.to_thread(
            #                 CricketDataService.push_immediate_sv3,
            #                 api_data,
            #                 auth_token,
            #                 source_url,
            #             ))
            #             logger.info(f"[FAST] sV3 immediate push queued for {source_url}")
            #         except Exception as e:
            #             logger.error(f"[FAST] Error queuing immediate push: {e}")
            
            # Call the callback if provided (for metrics etc)
            if self._settings.enable_fast_updates and self.on_sv3_update and match_id:
                try:
                    self.on_sv3_update(match_id, api_data)
                except Exception as e:
                    logger.error(f"[{match_id}] Error in sV3 callback: {e}")
            
            # Extract key for sC4 call
            parsed_url = urlparse(response.url)
            query_params = parse_qs(parsed_url.query)
            key = query_params.get('key', [None])[0]
            
            if key:
                sc4_url = f"https://api-v1.com/v10/sC4.php?key={key}"
                headers = await response.all_headers() # Use headers from original request
                await self._trigger_sc4_call(sc4_url, headers, data_store, page, match_id)
        except Exception as e:
            logger.error(f"Error processing sV3 response: {e}")

    async def _trigger_sc4_call(
        self,
        url: str,
        headers: Dict[str, str],
        data_store: Dict[str, Any],
        page: Page,
        match_id: Optional[str] = None,
    ):
        """
        Trigger sC4 API call for scorecard data.
        
        Feature 007: Added match_id for immediate push callbacks.
        """
        try:
            # Use page.request to make the call with browser context (cookies, etc)
            response = await page.request.get(url, headers=headers)
            if response.status == 200:
                sc4_data = await response.json()
                stats = extract_match_stats_by_innings(sc4_data)
                data_store["sC4_stats"] = stats
                logger.info(f"Successfully fetched sC4 stats for {url}")
                
                # Feature 007: Immediate push of sC4 data
                if self._settings.enable_fast_updates and self.on_sc4_update and match_id:
                    try:
                        self.on_sc4_update(match_id, stats)
                        logger.debug(f"[{match_id}] sC4 immediate push completed")
                    except Exception as e:
                        logger.error(f"[{match_id}] Error in sC4 callback: {e}")
            else:
                logger.warning(f"Failed to fetch sC4 stats: {response.status}")
        except Exception as e:
            logger.error(f"Error triggering sC4 call: {e}")

    def _process_live_data(self, final_data: Dict[str, Any], api_data: Dict[str, Any], local_storage: Dict[str, str] = None):
        """
        Process raw API data (sV3) into structured fields for the backend.
        """
        try:
            # 1. Current Ball Info (Field B)
            if "B" in api_data:
                raw_b = str(api_data["B"])
                
                # Special codes mapping
                # ^2 = Caught Out, ^4 = Run Out, B = Ball Start, etc.
                special_codes = {
                    "^2": "Caught Out",
                    "^4": "Run Out",
                    "B": "Ball Start",
                    "o": "Over",
                    "bc": "Boundary Check",
                    "wd": "Wide",
                    "nb": "No Ball",
                    "w": "Wicket"
                }
                
                if raw_b in special_codes:
                    final_data["current_ball"] = special_codes[raw_b]
                    # For special events, runs are typically 0 unless specified otherwise
                    # We don't set runs_on_ball here to avoid incorrect parsing (e.g. ^2 -> 2 runs)
                elif raw_b.lower() in special_codes:
                     final_data["current_ball"] = special_codes[raw_b.lower()]
                else:
                    # Clean up the value for standard runs/text
                    # Remove '^' which seems to be a prefix for runs (e.g. "^4" -> "4")
                    clean_b_str = raw_b.replace('^', '')
                    final_data["current_ball"] = clean_b_str
                    
                    # Try to parse runs only if it wasn't a special code
                    try:
                        if clean_b_str.isdigit():
                            final_data["runs_on_ball"] = int(clean_b_str)
                    except ValueError:
                        pass

            # 2. Team Odds (Field R)
            # Format: "back+diff" e.g. "90+2" -> Back 90, Lay 92
            if "R" in api_data:
                r_val = str(api_data["R"])
                
                # Resolve Favorite Team Name
                fav_team_code = api_data.get("F", "").replace("^", "")
                fav_team_name = fav_team_code
                if local_storage:
                    # Try t_{code}_name
                    fav_team_name = local_storage.get(f"t_{fav_team_code}_name", fav_team_code)

                if "+" in r_val:
                    parts = r_val.split("+")
                    back = parts[0]
                    diff = parts[1]
                    try:
                        lay = str(int(back) + int(diff))
                        final_data["team_odds"] = {
                            "backOdds": back,
                            "layOdds": lay,
                            "favTeam": fav_team_name
                        }
                    except ValueError:
                        logger.warning(f"Failed to parse team odds: {r_val}")
                else:
                     final_data["team_odds"] = {
                            "backOdds": r_val,
                            "layOdds": r_val, # Fallback
                            "favTeam": fav_team_name
                        }

            # 3. Session Odds (Fields D and Z)
            # D: "6,10,15" (Overs)
            # Z: "45+1,78+2,110+3" (Odds)
            if "D" in api_data and "Z" in api_data:
                d_val = str(api_data["D"])
                z_val = str(api_data["Z"])
                
                overs = d_val.split(",") if d_val else []
                odds = z_val.split(",") if z_val else []
                
                session_list = []
                for i, over in enumerate(overs):
                    if i < len(odds):
                        odd_str = odds[i]
                        back = "0"
                        lay = "0"
                        if "+" in odd_str:
                            parts = odd_str.split("+")
                            back = parts[0]
                            try:
                                lay = str(int(back) + int(parts[1]))
                            except ValueError:
                                lay = back
                        else:
                            back = odd_str
                            lay = odd_str
                            
                        session_list.append({
                            "sessionOver": over,
                            "sessionBackOdds": back,
                            "sessionLayOdds": lay
                        })
                
                if session_list:
                    final_data["session_odds"] = session_list

            # 4. Overs Data (Fields rb, A, l, n, m)
            # rb: Detailed recent balls list with full ball-by-ball data
            #     Structure: [{"o": 13, "r": 6, "ts": "112/4", "b": [{"d": 1, "t": 0, "u": "1"}, ...]}]
            # A: Current over info (e.g. "1.6" -> over 1, ball 6)
            # l: Last completed over (e.g. "4:0.1.0.6.0.0" -> over 4: balls 0,1,0,6,0,0)
            # m: 2nd last over
            # n: 3rd last over
            
            # Debug logging for overs extraction
            print(f"[OVERS] API Keys (short): {[k for k in api_data.keys() if len(k) <= 3]}")
            print(f"[OVERS] rb={api_data.get('rb') is not None}, l={api_data.get('l')}, m={api_data.get('m')}, n={api_data.get('n')}")
            
            # Always try to extract from API as it is more reliable than DOM
            api_overs = []
            try:
                # Helper to parse over string "OverNum:b1.b2.b3.b4.b5.b6"
                def parse_over_str(over_str: str) -> dict:
                    """Parse l/m/n format: '4:0.1.0.6.0.0' or '3:1.0.6.W.0.1'"""
                    if not over_str or ":" not in str(over_str):
                        return None
                    try:
                        parts = str(over_str).split(":")
                        if len(parts) != 2:
                            return None
                        over_num = parts[0].strip()
                        balls_str = parts[1].strip()
                        balls = balls_str.split(".")
                        
                        total_runs = 0
                        for b in balls:
                            b_clean = b.strip().upper()
                            if b_clean.isdigit():
                                total_runs += int(b_clean)
                            elif b_clean in ['W', 'WD', 'NB', 'LB']:
                                # Wicket or extras - don't add to runs
                                pass
                            elif b_clean.startswith('WD') or b_clean.startswith('NB'):
                                # Wide or no-ball with runs: wd1, nb2
                                import re
                                nums = re.findall(r'\d+', b_clean)
                                if nums:
                                    total_runs += int(nums[0])
                        
                        return {
                            "overNumber": over_num,
                            "balls": balls,
                            "totalRuns": str(total_runs)
                        }
                    except Exception as e:
                        logger.warning(f"[OVERS] Failed to parse over string '{over_str}': {e}")
                        return None

                # Try rb field first (most detailed)
                rb_overs = []
                rb_field = api_data.get("rb") or api_data.get("rbl")
                
                if rb_field and isinstance(rb_field, list) and len(rb_field) > 0:
                    logger.info(f"[OVERS] Found rb field with {len(rb_field)} overs. Sample: {rb_field[0] if rb_field else 'N/A'}")
                    
                    for idx, over_obj in enumerate(rb_field):
                        if not isinstance(over_obj, dict):
                            continue
                            
                        # o = over number, r = runs in over, b = balls array
                        o_num = str(over_obj.get("o", ""))
                        balls_data = over_obj.get("b", [])
                        total_runs_from_api = over_obj.get("r")
                        
                        balls = []
                        calculated_runs = 0
                        
                        for b_obj in balls_data:
                            if isinstance(b_obj, dict):
                                # u = outcome: "0", "1", "4", "6", "w", "lb1", "wd", etc.
                                u_val = str(b_obj.get("u", "0"))
                            else:
                                u_val = str(b_obj)
                            
                            balls.append(u_val)
                            
                            # Calculate runs from ball outcome
                            u_clean = u_val.strip().upper()
                            if u_val.isdigit():
                                calculated_runs += int(u_val)
                            elif u_clean not in ['W']:  # Not a wicket
                                import re
                                nums = re.findall(r'\d+', u_val)
                                if nums:
                                    calculated_runs += int(nums[0])
                        
                        # Use API runs if available, otherwise calculated
                        total_runs = total_runs_from_api if total_runs_from_api is not None else calculated_runs
                        
                        if o_num:
                            rb_overs.append({
                                "overNumber": o_num,
                                "balls": balls,
                                "totalRuns": str(total_runs)
                            })
                    
                    if rb_overs:
                        logger.info(f"[OVERS] Parsed {len(rb_overs)} overs from rb: {[(o['overNumber'], o['balls']) for o in rb_overs[-2:]]}")

                # If rb is empty or missing, try l/m/n fields as fallback
                lmn_overs = []
                if not rb_overs:
                    logger.info(f"[OVERS] rb empty, trying l/m/n fallback. l={api_data.get('l')}, m={api_data.get('m')}, n={api_data.get('n')}")
                    
                    # Parse m (oldest), n (middle), l (most recent) - in chronological order
                    for field in ["m", "n", "l"]:
                        if field in api_data and api_data[field]:
                            over_data = parse_over_str(api_data[field])
                            if over_data:
                                lmn_overs.append(over_data)
                                logger.info(f"[OVERS] Parsed {field} field: over {over_data['overNumber']}, balls={over_data['balls']}")
                    
                    # Sort by over number
                    if lmn_overs:
                        lmn_overs.sort(key=lambda x: int(x['overNumber']) if x['overNumber'].isdigit() else 0)
                        logger.info(f"[OVERS] Got {len(lmn_overs)} overs from l/m/n: {[o['overNumber'] for o in lmn_overs]}")

                # Use rb overs if available, otherwise lmn fallback
                if rb_overs:
                    api_overs = rb_overs
                elif lmn_overs:
                    api_overs = lmn_overs
                else:
                    logger.warning(f"[OVERS] No overs data found. rb={api_data.get('rb')}, l={api_data.get('l')}")

            except Exception as e:
                logger.error(f"[OVERS] Failed to parse overs data: {e}", exc_info=True)

            # Use API overs if available
            if api_overs:
                final_data["overs_data"] = api_overs
                logger.info(f"[OVERS] Set {len(api_overs)} overs in final_data")

            # Log extraction results
            logger.info(f"Extracted live data: runs_on_ball={final_data.get('runs_on_ball')}, team_odds={final_data.get('team_odds')}, session_odds_count={len(final_data.get('session_odds', []))}")

        except Exception as e:
            logger.error(f"Error processing live data: {e}")

    async def discover_matches(self, context: BrowserContext) -> Dict[str, str]:
        """
        Discover matches from Crex listing page.
        """
        # Placeholder for discovery logic
        # In a real implementation, this would visit the fixtures/live page
        return {}

    async def fetch_match_info(self, context: BrowserContext, url: str) -> Dict[str, Any]:
        """
        Fetch match info (static data) from Crex info page.
        """
        page = await context.new_page()
        try:
            logger.info(f"Navigating to info URL: {url}")
            try:
                await page.goto(url, wait_until="networkidle", timeout=30000)
            except Exception:
                logger.warning(f"Networkidle timeout on {url}, proceeding with domcontentloaded")

            # Wait for key elements
            try:
                await page.wait_for_selector(".match-date, .toss-wrap, .match-header", timeout=10000)
            except Exception:
                logger.warning(f"Timeout waiting for selectors on {url}")

            # Debug info
            title = await page.title()
            logger.info(f"Info Page Title: {title}")
            
            # Use BS4 for simple fields
            content = await page.content()
            soup = BeautifulSoup(content, "html.parser")

            toss_elem = soup.select_one('.toss-wrap p')
            toss_info = toss_elem.get_text(strip=True) if toss_elem else 'No toss information'

            date_elem = soup.select_one('.match-date')
            match_date = date_elem.get_text(strip=True) if date_elem else 'No match date'

            venue_elem = soup.select_one('.match-venue')
            venue = venue_elem.get_text(strip=True) if venue_elem else 'No venue info'

            name_elem = soup.select_one('.s-name')
            match_name = name_elem.get_text(strip=True) if name_elem else 'No match name'

            # Scrape team form
            try:
                team_form = await page.evaluate('''() => {
                    const teamsData = {};
                    const teamSections = document.querySelectorAll('.format-match-exp');
                    teamSections.forEach(section => {
                        const teamId = section.id || 'Unknown Team';
                        const last_matches = [];
                        const match_cards = section.querySelectorAll('.format-card-wrap');
                        match_cards.forEach((card) => {
                            const teams = [];
                            const team_details = card.querySelectorAll('.form-team-detail');
                            team_details.forEach((teamDetail) => {
                                const teamName = teamDetail.querySelector('.team-name')?.innerText.trim() || 'Unknown';
                                const innings_scores = teamDetail.querySelectorAll('.team-score');
                                const innings_overs = teamDetail.querySelectorAll('.team-over');
                                const inningsScoresArray = Array.from(innings_scores).filter(el => el.innerText.trim() !== '&');
                                const inningsOversArray = Array.from(innings_overs).filter(el => el.innerText.trim() !== '&');
                                const scores = [];
                                inningsScoresArray.forEach((scoreElement, idx) => {
                                    scores.push({
                                        "team_score": scoreElement.innerText.trim(),
                                        "team_over": inningsOversArray[idx]?.innerText.trim() || 'N/A'
                                    });
                                });
                                teams.push({ "team_name": teamName, "innings": scores });
                            });
                            const match_info = card.querySelector('.form-match-no');
                            const match_name = match_info.querySelector('.match-name')?.innerText.trim() || 'Unknown Match';
                            const series_name = match_info.querySelector('.series-name')?.innerText.trim() || 'Unknown Series';
                            const resultElement = card.querySelector('.win.match, .loss.match, .draw.match');
                            const result = resultElement?.innerText.trim() || 'Unknown Result';
                            last_matches.push({ "match_name": match_name, "series_name": series_name, "teams": teams, "result": result });
                        });
                        teamsData[teamId] = last_matches;
                    });
                    return teamsData;
                }''')
            except Exception as e:
                logger.warning(f"Error extracting team_form: {e}")
                team_form = {}

            # Scrape team comparison
            try:
                team_comparison = await page.evaluate('''() => {
                    const team_comparison = {};
                    const team1_element = document.querySelector('.team1 .team-name');
                    const team2_element = document.querySelector('.team2 .team-name');
                    const team1_name = team1_element ? team1_element.innerText.trim() : 'Team 1';
                    const team2_name = team2_element ? team2_element.innerText.trim() : 'Team 2';
                    team_comparison[team1_name] = {};
                    team_comparison[team2_name] = {};
                    const rows = document.querySelectorAll('#table tbody tr');
                    rows.forEach(row => {
                        const cells = row.querySelectorAll('td');
                        if (cells.length >= 3) {
                            const stat_name = cells[1].innerText.trim();
                            const team1_stat = cells[0].innerText.trim();
                            const team2_stat = cells[2].innerText.trim();
                            team_comparison[team1_name][stat_name.toLowerCase().replace(' ', '_')] = team1_stat;
                            team_comparison[team2_name][stat_name.toLowerCase().replace(' ', '_')] = team2_stat;
                        }
                    });
                    return team_comparison;
                }''')
            except Exception as e:
                logger.warning(f"Error extracting team_comparison: {e}")
                team_comparison = {}

            # Scrape venue stats
            try:
                venue_stats = await page.evaluate('''() => {
                    const stats = {};
                    stats.matches = document.querySelector('.match-count')?.innerText.trim() || 'No data';
                    stats.win_bat_first = document.querySelector('.win-bat-first .match-win-per')?.innerText.trim() || 'No data';
                    stats.win_bowl_first = document.querySelector('.win-bowl-first .match-win-per')?.innerText.trim() || 'No data';
                    stats.avg_1st_inns = document.querySelector('.venue-avg-sec-inn .venue-avg-val')?.innerText.trim() || 'No data';
                    stats.avg_2nd_inns = document.querySelector('.venue-avg-wrap .venue-avg-val')?.innerText.trim() || 'No data';
                    return stats;
                }''')
            except Exception as e:
                logger.warning(f"Error extracting venue_stats: {e}")
                venue_stats = {}

            # Scrape playing XI
            playing_xi = {}
            try:
                buttons = await page.query_selector_all('.playingxi-button')
                for button in buttons:
                    team_name = await button.inner_text()
                    team_name = team_name.strip()
                    await button.click()
                    await asyncio.sleep(0.5) 
                    players = await page.evaluate('''() => {
                        const playersList = [];
                        document.querySelectorAll('.playingxi-card-row').forEach(player => {
                            const playerName = player.querySelector('.player-name')?.innerText.trim() || 'Unknown Player';
                            const playerRole = player.querySelector('.bat-ball-type')?.innerText.trim() || 'Unknown Role';
                            playersList.push({ playerName, playerRole });
                        });
                        return playersList;
                    }''')
                    playing_xi[team_name] = players
            except Exception as e:
                logger.warning(f"Error scraping playing XI: {e}")

            return {
                "match_date": match_date,
                "venue": venue,
                "match_name": match_name,
                "team_form": team_form,
                "team_comparison": team_comparison,
                "venue_stats": venue_stats,
                "playing_xi": playing_xi,
                "toss_info": toss_info
            }
        except Exception as e:
            logger.error(f"Error fetching match info: {e}")
            return {}
        finally:
            await page.close()
