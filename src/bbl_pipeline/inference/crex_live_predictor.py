"""
Crex Live Match Predictor

Uses the existing Crex scraper to get live match data and runs predictions.
"""

import asyncio
import sys
import os
import re
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List

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
    """
    
    def __init__(self, match_url: str, model_dir: str, headless: bool = True, feature_store_dir: str = None):
        self.match_url = match_url
        self.model_dir = model_dir
        self.headless = headless
        self.feature_store_dir = feature_store_dir
        self.browser = None
        self.page = None
        self.match_state = MatchState()
        self.last_ball_number = ""
        self._running = False
        self._first_prediction = True  # Debug flag for first prediction
        
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
            
            # Parse toss decision
            import re
            toss_match = re.search(r'(\w+)\s+opt\s+to\s+(Bat|Bowl)', page_text, re.IGNORECASE)
            if toss_match:
                self.match_state.toss_winner = toss_match.group(1)
                self.match_state.toss_decision = toss_match.group(2).lower()
                print(f"🪙 Toss: {self.match_state.toss_winner} won, elected to {self.match_state.toss_decision}")
            
            # Extract venue - look for specific cricket ground names
            venue_patterns = [
                r'(Tribhuvan University International Cricket Ground[,\s]*\w*)',
                r'([\w\s]+ Cricket Ground[,\s]*[\w]*)',
                r'([\w\s]+ Stadium[,\s]*[\w]*)',
                r'([\w\s]+ Oval[,\s]*[\w]*)',
            ]
            for pattern in venue_patterns:
                venue_match = re.search(pattern, page_text)
                if venue_match:
                    self.match_state.venue = venue_match.group(1).strip()
                    print(f"🏟️ Venue: {self.match_state.venue}")
                    break
            
            # Extract team form (last 5 matches)
            # Look for patterns like "WWWWL" after team names
            form_matches = re.findall(r'([WL]{5})', page_text)
            if len(form_matches) >= 2:
                print(f"📊 Team Form - Team1: {form_matches[0]}, Team2: {form_matches[1]}")
            
            # Extract head to head (format: "KMG 2 - 2 LBL")
            h2h_match = re.search(r'(\w+)\s+(\d+)\s*-\s*(\d+)\s+(\w+)', page_text)
            if h2h_match and int(h2h_match.group(2)) <= 10 and int(h2h_match.group(3)) <= 10:
                print(f"📊 Head to Head: {h2h_match.group(1)} {h2h_match.group(2)} - {h2h_match.group(3)} {h2h_match.group(4)}")
            
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
                        else:
                            u_val = str(b_obj)
                        
                        # Parse runs
                        runs = 0
                        is_wicket = u_val.upper() == "W"
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
            # Extract from page title as fallback (most reliable)
            title = await self.page.title()
            # Title format: "LBL 16-0 (1.4)" or "LBL 16/0 (1.4)" - handle both hyphen and slash
            title_match = re.match(r'^(\w+)\s+(\d+)[-/](\d+)\s+\((\d+\.?\d*)\)', title)
            if title_match:
                self.match_state.batting_team = title_match.group(1)
                self.match_state.total_runs = int(title_match.group(2))
                self.match_state.wickets = int(title_match.group(3))
                self.match_state.overs = float(title_match.group(4))
                print(f"📊 From title: {self.match_state.batting_team} {self.match_state.total_runs}/{self.match_state.wickets} ({self.match_state.overs} ov)")
            
            # Get page text to detect second innings
            page_text = await self.page.inner_text("body")
            
            # Detect second innings by looking for "need X runs" or "RRR"
            needs_runs_match = re.search(r'need\s+(\d+)\s+runs\s+in\s+(\d+)\s+balls', page_text, re.IGNORECASE)
            rrr_match = re.search(r'RRR\s*:\s*([\d.]+)', page_text)
            
            if needs_runs_match or rrr_match:
                self.match_state.is_second_innings = True
                if needs_runs_match:
                    runs_needed = int(needs_runs_match.group(1))
                    # Target = current_score + runs_needed (need to win, so +1 implicitly)
                    self.match_state.target = self.match_state.total_runs + runs_needed
                    print(f"🎯 2nd Innings: Target = {self.match_state.target}, Need {runs_needed} more runs")
                if rrr_match:
                    self.match_state.required_run_rate = float(rrr_match.group(1))
                    print(f"📈 RRR: {self.match_state.required_run_rate}")
            
            # Extract team names from DOM
            team_els = await self.page.query_selector_all(".team-content .team-name")
            teams = []
            for el in team_els[:2]:
                name = await el.inner_text()
                teams.append(name.strip())
            
            if len(teams) >= 2:
                if not self.match_state.batting_team:
                    self.match_state.batting_team = teams[0]
                self.match_state.bowling_team = teams[1] if teams[0] == self.match_state.batting_team else teams[0]
                print(f"📍 Teams: {self.match_state.batting_team} vs {self.match_state.bowling_team}")
            
            # Extract score from .team-content .runs
            team_content = await self.page.query_selector(".team-content")
            if team_content:
                runs_span = await team_content.query_selector(".runs span:first-child")
                if runs_span:
                    runs_text = await runs_span.inner_text()
                    # Parse "63/7" format
                    match = re.match(r'(\d+)/(\d+)', runs_text)
                    if match:
                        self.match_state.total_runs = int(match.group(1))
                        self.match_state.wickets = int(match.group(2))
                        print(f"📊 Score: {self.match_state.total_runs}/{self.match_state.wickets}")
                
                overs_span = await team_content.query_selector(".runs span:nth-child(2)")
                if overs_span:
                    overs_text = await overs_span.inner_text()
                    # Parse "(12.3)" format
                    match = re.search(r'(\d+\.?\d*)', overs_text)
                    if match:
                        self.match_state.overs = float(match.group(1))
                        print(f"⏱️ Overs: {self.match_state.overs}")
            
            # Calculate run rate
            if self.match_state.overs > 0:
                self.match_state.current_run_rate = round(
                    self.match_state.total_runs / self.match_state.overs, 2
                )
            
            # Extract batsman data
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
            
            # Extract bowler data
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
    
    def _run_prediction(self) -> Optional[float]:
        """Run the prediction model on current match state."""
        try:
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
            
            # Get prediction using predictor (debug=True to see features)
            win_prob = self.predictor.predict(pred_state, debug=self._first_prediction)
            self._first_prediction = False
            
            return float(win_prob)
            
        except Exception as e:
            print(f"⚠️ Prediction error: {e}")
            import traceback
            traceback.print_exc()
            return None
    
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
        
        # Clear line and print update
        print(f"\r📊 {state.batting_team}: {state.total_runs}/{state.wickets} ({state.overs} ov) | CRR: {state.current_run_rate}", end="")
        
        if win_prob is not None:
            bar_len = 20
            filled = int(win_prob * bar_len)
            bar = "█" * filled + "░" * (bar_len - filled)
            print(f" | Win Prob: [{bar}] {win_prob*100:.1f}%", end="")
        
        print("   ", end="", flush=True)
    
    async def stop(self):
        """Stop the predictor."""
        self._running = False
        if self.browser:
            await self.browser.close()
            print("\n🛑 Browser closed")


async def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Crex Live Match Predictor")
    parser.add_argument("--match-url", required=True, help="Crex match URL")
    parser.add_argument("--model-dir", default="models/champion_final", help="Model directory")
    parser.add_argument("--feature-store-dir", default=None, help="Feature store directory (for league-specific models)")
    parser.add_argument("--headless", action="store_true", default=True, help="Run headless")
    parser.add_argument("--poll-interval", type=float, default=2.0, help="Poll interval in seconds")
    
    args = parser.parse_args()
    
    predictor = CrexLivePredictor(
        match_url=args.match_url,
        model_dir=args.model_dir,
        headless=args.headless,
        feature_store_dir=args.feature_store_dir
    )
    
    await predictor.run(poll_interval=args.poll_interval)


if __name__ == "__main__":
    asyncio.run(main())
