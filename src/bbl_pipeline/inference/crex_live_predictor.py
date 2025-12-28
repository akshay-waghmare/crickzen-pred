"""
Crex Live Match Predictor

Uses the existing Crex scraper to get live match data and runs predictions.
Optionally outputs state to a JSON file for Streamlit integration.
"""

import asyncio
import sys
import os
import re
import json
import structlog
from pathlib import Path
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, Dict, Any, List

logger = structlog.get_logger()

# Add scraper to path
SCRAPER_PATH = Path(__file__).parent.parent.parent.parent.parent / "scraper" / "crex_scraper_python"
sys.path.insert(0, str(SCRAPER_PATH))

from playwright.async_api import async_playwright, BrowserContext, Page


@dataclass
class BallData:
    """Data for a single ball delivery."""
    ball_number: str  # e.g., "8.3"
    over_number: int
    ball_in_over: int
    runs: int
    is_wicket: bool
    is_dot: bool
    is_boundary: bool
    is_six: bool
    extras: int
    extras_type: Optional[str]
    commentary: str
    batsman_name: str
    bowler_name: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass  
class MatchState:
    """Current match state for predictions."""
    batting_team: str = ""
    bowling_team: str = ""
    total_runs: int = 0
    wickets: int = 0
    overs: float = 0.0
    current_run_rate: float = 0.0
    required_run_rate: float = 0.0
    target: Optional[int] = None
    is_second_innings: bool = False
    batsman1_name: str = ""
    batsman1_runs: int = 0
    batsman1_balls: int = 0
    batsman2_name: str = ""
    batsman2_runs: int = 0
    batsman2_balls: int = 0
    bowler1_name: str = ""
    bowler1_overs: float = 0.0
    bowler1_runs: int = 0
    bowler1_wickets: int = 0
    venue: str = ""
    toss_winner: str = ""
    toss_decision: str = ""
    balls_data: List[BallData] = field(default_factory=list)


class CrexLivePredictor:
    """
    Live match predictor using Crex scraper data.
    Optionally writes state to JSON for Streamlit integration.
    """
    
    def __init__(self, match_url: str, model_dir: str, headless: bool = True,
                 feature_store_dir: str = None, output_json: str = None,
                 live_match_json: str = None):
        self.match_url = match_url
        self.model_dir = model_dir
        self.headless = headless
        self.feature_store_dir = feature_store_dir
        self.output_json = output_json  # Path for JSON output (for Streamlit)
        # Optional richer debug output (defaults to sibling livematch.json if output_json is set)
        if live_match_json is None and output_json:
            try:
                live_match_json = str(Path(output_json).with_name("livematch.json"))
            except Exception:
                live_match_json = None
        self.live_match_json = live_match_json
        self.browser = None
        self.page = None
        self.match_state = MatchState()
        self.last_ball_number = ""
        self._running = False
        self._first_prediction = True  # Debug flag for first prediction
        self._prediction_history = []  # Track predictions over time
        
        # Try to load the prediction model
        self.model = None
        self._load_model()
    
    def _load_model(self):
        """Load the trained prediction model."""
        try:
            from bbl_pipeline.inference.predictor import Predictor
            self.predictor = Predictor.load(self.model_dir, self.feature_store_dir)
            self.model = self.predictor.model
            print(f"✅ Model loaded from {self.model_dir}")
            if self.feature_store_dir:
                print(f"📊 Feature store: {self.feature_store_dir}")
        except Exception as e:
            print(f"⚠️ Could not load model: {e}")
            print("   Will run in scraper-only mode (no predictions)")
            self.predictor = None
    
    def _get_info_url(self) -> str:
        """Convert live URL to info URL."""
        return self.match_url.replace("/live", "/info")
    
    async def _fetch_match_info_page(self):
        """Fetch additional match info from the info page (toss, venue, etc)."""
        try:
            info_url = self._get_info_url()
            print(f"📋 Fetching match info from: {info_url}")
            
            # Navigate to info page briefly
            await self.page.goto(info_url, timeout=30000)
            await asyncio.sleep(2)
            
            # Extract toss info - look for "opt to Bat" or "opt to Bowl"
            page_text = await self.page.inner_text("body")
            
            # Parse toss decision - match team abbreviations like PRS-W, SYS-W
            import re
            toss_match = re.search(r'([A-Z0-9\-]+)\s+opt\s+to\s+(Bat|Bowl)', page_text, re.IGNORECASE)
            if toss_match:
                self.match_state.toss_winner = toss_match.group(1)
                self.match_state.toss_decision = toss_match.group(2).lower()
                print(f"🪙 Toss: {self.match_state.toss_winner} won, elected to {self.match_state.toss_decision}")
            
            # Extract venue - look for known cricket venue patterns
            # Be specific to avoid capturing random text
            venue_patterns = [
                r'Venue\s*[:\-]?\s*([\w\s]+(?:Stadium|Oval|Ground|Arena|Park))',  # "Venue: North Sydney Oval"
                # SA20 venues
                r'(Kingsmead[\w\s,]*)',  # Durban
                r'(Newlands[\w\s,]*)',   # Cape Town
                r'(Boland Park[\w\s,]*)', # Paarl
                r"(St George's Park[\w\s,]*)",  # Gqeberha
                r'(SuperSport Park[\w\s,]*)',  # Centurion
                r'(Wanderers[\w\s,]*)',  # Johannesburg
                r'(Durban[\w\s]+Stadium)',
                r'(Hollywoodbets[\w\s]+)',
                # Australian venues
                r'(Simonds Stadium)',  # Specific pattern for Simonds Stadium
                r'(Kardinia Park)',
                r'(GMHBA Stadium)',
                r'(North Sydney Oval)',
                r'(Sydney Showground Stadium)',
                r'(Adelaide Oval)',
                r'(The Gabba|Brisbane Cricket Ground)',
                r'(MCG|Melbourne Cricket Ground)',
                r'(SCG|Sydney Cricket Ground)',
                r'(WACA|Perth Stadium|Optus Stadium)',
                r'(Bellerive Oval|Blundstone Arena)',
                r'(Manuka Oval)',
                r'(Junction Oval)',
                # UAE venues
                r'(Dubai International Cricket Stadium)',
                r'(Zayed Cricket Stadium[\w\s,]*)',
                r'(Sharjah Cricket Stadium)',
                # Generic patterns (last)
                r'([\w\s]+Cricket Ground)',
                r'([\w\s]+Cricket Stadium)',
                r'([\w\s]+Stadium)',
                r'([\w\s]+Oval)',
            ]
            for pattern in venue_patterns:
                venue_match = re.search(pattern, page_text, re.IGNORECASE)
                if venue_match:
                    venue = venue_match.group(1).strip()
                    # Clean up venue - remove any newlines or extra whitespace
                    venue = ' '.join(venue.split())
                    # Remove time prefixes like "45 PM" or date info
                    venue = re.sub(r'^\d+\s*(?:AM|PM)\s+', '', venue, flags=re.IGNORECASE)
                    # Remove common trailing words that get captured
                    venue = re.sub(r'\s+(Team Form|Match Info|Live|Scorecard|Commentary).*$', '', venue, flags=re.IGNORECASE)
                    # Clean trailing commas or spaces
                    venue = venue.rstrip(', ')
                    if len(venue) > 5 and len(venue) < 60:  # Reasonable venue name length
                        self.match_state.venue = venue
                        logger.info(f"Extracted venue from page: '{venue}'")
                        print(f"🏟️ Venue: {self.match_state.venue}")
                        break
            
            # Extract teams from info page - store both teams, we'll figure out batting/bowling from title
            vs_match = re.search(r'([A-Z0-9\-]+)\s+vs\s+([A-Z0-9\-]+)', page_text)
            if vs_match:
                team1, team2 = vs_match.group(1), vs_match.group(2)
                # Store as team1 and team2 initially - batting will be set from title later
                self._team1 = team1
                self._team2 = team2
                print(f"📍 Teams: {team1} vs {team2}")
            
            # Navigate back to live page
            await self.page.goto(self.match_url, timeout=30000)
            await asyncio.sleep(3)
            
        except Exception as e:
            print(f"⚠️ Could not fetch info page: {e}")
            # Still try to go to live page
            try:
                await self.page.goto(self.match_url, timeout=30000)
                await asyncio.sleep(3)
            except:
                pass
    
    async def start(self):
        """Start the browser and navigate to match."""
        print(f"🏏 Starting Crex Live Predictor")
        print(f"   Match URL: {self.match_url}")
        
        playwright = await async_playwright().start()
        
        self.browser = await playwright.chromium.launch(headless=self.headless)
        context = await self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080},
        )
        
        self.page = await context.new_page()
        
        # Setup network interception for API data
        self.api_data = {}
        self.page.on("response", self._handle_response)
        
        # First fetch info page for toss, venue, etc.
        print(f"🌐 Opening info page first...")
        await self._fetch_match_info_page()
        
        # Wait for page title to include score (retry up to 10 times)
        for _ in range(10):
            title = await self.page.title()
            if re.match(r'^(\w+)\s+(\d+)[-/](\d+)\s+\(', title):
                break
            await asyncio.sleep(1)
        
        print(f"✅ Page loaded: {title}")
        
        # Extract initial match info from live page
        await self._extract_match_info()
        
        return True
    
    async def _handle_response(self, response):
        """Handle network responses to capture API data."""
        try:
            if "sV3" in response.url:
                data = await response.json()
                self.api_data = data
                self._process_api_data(data)
        except Exception:
            pass
    
    def _process_api_data(self, data: Dict[str, Any]):
        """Process sV3 API data into match state."""
        try:
            # Current ball info (field B)
            if "B" in data:
                raw_b = str(data["B"])
                self.match_state.current_ball = raw_b
            
            # Extract overs data from rb field
            rb_field = data.get("rb") or data.get("rbl")
            if rb_field and isinstance(rb_field, list):
                for over_obj in rb_field:
                    if not isinstance(over_obj, dict):
                        continue
                    
                    o_num = over_obj.get("o", 0)
                    balls_data = over_obj.get("b", [])
                    
                    for i, b_obj in enumerate(balls_data):
                        ball_num = f"{o_num}.{i+1}"
                        
                        if isinstance(b_obj, dict):
                            u_val = str(b_obj.get("u", "0"))
                            # Also check for explicit wicket field
                            has_wicket_field = b_obj.get("w") == 1 or b_obj.get("wicket") == 1
                        else:
                            u_val = str(b_obj)
                            has_wicket_field = False
                        
                        # Parse runs
                        runs = 0
                        # Detect wicket from multiple formats: W, w, OUT, or explicit wicket field
                        # Be careful NOT to match "WD" (wide) or "1W" (runs + wide) as wickets
                        u_upper = u_val.upper()
                        is_wide = "WD" in u_upper or u_upper.endswith("W") and u_upper != "W"  # e.g. "1W" = 1 wide
                        is_wicket = (u_upper in ("W", "OUT") or has_wicket_field) and not is_wide
                        is_dot = u_val == "0"
                        is_boundary = u_val == "4"
                        is_six = u_val == "6"
                        
                        if u_val.isdigit():
                            runs = int(u_val)
                        
                        ball = BallData(
                            ball_number=ball_num,
                            over_number=o_num,
                            ball_in_over=i+1,
                            runs=runs,
                            is_wicket=is_wicket,
                            is_dot=is_dot,
                            is_boundary=is_boundary,
                            is_six=is_six,
                            extras=0,
                            extras_type=None,
                            commentary="",
                            batsman_name="",
                            bowler_name=""
                        )
                        
                        # Add to balls data if new
                        if not any(b.ball_number == ball_num for b in self.match_state.balls_data):
                            self.match_state.balls_data.append(ball)
                            
        except Exception as e:
            print(f"⚠️ Error processing API data: {e}")
    
    async def _extract_match_info(self):
        """Extract match information from DOM using Crex selectors."""
        try:
            # PRIMARY: Extract from page title (most reliable - Crex always updates title)
            title = await self.page.title()
            # Title format: "PRS-W 66-1 (7.2) (Sophie Devine 0(0), Beth Mooney 22(14)) vs Sydney..."
            # Extract score first
            title_match = re.match(r'^([A-Z0-9\-]+)\s+(\d+)[-/](\d+)\s+\((\d+\.?\d*)\)', title)
            if title_match:
                current_batting_team = title_match.group(1)
                self.match_state.total_runs = int(title_match.group(2))
                self.match_state.wickets = int(title_match.group(3))
                self.match_state.overs = float(title_match.group(4))
                
                # If batting team changed, update bowling team accordingly
                if self.match_state.batting_team and self.match_state.batting_team != current_batting_team:
                    # The current batting was the previous bowling
                    self.match_state.bowling_team = self.match_state.batting_team
                elif not self.match_state.bowling_team:
                    # First time setting teams - use info page teams if available
                    if hasattr(self, '_team1') and hasattr(self, '_team2'):
                        self.match_state.bowling_team = self._team2 if current_batting_team == self._team1 else self._team1
                
                self.match_state.batting_team = current_batting_team
            else:
                # Fallback: If match hasn't started, use teams from info page
                if hasattr(self, '_team1') and hasattr(self, '_team2'):
                    self.match_state.batting_team = self._team1
                    self.match_state.bowling_team = self._team2
                else:
                    # Try to extract from title "ADKR vs GG"
                    vs_match = re.search(r'([A-Z0-9\-]+)\s+vs\s+([A-Z0-9\-]+)', title)
                    if vs_match:
                        self.match_state.batting_team = vs_match.group(1)
                        self.match_state.bowling_team = vs_match.group(2)
            
            # Extract batsmen names from title: "(Sophie Devine 0(0), Beth Mooney 22(14))"
            # Pattern: Name Runs(Balls), Name Runs(Balls)
            batsmen_match = re.search(r'\)\s*\(([A-Za-z\s]+)\s+(\d+)\((\d+)\),\s*([A-Za-z\s]+)\s+(\d+)\((\d+)\)\)', title)
            if batsmen_match:
                self.match_state.batsman1_name = batsmen_match.group(1).strip()
                self.match_state.batsman1_runs = int(batsmen_match.group(2))
                self.match_state.batsman1_balls = int(batsmen_match.group(3))
                self.match_state.batsman2_name = batsmen_match.group(4).strip()
                self.match_state.batsman2_runs = int(batsmen_match.group(5))
                self.match_state.batsman2_balls = int(batsmen_match.group(6))
            
            # Get page text to detect second innings and extract data
            page_text = await self.page.inner_text("body")
            
            # Detect second innings by looking for "need X runs" or "RRR"
            needs_runs_match = re.search(r'need\s+(\d+)\s+runs?\s+(?:in|from)\s+(\d+)\s+balls?', page_text, re.IGNORECASE)
            rrr_match = re.search(r'RRR\s*:\s*([\d.]+)', page_text)
            
            # Also try to extract the first innings total from "vs Team XXX-Y" or "((overs))" pattern
            # Pattern: "vs Sydney Sixers 113-5 ((11.0))" -> target = 114
            first_innings_match = re.search(r'vs\s+[A-Za-z\s]+\s+(\d+)-\d+\s+\(\(', page_text)
            
            if needs_runs_match or rrr_match or first_innings_match:
                # Note: We do NOT clear balls_data here anymore!
                # The _build_ball_history_for_mapper function handles innings filtering
                # by detecting the innings boundary (over number reset)
                if not self.match_state.is_second_innings:
                    logger.info("Innings change detected - will filter ball history in _build_ball_history_for_mapper")
                self.match_state.is_second_innings = True
                
                # Set target from "need X runs" if available
                if needs_runs_match:
                    runs_needed = int(needs_runs_match.group(1))
                    # Target = current_score + runs_needed
                    self.match_state.target = self.match_state.total_runs + runs_needed
                # Otherwise, set target from first innings score (if not already set)
                elif first_innings_match and self.match_state.target is None:
                    first_innings_score = int(first_innings_match.group(1))
                    self.match_state.target = first_innings_score + 1  # Target = first innings + 1
                    logger.info(f"Set target from first innings score: {first_innings_score} + 1 = {self.match_state.target}")
                    
                if rrr_match:
                    self.match_state.required_run_rate = float(rrr_match.group(1))
            
            # Extract bowling team from page text if not already set
            if not self.match_state.bowling_team or self.match_state.bowling_team == self.match_state.batting_team:
                # First try using stored teams from info page
                if hasattr(self, '_team1') and hasattr(self, '_team2'):
                    if self.match_state.batting_team == self._team1:
                        self.match_state.bowling_team = self._team2
                    elif self.match_state.batting_team == self._team2:
                        self.match_state.bowling_team = self._team1
                
                # If still not set, look for "vs TEAM" pattern - "PRS-W vs SYS-W"
                if not self.match_state.bowling_team or self.match_state.bowling_team == self.match_state.batting_team:
                    vs_match = re.search(r'([A-Z0-9\-]+)\s+vs\s+([A-Z0-9\-]+)', page_text)
                    if vs_match:
                        team1 = vs_match.group(1)
                        team2 = vs_match.group(2)
                        # The batting team is from title, bowling is the other
                        if self.match_state.batting_team == team1:
                            self.match_state.bowling_team = team2
                        elif self.match_state.batting_team == team2:
                            self.match_state.bowling_team = team1
                        else:
                            # Fuzzy match - batting team might be abbreviated differently
                            if team1.startswith(self.match_state.batting_team[:3]):
                                self.match_state.bowling_team = team2
                            else:
                                self.match_state.bowling_team = team1
            
            # Calculate run rate
            if self.match_state.overs > 0:
                self.match_state.current_run_rate = round(
                    self.match_state.total_runs / self.match_state.overs, 2
                )
            
            # Extract batsman data from DOM (fallback if title parsing didn't work)
            if not self.match_state.batsman1_name or self.match_state.batsman1_name == "Unknown":
                batsman_rows = await self.page.query_selector_all(".batsman-row, .bat-bowl-row")
                for i, row in enumerate(batsman_rows[:2]):
                    name_el = await row.query_selector(".player-name, .name")
                    runs_el = await row.query_selector(".runs, .score")
                    balls_el = await row.query_selector(".balls, .ball")
                    
                    if name_el and runs_el:
                        name = await name_el.inner_text()
                        runs = await runs_el.inner_text()
                        balls = await balls_el.inner_text() if balls_el else "0"
                        
                        if i == 0:
                            self.match_state.batsman1_name = name.strip()
                            self.match_state.batsman1_runs = int(runs) if runs.isdigit() else 0
                            self.match_state.batsman1_balls = int(balls) if balls.isdigit() else 0
                        else:
                            self.match_state.batsman2_name = name.strip()
                            self.match_state.batsman2_runs = int(runs) if runs.isdigit() else 0
                            self.match_state.batsman2_balls = int(balls) if balls.isdigit() else 0
            
            # Extract bowler data from DOM
            bowler_row = await self.page.query_selector(".bowler-row, .bowl-row")
            if bowler_row:
                name_el = await bowler_row.query_selector(".player-name, .name")
                overs_el = await bowler_row.query_selector(".overs, .over")
                runs_el = await bowler_row.query_selector(".runs, .score")
                wickets_el = await bowler_row.query_selector(".wickets, .wkt")
                
                if name_el:
                    self.match_state.bowler1_name = (await name_el.inner_text()).strip()
                if overs_el:
                    overs_text = await overs_el.inner_text()
                    try:
                        self.match_state.bowler1_overs = float(overs_text)
                    except:
                        pass
                if runs_el:
                    runs_text = await runs_el.inner_text()
                    try:
                        self.match_state.bowler1_runs = int(runs_text)
                    except:
                        pass
                if wickets_el:
                    wickets_text = await wickets_el.inner_text()
                    try:
                        self.match_state.bowler1_wickets = int(wickets_text)
                    except:
                        pass
            
            # Fallback: Try to extract bowler from page text patterns
            if not self.match_state.bowler1_name or self.match_state.bowler1_name == "Unknown":
                # Look for bowling figure pattern: "Player Name 1-0-8-0" (overs-maidens-runs-wickets)
                bowler_match = re.search(r'([A-Za-z\s]+)\s+(\d+)-(\d+)-(\d+)-(\d+)', page_text)
                if bowler_match:
                    self.match_state.bowler1_name = bowler_match.group(1).strip()
                        
        except Exception as e:
            print(f"⚠️ Error extracting match info: {e}")
    
    async def poll_and_predict(self) -> Optional[float]:
        """Poll for updates and run prediction."""
        if not self.page:
            return None
        
        try:
            # Refresh match state from DOM
            await self._extract_match_info()
            
            # Run prediction if model is loaded
            if self.model:
                win_prob = self._run_prediction()
                return win_prob
            
            return None
            
        except Exception as e:
            print(f"⚠️ Error in poll_and_predict: {e}")
            return None
    
    def _check_match_result(self) -> Optional[float]:
        """
        Check if match is definitively over and return final probability.
        Returns:
            1.0 if batting team won
            0.0 if bowling team won
            None if match still in progress
        """
        state = self.match_state
        
        # Second innings scenarios
        if state.is_second_innings and state.target:
            # Batting team won - scored enough runs
            if state.total_runs >= state.target:
                return 1.0
            
            # Bowling team won - innings complete and target not reached
            # All out (10 wickets) or all overs bowled (20 overs)
            if state.wickets >= 10:
                return 0.0
            if state.overs >= 20.0:
                return 0.0
            
            # Match tied - score equals target-1 at end of innings
            # (This is rare but handle it)
            
        # First innings - can't determine winner yet
        # (unless all out or 20 overs, but that just ends the innings)
        
        return None  # Match still in progress
    
    def _run_prediction(self) -> Optional[float]:
        """Run the prediction model on current match state."""
        try:
            # First check if match has a definitive result
            final_result = self._check_match_result()
            if final_result is not None:
                return final_result
            
            from bbl_pipeline.inference.schema import MatchState as PredictorMatchState
            
            # Parse overs into over and ball
            overs_float = self.match_state.overs
            over = int(overs_float)
            ball = int(round((overs_float - over) * 10))  # 12.3 -> 3 balls
            if ball >= 6:  # Handle edge case
                ball = 0
            
            # Build MatchState for predictor using its schema
            pred_state = PredictorMatchState(
                match_id="live_match",  # Required field
                venue=self.match_state.venue or "Unknown",
                batting_team=self.match_state.batting_team,
                bowling_team=self.match_state.bowling_team,
                innings=2 if self.match_state.is_second_innings else 1,
                over=over,
                ball=ball,
                current_score=self.match_state.total_runs,
                wickets_lost=self.match_state.wickets,
                batsman_1=self.match_state.batsman1_name or "Unknown",
                batsman_2=self.match_state.batsman2_name or "Unknown",
                bowler=self.match_state.bowler1_name or "Unknown",
                target_runs=self.match_state.target,
            )
            
            # Convert ball history to mapper format for rolling stats
            ball_history = self._build_ball_history_for_mapper()
            logger.info(f"Ball history has {len(ball_history)} balls, current state: {self.match_state.total_runs}/{self.match_state.wickets}")
            
            # Log ball history details for debugging
            if ball_history:
                logger.info(f"Ball history details: {ball_history[-3:]}")  # Last 3 balls
                # Show all wicket balls
                wicket_balls = [b for b in ball_history if b.get('is_wicket', 0) == 1]
                logger.info(f"Wicket balls in history ({len(wicket_balls)}): {wicket_balls}")
            
            # Get prediction using predictor (always show debug for visibility)
            win_prob = self.predictor.predict(
                pred_state, 
                debug=True,  # Always show debug output
                ball_history=ball_history
            )
            
            # Store the detailed probabilities for JSON output
            self.last_raw_prob = getattr(self.predictor, 'last_raw_prob', win_prob)
            self.last_smoothed_prob = getattr(self.predictor, 'last_smoothed_prob', win_prob)
            self.last_calibrated_prob = getattr(self.predictor, 'last_calibrated_prob', win_prob)
            self.last_calibrated_combined = getattr(self.predictor, 'last_calibrated_combined', win_prob)
            
            return float(win_prob)
            
        except Exception as e:
            print(f"⚠️ Prediction error: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _build_ball_history_for_mapper(self) -> list:
        """
        Convert scraped ball data to the format expected by RealTimeFeatureMapper.
        The mapper expects dicts with: runs_scored, is_wicket, is_boundary, total_score, total_wickets
        """
        history = []
        running_score = 0
        running_wickets = 0
        
        # Get balls - use original order first to detect innings boundary
        balls = list(self.match_state.balls_data)
        
        # For 2nd innings: filter to only include balls from current innings
        if self.match_state.is_second_innings and balls:
            current_overs = self.match_state.overs
            
            # SPECIAL CASE: 2nd innings just started (0/0 at 0.0 overs)
            # No balls have been bowled yet - return empty history
            if current_overs == 0 and self.match_state.total_runs == 0:
                logger.info("2nd innings just started - returning empty ball history")
                return []
            
            innings_start_idx = 0
            
            # Detection: Find where overs reset (e.g., 19.4 -> 0.1), indicating innings change
            # Look for the point where overs jump backwards significantly
            for i, ball in enumerate(balls):
                if i > 0:
                    prev_ball = balls[i - 1]
                    # If previous ball was in high overs (late 1st innings) and this ball is in low overs
                    if prev_ball.over_number >= 15 and ball.over_number <= 5:
                        innings_start_idx = i
                        logger.info(f"Detected innings boundary at index {i}: over {prev_ball.over_number} -> {ball.over_number}")
                        break
            
            # Only keep balls from current innings
            if innings_start_idx > 0:
                balls = balls[innings_start_idx:]
                logger.info(f"Filtered ball history: keeping {len(balls)} balls from 2nd innings")
            else:
                # No innings boundary found - check if all balls are from 1st innings
                # If all balls have high over numbers and we're early in 2nd innings, clear history
                if balls and current_overs <= 2:
                    max_over_in_history = max(b.over_number for b in balls)
                    if max_over_in_history >= 15:
                        logger.info(f"2nd innings early but ball history shows 1st innings (max over {max_over_in_history}) - clearing")
                        balls = []
        
        # Now sort the filtered balls by over/ball
        sorted_balls = sorted(balls, key=lambda b: (b.over_number, b.ball_in_over))
        
        for ball in sorted_balls:
            running_score += ball.runs
            if ball.is_wicket:
                running_wickets += 1
            
            history.append({
                'innings_num': 2 if self.match_state.is_second_innings else 1,
                'over_number': ball.over_number,
                'ball_number': ball.ball_in_over,
                'runs_scored': ball.runs,
                'is_wicket': 1 if ball.is_wicket else 0,
                'is_boundary': 1 if ball.is_boundary or ball.is_six else 0,
                'total_score': running_score,
                'total_wickets': running_wickets,
            })
        
        # CRITICAL: Sync with actual match state if there's a mismatch
        # The scraped ball-by-ball data may miss some events
        actual_wickets = self.match_state.wickets
        actual_score = self.match_state.total_runs
        
        if history:
            # Always sync the totals to match reality
            history[-1]['total_score'] = actual_score
            history[-1]['total_wickets'] = actual_wickets
            
            # DON'T retroactively mark balls as wickets - this creates false rolling stats
            # If ball history is incomplete, accept that and let rolling stats reflect
            # only the wickets we actually have data for
            if running_wickets != actual_wickets or running_score != actual_score:
                logger.warning(
                    f"Ball history mismatch: running={running_score}/{running_wickets}, "
                    f"actual={actual_score}/{actual_wickets}. "
                    f"History has {len(history)} balls (may be incomplete from scraper)"
                )
        
        return history
    
    def _build_features(self) -> Optional[Dict[str, Any]]:
        """Build feature dictionary from match state for model input."""
        try:
            # Calculate derived features
            total_balls = int(self.match_state.overs) * 6 + int((self.match_state.overs % 1) * 10)
            balls_remaining = 120 - total_balls  # T20 = 120 balls
            
            # Determine phase
            if self.match_state.overs <= 6:
                phase = 1  # Powerplay
            elif self.match_state.overs <= 15:
                phase = 2  # Middle overs
            else:
                phase = 3  # Death overs
            
            features = {
                'total_runs': self.match_state.total_runs,
                'wickets': self.match_state.wickets,
                'overs': self.match_state.overs,
                'balls_remaining': balls_remaining,
                'current_run_rate': self.match_state.current_run_rate,
                'required_run_rate': self.match_state.required_run_rate,
                'phase': phase,
                'is_second_innings': int(self.match_state.is_second_innings),
                'batsman1_runs': self.match_state.batsman1_runs,
                'batsman1_balls': self.match_state.batsman1_balls,
                'batsman1_sr': (self.match_state.batsman1_runs / self.match_state.batsman1_balls * 100) if self.match_state.batsman1_balls > 0 else 0,
                'batsman2_runs': self.match_state.batsman2_runs,
                'batsman2_balls': self.match_state.batsman2_balls,
                'batsman2_sr': (self.match_state.batsman2_runs / self.match_state.batsman2_balls * 100) if self.match_state.batsman2_balls > 0 else 0,
                'bowler1_overs': self.match_state.bowler1_overs,
                'bowler1_runs': self.match_state.bowler1_runs,
                'bowler1_wickets': self.match_state.bowler1_wickets,
                'bowler1_economy': (self.match_state.bowler1_runs / self.match_state.bowler1_overs) if self.match_state.bowler1_overs > 0 else 0,
            }
            
            # Add target-related features for 2nd innings
            if self.match_state.is_second_innings and self.match_state.target:
                features['target'] = self.match_state.target
                features['runs_required'] = self.match_state.target - self.match_state.total_runs
                features['required_run_rate'] = features['runs_required'] / (balls_remaining / 6) if balls_remaining > 0 else 0
            
            return features
            
        except Exception as e:
            print(f"⚠️ Error building features: {e}")
            return None
    
    async def run(self, poll_interval: float = 2.0):
        """Run the live predictor continuously."""
        self._running = True
        
        started = await self.start()
        if not started:
            print("❌ Failed to start predictor")
            return
        
        print("\n" + "="*60)
        print("🏏 LIVE MATCH PREDICTION")
        print("="*60)
        print(f"   {self.match_state.batting_team} vs {self.match_state.bowling_team}")
        if self.match_state.venue:
            print(f"   📍 {self.match_state.venue}")
        print("="*60)
        print("\n⏳ Monitoring match... Press Ctrl+C to stop\n")
        
        try:
            while self._running:
                # Poll and predict
                win_prob = await self.poll_and_predict()
                
                # Display current state
                self._display_state(win_prob)
                
                await asyncio.sleep(poll_interval)
                
        except asyncio.CancelledError:
            print("\n✋ Predictor stopped")
        except KeyboardInterrupt:
            print("\n✋ Stopped by user")
        finally:
            await self.stop()
    
    def _display_state(self, win_prob: Optional[float]):
        """Display current match state and prediction."""
        state = self.match_state
        
        # Build display line
        display = f"\r📊 {state.batting_team}: {state.total_runs}/{state.wickets} ({state.overs} ov)"
        
        if state.is_second_innings and state.target:
            runs_needed = state.target - state.total_runs
            display += f" | Need: {runs_needed}"
        else:
            display += f" | CRR: {state.current_run_rate}"
        
        if win_prob is not None:
            bar_len = 20
            filled = int(win_prob * bar_len)
            bar = "█" * filled + "░" * (bar_len - filled)
            # Show both teams' probabilities
            bowling_prob = 1 - win_prob
            display += f" | {state.batting_team}: {win_prob*100:.1f}% [{bar}] {state.bowling_team}: {bowling_prob*100:.1f}%"
            
            # Track prediction history
            self._prediction_history.append({
                "overs": state.overs,
                "bat_prob": win_prob,
                "bowl_prob": bowling_prob,
                "score": state.total_runs,
                "wickets": state.wickets,
                "timestamp": datetime.now().isoformat()
            })
            
            # Write to JSON if output file specified
            if self.output_json:
                self._write_json_state(win_prob)
        
        # Pad and print
        print(display.ljust(120), end="", flush=True)
    
    def _write_json_state(self, win_prob: float):
        """Write current state to JSON file for Streamlit."""
        try:
            state = self.match_state

            over = int(state.overs)
            ball = int(round((state.overs - over) * 10))
            if ball >= 6:
                ball = 0

            # Get features if predictor is available
            pred_state = None
            scraped_data = None
            ball_history = None
            features = {}
            if self.predictor:
                try:
                    from bbl_pipeline.inference.schema import MatchState as PredictorMatchState

                    pred_state = PredictorMatchState(
                        match_id="live_match",
                        venue=state.venue or "Unknown",
                        batting_team=state.batting_team,
                        bowling_team=state.bowling_team,
                        innings=2 if state.is_second_innings else 1,
                        over=over,
                        ball=ball,
                        current_score=state.total_runs,
                        wickets_lost=state.wickets,
                        batsman_1=state.batsman1_name or "Unknown",
                        batsman_2=state.batsman2_name or "Unknown",
                        bowler=state.bowler1_name or "Unknown",
                        target_runs=state.target,
                    )

                    scraped_data = {
                        'innings_num': pred_state.innings,
                        'over_number': over,
                        'ball_number': ball,
                        'total_score': state.total_runs,
                        'total_wickets': state.wickets,
                        'current_batsman': state.batsman1_name,
                        'non_striker': state.batsman2_name,
                        'batting_team': state.batting_team,
                        'bowling_team': state.bowling_team,
                        'venue': state.venue,
                        'target_score': state.target,
                        'runs_needed': (state.target - state.total_runs) if state.target else 0
                    }
                    ball_history = self._build_ball_history_for_mapper()

                    feat_df = self.predictor.feature_mapper.create_feature_dataframe(scraped_data)
                    features = {
                        k: (float(v) if isinstance(v, (int, float)) else str(v))
                        for k, v in feat_df.iloc[0].to_dict().items()
                    }
                except Exception:
                    pass
            
            output = {
                "timestamp": datetime.now().isoformat(),
                "match_url": self.match_url,
                "model_dir": self.model_dir,
                "feature_store_dir": self.feature_store_dir,
                "batting_team": state.batting_team,
                "bowling_team": state.bowling_team,
                "score": state.total_runs,
                "wickets": state.wickets,
                "overs": state.overs,
                "over": over,
                "ball": ball,
                "target": state.target,
                "is_second_innings": state.is_second_innings,
                "venue": state.venue,
                "batsman1_name": state.batsman1_name,
                "batsman1_runs": state.batsman1_runs,
                "batsman1_balls": state.batsman1_balls,
                "batsman2_name": state.batsman2_name,
                "batsman2_runs": state.batsman2_runs,
                "batsman2_balls": state.batsman2_balls,
                "current_run_rate": state.current_run_rate,
                "required_run_rate": state.required_run_rate,
                "bat_win_prob": win_prob,
                "bowl_win_prob": 1 - win_prob,
                "raw_win_prob": getattr(self, 'last_raw_prob', win_prob),
                "smoothed_win_prob": getattr(self, 'last_smoothed_prob', win_prob),
                "calibrated_combined_prob": getattr(self, 'last_calibrated_combined', win_prob),
                "calibrated_win_prob": getattr(self, 'last_calibrated_prob', win_prob),
                "features": features,
                "history": self._prediction_history[-50:]  # Last 50 data points
            }
            
            # Write atomically
            json_path = Path(self.output_json)
            tmp_path = json_path.with_suffix('.tmp')
            with open(tmp_path, 'w') as f:
                json.dump(output, f, indent=2)
            tmp_path.replace(json_path)

            if self.live_match_json:
                try:
                    from dataclasses import asdict

                    debug_payload = {
                        "timestamp": output["timestamp"],
                        "match_url": self.match_url,
                        "model_dir": self.model_dir,
                        "feature_store_dir": self.feature_store_dir,
                        "state": {
                            "batting_team": state.batting_team,
                            "bowling_team": state.bowling_team,
                            "score": state.total_runs,
                            "wickets": state.wickets,
                            "overs": state.overs,
                            "over": over,
                            "ball": ball,
                            "target": state.target,
                            "is_second_innings": state.is_second_innings,
                            "venue": state.venue,
                            "toss_winner": state.toss_winner,
                            "toss_decision": state.toss_decision,
                            "batsman1_name": state.batsman1_name,
                            "batsman1_runs": state.batsman1_runs,
                            "batsman1_balls": state.batsman1_balls,
                            "batsman2_name": state.batsman2_name,
                            "batsman2_runs": state.batsman2_runs,
                            "batsman2_balls": state.batsman2_balls,
                            "bowler1_name": state.bowler1_name,
                            "bowler1_overs": state.bowler1_overs,
                            "bowler1_runs": state.bowler1_runs,
                            "bowler1_wickets": state.bowler1_wickets,
                            "current_run_rate": state.current_run_rate,
                            "required_run_rate": state.required_run_rate,
                            "last_ball_number": self.last_ball_number,
                        },
                        "pred_state": asdict(pred_state) if pred_state else None,
                        "scraped_data": scraped_data,
                        "ball_history": ball_history,
                        "features": features,
                        "bat_win_prob": win_prob,
                        "bowl_win_prob": 1 - win_prob,
                        "history": self._prediction_history[-200:],
                        "balls_data": [asdict(b) for b in (state.balls_data or [])],
                    }

                    debug_path = Path(self.live_match_json)
                    debug_tmp = debug_path.with_suffix('.tmp')
                    with open(debug_tmp, 'w') as f:
                        json.dump(debug_payload, f, indent=2)
                    debug_tmp.replace(debug_path)
                except Exception:
                    pass
            
        except Exception as e:
            pass  # Don't interrupt the main flow
    
    async def stop(self):
        """Stop the predictor."""
        self._running = False
        if self.browser:
            try:
                await self.browser.close()
                print("\n🛑 Browser closed")
            except Exception as e:
                print(f"\n⚠️ Browser close failed (ignored): {e}")
            finally:
                self.browser = None


async def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Crex Live Match Predictor")
    parser.add_argument("--match-url", required=True, help="Crex match URL")
    parser.add_argument("--model-dir", default="models/champion_final", help="Model directory")
    parser.add_argument("--feature-store-dir", default=None, help="Feature store directory (for league-specific models)")
    parser.add_argument("--headless", action="store_true", default=True, help="Run headless")
    parser.add_argument("--poll-interval", type=float, default=2.0, help="Poll interval in seconds")
    parser.add_argument("--output-json", default=None, help="Output JSON file for Streamlit integration")
    parser.add_argument(
        "--live-match-json",
        default=None,
        help="Optional richer per-match debug JSON (defaults to sibling livematch.json when --output-json is set)",
    )
    
    args = parser.parse_args()
    
    predictor = CrexLivePredictor(
        match_url=args.match_url,
        model_dir=args.model_dir,
        headless=args.headless,
        feature_store_dir=args.feature_store_dir,
        output_json=args.output_json,
        live_match_json=args.live_match_json,
    )
    
    await predictor.run(poll_interval=args.poll_interval)


if __name__ == "__main__":
    asyncio.run(main())
