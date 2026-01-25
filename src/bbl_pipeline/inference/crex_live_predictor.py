"""
Crex Live Match Predictor

Uses the existing Crex scraper to get live match data and runs predictions.
Optionally outputs state to a JSON file for Streamlit integration.
Includes Monte Carlo simulation for uncertainty quantification.
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

# Monte Carlo simulation imports
try:
    from bbl_pipeline.simulation import (
        MatchState as SimMatchState,
        simulate,
        simulate_one_over,
        simulate_two_overs,
        simulate_five_overs,
        evaluate_bet,
        BettingThresholds,
    )
    SIMULATION_AVAILABLE = True
except ImportError:
    SIMULATION_AVAILABLE = False
    logger.warning("Monte Carlo simulation module not available")

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
    # Market odds from CREX API
    market_fav_team: str = ""
    market_back_odds: str = ""
    market_lay_odds: str = ""
    market_fav_prob: float = 0.0  # Implied probability from back odds


class CrexLivePredictor:
    """
    Live match predictor using Crex scraper data.
    Optionally writes state to JSON for Streamlit integration.
    """
    
    def __init__(self, match_url: str, model_dir: str, headless: bool = True,
                 feature_store_dir: str = None, output_json: str = None,
                 live_match_json: str = None, venue: str = None, league: str = None,
                 use_ml_model: bool = False):
        self.match_url = match_url
        self.model_dir = model_dir
        self.headless = headless
        self.feature_store_dir = feature_store_dir
        self.league = league  # League code for league-specific calibration
        self.use_ml_model = use_ml_model  # Use ML model for Monte Carlo terminal evaluation
        self.output_json = output_json  # Path for JSON output (for Streamlit)
        self.venue_override = venue
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
        self.local_storage = {}  # CREX localStorage for resolving team/player codes
        
        # Persist history to separate file for Streamlit page refresh resilience
        if output_json:
            self._history_file = str(Path(output_json).with_name("prediction_history.json"))
            self._load_history()  # Load existing history on startup
        else:
            self._history_file = None
        
        # Try to load the prediction model
        self.model = None
        self._load_model()
    
    def _load_model(self):
        """Load the trained prediction model."""
        try:
            from bbl_pipeline.inference.predictor import Predictor
            self.predictor = Predictor.load(self.model_dir, self.feature_store_dir, league=self.league)
            self.model = self.predictor.model
            print(f"[OK] Model loaded from {self.model_dir}")
            if self.feature_store_dir:
                print(f"[INFO] Feature store: {self.feature_store_dir}")
            if self.league:
                print(f"[INFO] League calibrator: {self.league}")
        except Exception as e:
            print(f"[WARN] Could not load model: {e}")
            print("   Will run in scraper-only mode (no predictions)")
            self.predictor = None
    
    def _load_history(self):
        """Load prediction history from file for persistence across restarts."""
        if not self._history_file:
            return
        try:
            history_path = Path(self._history_file)
            if history_path.exists():
                with open(history_path, 'r') as f:
                    data = json.load(f)
                    # Check if history belongs to current match
                    saved_url = data.get("match_url")
                    if saved_url and saved_url != self.match_url:
                        print(f"[NEW] New match detected (URL mismatch). Clearing history.")
                        self._prediction_history = []
                        return
                        
                    self._prediction_history = data.get("history", [])
                    print(f"[HIST] Loaded {len(self._prediction_history)} history points from {self._history_file}")
        except Exception as e:
            logger.warning(f"Could not load history: {e}")
            self._prediction_history = []
    
    def _save_history(self):
        """Save prediction history to file for persistence."""
        if not self._history_file:
            return
        try:
            history_path = Path(self._history_file)
            tmp_path = history_path.with_suffix('.tmp')
            with open(tmp_path, 'w') as f:
                json.dump({
                    "match_url": self.match_url,
                    "history": self._prediction_history
                }, f)
            tmp_path.replace(history_path)
        except Exception as e:
            logger.warning(f"Could not save history: {e}")
    
    def _run_monte_carlo_simulation(self, model_prob: Optional[float] = None, use_ml_model: bool = False) -> Optional[Dict[str, Any]]:
        """
        Run Monte Carlo simulation for uncertainty quantification.
        
        Args:
            model_prob: League-calibrated model probability from predictor.predict().
                       If provided, this is used for edge calculation in betting decisions
                       (more accurate than simulation mean which uses resource_win_prob).
            use_ml_model: If True, use ML model for terminal state evaluation (slower but
                         more accurate ~400-800ms). If False, use resource_win_prob heuristic
                         (faster ~60ms but less accurate).
        
        Returns dict with simulation results or None if unavailable.
        """
        if not SIMULATION_AVAILABLE:
            return None
        
        try:
            state = self.match_state
            
            # Calculate balls remaining
            overs_float = state.overs
            balls_bowled = int(overs_float) * 6 + int(round((overs_float - int(overs_float)) * 10))
            balls_remaining = 120 - balls_bowled
            
            if balls_remaining <= 0:
                return None
            
            # Use self.league if provided, otherwise detect from model_dir
            league = self.league  # Prefer explicitly set league
            if not league:
                # Fallback: detect from model_dir
                league = "bbl"  # Default
                model_dir_lower = self.model_dir.lower()
                if "t20_international" in model_dir_lower or "t20i" in model_dir_lower:
                    league = "t20i"
                elif "sa20" in model_dir_lower or "sat_" in model_dir_lower:
                    league = "sa20"
                elif "ilt20" in model_dir_lower or "ilt_" in model_dir_lower:
                    league = "ilt20"
                elif "wpl" in model_dir_lower:
                    league = "wpl"
                elif "ssm" in model_dir_lower:
                    league = "ssm"
                elif "bpl" in model_dir_lower:
                    league = "bpl"
                elif "female" in model_dir_lower:
                    league = None  # Global female model - no specific league calibration
            
            # Create simulation state
            # Get team stats from feature store for accurate Monte Carlo
            batting_team_wr = 0.5
            bowling_team_wr = 0.5
            batting_team_sit_wr = 0.5
            bowling_team_sit_wr = 0.5
            
            if self.predictor and hasattr(self.predictor, 'feature_store'):
                fs = self.predictor.feature_store
                bat_stats = fs.get_team_stats(state.batting_team)
                bowl_stats = fs.get_team_stats(state.bowling_team)
                if bat_stats:
                    batting_team_wr = bat_stats.get('win_rate', 0.5)
                    # Use appropriate situation rate based on innings
                    if state.is_second_innings:
                        batting_team_sit_wr = bat_stats.get('bowl_first_wr', batting_team_wr)  # They batted 2nd
                    else:
                        batting_team_sit_wr = bat_stats.get('bat_first_wr', batting_team_wr)
                if bowl_stats:
                    bowling_team_wr = bowl_stats.get('win_rate', 0.5)
                    if state.is_second_innings:
                        bowling_team_sit_wr = bowl_stats.get('bat_first_wr', bowling_team_wr)  # They batted 1st
                    else:
                        bowling_team_sit_wr = bowl_stats.get('bowl_first_wr', bowling_team_wr)
            
            sim_state = SimMatchState(
                innings=2 if state.is_second_innings else 1,
                score=state.total_runs,
                wickets_lost=state.wickets,
                balls_remaining=balls_remaining,
                target_runs=state.target if state.is_second_innings else None,
                batting_team=state.batting_team,
                bowling_team=state.bowling_team,
                league=league,
                venue=state.venue,
                batting_team_win_rate=batting_team_wr,
                bowling_team_win_rate=bowling_team_wr,
                batting_team_situation_wr=batting_team_sit_wr,
                bowling_team_situation_wr=bowling_team_sit_wr,
            )
            
            # Choose predictor for ML model mode
            predictor = self.predictor if use_ml_model else None
            
            # Run 1-ball simulation (fast)
            result_1ball = simulate(sim_state, horizon=1, n_simulations=1000, predictor=predictor)
            
            # Run 6-ball (1 over) simulation
            result_6ball = simulate_one_over(sim_state, n_simulations=2000, predictor=predictor)
            
            # Run 12-ball (2 over) simulation
            result_12ball = simulate_two_overs(sim_state, n_simulations=2000, predictor=predictor)
            
            # Run 30-ball (5 over) simulation - useful for first innings uncertainty
            result_30ball = simulate_five_overs(sim_state, n_simulations=2000, predictor=predictor)
            
            # Evaluate betting decision if market odds available
            # Uses league-calibrated model_prob for edge calculation (more accurate than simulation mean)
            betting_decision = None
            if state.market_back_odds:
                try:
                    odds = float(state.market_back_odds)
                    if odds > 1.0:
                        decision = evaluate_bet(
                            simulation_result=result_6ball,
                            market_odds=odds,
                            balls_remaining=balls_remaining,
                            model_prob=model_prob,  # League-calibrated probability for edge
                        )
                        betting_decision = {
                            "decision": decision.decision.value,
                            "edge": decision.edge,
                            "kelly_stake": decision.kelly_stake,
                            "confidence": decision.confidence,
                            "phase": decision.phase,
                            "rationale": decision.rationale,
                            "model_prob": decision.model_prob,  # Include in output
                            "simulation_mean": result_6ball.mean_prob,  # Also include simulation mean for comparison
                        }
                except (ValueError, TypeError):
                    pass
            
            return {
                "available": True,
                "league": league,
                "balls_remaining": balls_remaining,
                "use_ml_model": use_ml_model,  # Indicates whether ML model was used for terminal evaluation
                "simulation_1ball": {
                    "mean_prob": result_1ball.mean_prob,
                    "std_prob": result_1ball.std_prob,
                    "p5": result_1ball.p5,
                    "p95": result_1ball.p95,
                    "n_sims": result_1ball.n_sims,
                    "time_ms": result_1ball.time_taken_ms,
                },
                "simulation_6ball": {
                    "mean_prob": result_6ball.mean_prob,
                    "std_prob": result_6ball.std_prob,
                    "p5": result_6ball.p5,
                    "p95": result_6ball.p95,
                    "n_sims": result_6ball.n_sims,
                    "time_ms": result_6ball.time_taken_ms,
                },
                "simulation_12ball": {
                    "mean_prob": result_12ball.mean_prob,
                    "std_prob": result_12ball.std_prob,
                    "p5": result_12ball.p5,
                    "p95": result_12ball.p95,
                    "n_sims": result_12ball.n_sims,
                    "time_ms": result_12ball.time_taken_ms,
                },
                "simulation_30ball": {
                    "mean_prob": result_30ball.mean_prob,
                    "std_prob": result_30ball.std_prob,
                    "p5": result_30ball.p5,
                    "p95": result_30ball.p95,
                    "n_sims": result_30ball.n_sims,
                    "time_ms": result_30ball.time_taken_ms,
                },
                "betting_decision": betting_decision,
            }
            
        except Exception as e:
            logger.warning(f"Monte Carlo simulation failed: {e}")
            return {"available": False, "error": str(e)}

    def _get_info_url(self) -> str:
        """Convert live URL to info URL."""
        return self.match_url.replace("/live", "/info")
    
    async def _extract_team_comparison(self, page_text: str, team1: str, team2: str):
        """
        Extract team comparison stats from CREX info page and inject into feature store.
        
        Example text pattern:
        Team Comparison (Last 10 matches)
        IND vs all teams NZ vs all teams
        10 Matches Played 8
        80% Win 60%
        165 Avg Score 148
        
        Note: The order of teams in the comparison table may differ from the match title!
        We need to extract team abbreviations from "XXX vs all teams" to match correctly.
        """
        try:
            import re
            
            # First, extract the team abbreviations from the comparison headers
            # Pattern: "XXX vs all teams YYY vs all teams"
            team_headers_pattern = r'([A-Z0-9\-]+)\s+vs\s+all\s+teams\s+([A-Z0-9\-]+)\s+vs\s+all\s+teams'
            team_headers_match = re.search(team_headers_pattern, page_text, re.IGNORECASE)
            
            if not team_headers_match:
                logger.warning("Could not find team comparison headers")
                return
                
            # These are the teams in the order they appear in the comparison table
            left_team = team_headers_match.group(1)
            right_team = team_headers_match.group(2)
            
            # Now extract the stats (these correspond to left and right columns)
            matches_pattern = r'(\d+)\s*Matches\s*Played\s*(\d+)'
            win_pattern = r'(\d+)%\s*Win\s*(\d+)%'
            avg_score_pattern = r'(\d+)\s*Avg\s*Score\s*(\d+)'
            
            matches_match = re.search(matches_pattern, page_text, re.IGNORECASE)
            win_match = re.search(win_pattern, page_text, re.IGNORECASE)
            avg_score_match = re.search(avg_score_pattern, page_text, re.IGNORECASE)
            
            if matches_match and win_match:
                left_matches = int(matches_match.group(1))
                right_matches = int(matches_match.group(2))
                left_win_pct = int(win_match.group(1)) / 100
                right_win_pct = int(win_match.group(2)) / 100
                left_avg_score = int(avg_score_match.group(1)) if avg_score_match else 150
                right_avg_score = int(avg_score_match.group(2)) if avg_score_match else 150
                
                # Only use if at least 2 matches played
                if left_matches >= 2:
                    print(f"[STATS] Extracted season stats for {left_team}: {left_matches} matches, {left_win_pct*100:.0f}% win rate")
                    self._inject_season_stats(left_team, left_matches, left_win_pct, left_avg_score)
                
                if right_matches >= 2:
                    print(f"[STATS] Extracted season stats for {right_team}: {right_matches} matches, {right_win_pct*100:.0f}% win rate")
                    self._inject_season_stats(right_team, right_matches, right_win_pct, right_avg_score)
                    
        except Exception as e:
            logger.warning(f"Could not extract team comparison: {e}")
    
    def _inject_season_stats(self, team_abbrev: str, matches: int, win_rate: float, avg_score: float):
        """Inject extracted season stats into the feature store's SEASON_OVERRIDES.
        
        Note: bat_first_wr and bowl_first_wr are TEAM-specific situation rates, NOT venue rates.
        We scale the team's historical situation rates by their current season win rate.
        This preserves team-specific batting/bowling first preferences.
        """
        try:
            from bbl_pipeline.features.store import InMemoryFeatureStore
            
            # Resolve full team name from abbreviation
            full_name = team_abbrev
            if team_abbrev.upper() in InMemoryFeatureStore.TEAM_ABBREVIATIONS:
                full_name = InMemoryFeatureStore.TEAM_ABBREVIATIONS[team_abbrev.upper()]
            
            # Always use team's historical situation rates scaled by current season win rate
            # This is different from venue bat_first_wr which is the same for all teams!
            bat_first_wr = None
            bowl_first_wr = None
            
            # Get feature store from predictor
            feature_store = getattr(self.predictor, 'feature_store', None) if hasattr(self, 'predictor') else None
            if feature_store and hasattr(feature_store, '_team_stats'):
                # Ensure feature store is loaded
                if not feature_store._loaded:
                    feature_store.load()
                # Get historical team stats for situation rates
                hist_team_stats = feature_store._team_stats.get(full_name)
                if hist_team_stats:
                    hist_wr = hist_team_stats.get('win_rate', 0.5)
                    hist_bat = hist_team_stats.get('bat_first_wr', hist_wr)
                    hist_bowl = hist_team_stats.get('bowl_first_wr', hist_wr)
                    
                    # Scale historical situation rates to current season win rate
                    # This preserves team's relative strength batting vs bowling first
                    # BUT CAP the ratio to prevent extreme values (max 1.15 = 15% boost)
                    if hist_wr > 0:
                        bat_first_ratio = min(1.15, max(0.85, hist_bat / hist_wr))  # Cap ratio to +/- 15%
                        bowl_first_ratio = min(1.15, max(0.85, hist_bowl / hist_wr))  # Cap ratio to +/- 15%
                        bat_first_wr = min(0.85, max(0.15, win_rate * bat_first_ratio))  # Also cap absolute value
                        bowl_first_wr = min(0.85, max(0.15, win_rate * bowl_first_ratio))
                        logger.info(f"Scaled team situation rates for '{full_name}': bat_first={bat_first_wr:.0%}, bowl_first={bowl_first_wr:.0%} (from historical ratios, capped)")
            
            # Final fallback to team's overall win rate
            if bat_first_wr is None:
                bat_first_wr = win_rate
            if bowl_first_wr is None:
                bowl_first_wr = win_rate
            
            # Update the class-level SEASON_OVERRIDES dictionary
            InMemoryFeatureStore.SEASON_OVERRIDES[full_name] = {
                'win_rate': win_rate,
                'matches': matches,
                'avg_score': avg_score,
                'bat_first_wr': bat_first_wr,
                'bowl_first_wr': bowl_first_wr,
            }
            logger.info(f"Injected season stats for '{full_name}': {matches} matches, {win_rate*100:.0f}% WR, bat_first={bat_first_wr:.0%}, bowl_first={bowl_first_wr:.0%}")
            
        except Exception as e:
            logger.warning(f"Could not inject season stats: {e}")
    
    async def _extract_venue_stats(self, page_text: str):
        """
        Extract venue stats from CREX info page.
        
        Example text pattern (multi-line, numbers may be adjacent to labels):
        Venue Stats
        31
        Matches
        Win Bat first
        55%
        Win Bowl first
        45%
        Avg 1st Inns163
        Avg 2st Inns147
        """
        try:
            import re
            from bbl_pipeline.features.store import InMemoryFeatureStore
            
            # More flexible patterns for multi-line format
            # Pattern 1: "Venue Stats\n31\nMatches" or "Venue Stats 31 Matches"
            venue_matches_pattern = r'Venue\s*Stats\s*(\d+)\s*Matches'
            
            # Pattern 2: "Win Bat first\n55%" or "Win Bat first 55%"
            bat_first_pattern = r'Win\s*Bat\s*first\s*[\n\r\s]*(\d+)\s*%'
            bowl_first_pattern = r'Win\s*Bowl\s*first\s*[\n\r\s]*(\d+)\s*%'
            
            # Pattern for avg innings scores: "Avg 1st Inns163" or "Avg 1st Inns 163"
            avg_1st_inns_pattern = r'Avg\s*1st\s*Inns\s*[\n\r\s]*(\d+)'
            avg_2nd_inns_pattern = r'Avg\s*2(?:st|nd)\s*Inns\s*[\n\r\s]*(\d+)'
            
            venue_matches = re.search(venue_matches_pattern, page_text, re.IGNORECASE)
            bat_first_match = re.search(bat_first_pattern, page_text, re.IGNORECASE)
            bowl_first_match = re.search(bowl_first_pattern, page_text, re.IGNORECASE)
            avg_1st_match = re.search(avg_1st_inns_pattern, page_text, re.IGNORECASE)
            avg_2nd_match = re.search(avg_2nd_inns_pattern, page_text, re.IGNORECASE)
            
            if bat_first_match and bowl_first_match:
                bat_first_wr = int(bat_first_match.group(1)) / 100
                bowl_first_wr = int(bowl_first_match.group(1)) / 100
                num_matches = int(venue_matches.group(1)) if venue_matches else 0
                avg_1st_inns = int(avg_1st_match.group(1)) if avg_1st_match else 160
                avg_2nd_inns = int(avg_2nd_match.group(1)) if avg_2nd_match else 150
                
                # Store venue situation stats
                InMemoryFeatureStore.VENUE_SITUATION_STATS = {
                    'bat_first_wr': bat_first_wr,
                    'bowl_first_wr': bowl_first_wr,
                    'matches': num_matches,
                    'avg_1st_inns': avg_1st_inns,
                    'avg_2nd_inns': avg_2nd_inns,
                }
                print(f"[VENUE] Extracted venue stats: {num_matches} matches, bat first WR {bat_first_wr*100:.0f}%, bowl first WR {bowl_first_wr*100:.0f}%")
                print(f"   Avg 1st innings: {avg_1st_inns}, Avg 2nd innings: {avg_2nd_inns}")
                logger.info(f"Injected venue situation stats: bat_first={bat_first_wr:.0%}, bowl_first={bowl_first_wr:.0%}, avg_1st={avg_1st_inns}, avg_2nd={avg_2nd_inns}")
                
        except Exception as e:
            logger.warning(f"Could not extract venue stats: {e}")
    
    async def _fetch_match_info_page(self):
        """Fetch additional match info from the info page (toss, venue, etc)."""
        try:
            info_url = self._get_info_url()
            print(f"[FETCH] Fetching match info from: {info_url}")
            
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
                print(f"[TOSS] Toss: {self.match_state.toss_winner} won, elected to {self.match_state.toss_decision}")
            
            # Extract venue - look for known cricket venue patterns
            # Be specific to avoid capturing random text
            if self.venue_override:
                self.match_state.venue = self.venue_override
                print(f"[VENUE] Venue (Override): {self.match_state.venue}")
            else:
                # First, try to extract venue from the weather section (appears at top of info page)
                # Pattern: "International Sports Stadium, Coffs Harbour weather International Sports Stadium"
                # or "Adelaide Oval weather Adelaide Oval 25°C"
                weather_venue_match = re.search(r'([\w\s]+(?:Stadium|Oval|Ground|Arena|Park))(?:,\s*[\w\s]+)?\s+weather\s+\1', page_text, re.IGNORECASE)
                if weather_venue_match:
                    venue = weather_venue_match.group(1).strip()
                    venue = ' '.join(venue.split())
                    if len(venue) > 5 and len(venue) < 60:
                        self.match_state.venue = venue
                        logger.info(f"Extracted venue from weather section: '{venue}'")
                        print(f"[VENUE] Venue: {self.match_state.venue}")
                
                # If weather pattern didn't work, try specific venue patterns
                if not self.match_state.venue:
                    venue_patterns = [
                        r'Venue\s*[:\-]?\s*([\w\s]+(?:Stadium|Oval|Ground|Arena|Park))',  # "Venue: North Sydney Oval"
                        # BBL regional/special venues (prioritize specific names)
                        r'(International Sports Stadium[\w\s,]*)',  # Coffs Harbour
                        r'(C\.?ex Coffs International Stadium)',  # Alternative name
                        r'(Lavington Sports Ground)',  # Albury
                        r'(Traeger Park[\w\s,]*)',  # Alice Springs
                        # SA20 venues
                        r'(Kingsmead[\w\s,]*)',  # Durban
                        r'(Newlands[\w\s,]*)',   # Cape Town
                        r'(Boland Park[\w\s,]*)', # Paarl
                        r"(St George's Park[\w\s,]*)",  # Gqeberha
                        r'(SuperSport Park[\w\s,]*)',  # Centurion
                        r'(Wanderers[\w\s,]*)',  # Johannesburg
                        r'(Durban[\w\s]+Stadium)',
                        r'(Hollywoodbets[\w\s]+)',
                        # New Zealand venues (Super Smash)
                        r'(Basin Reserve[\w\s,]*)',
                        r'(Eden Park[\w\s,]*)',
                        r'(Hagley Oval[\w\s,]*)',
                        r'(Seddon Park[\w\s,]*)',
                        r'(Bay Oval[\w\s,]*)',
                        r'(McLean Park[\w\s,]*)',
                        r'(University of Otago Oval[\w\s,]*)',  # Dunedin - exact name
                        r'(University Oval[\w\s,]*)',  # Generic fallback
                        r'(Saxton Oval[\w\s,]*)',
                        r'(Pukekura Park[\w\s,]*)',
                        r'(Molyneux Park[\w\s,]*)',
                        r'(John Davies Oval[\w\s,]*)',
                        r'(Fitzherbert Park[\w\s,]*)',
                        r'(Cobham Oval[\w\s,]*)',
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
                                print(f"[VENUE] Venue: {self.match_state.venue}")
                                break
            
            # Extract teams from info page - store both teams, we'll figure out batting/bowling from title
            vs_match = re.search(r'([A-Z0-9\-]+)\s+vs\s+([A-Z0-9\-]+)', page_text)
            if vs_match:
                team1, team2 = vs_match.group(1), vs_match.group(2)
                # Store as team1 and team2 initially - batting will be set from title later
                self._team1 = team1
                self._team2 = team2
                print(f"[TEAMS] Teams: {team1} vs {team2}")
                
                # Extract venue stats FIRST (bat/bowl first win rates)
                await self._extract_venue_stats(page_text)
                
                # Extract team comparison stats (season form) and inject into feature store
                # This will use venue stats for situation rates if available
                await self._extract_team_comparison(page_text, team1, team2)
            
            # Navigate back to live page
            await self.page.goto(self.match_url, timeout=30000)
            await asyncio.sleep(3)
            
        except Exception as e:
            print(f"[WARN] Could not fetch info page: {e}")
            # Still try to go to live page
            try:
                await self.page.goto(self.match_url, timeout=30000)
                await asyncio.sleep(3)
            except:
                pass
    
    async def start(self):
        """Start the browser and navigate to match."""
        print(f"[START] Starting Crex Live Predictor")
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
        print(f"[WEB] Opening info page first...")
        await self._fetch_match_info_page()
        
        # Wait for page title to include score (retry up to 10 times)
        for _ in range(10):
            title = await self.page.title()
            if re.match(r'^(\w+)\s+(\d+)[-/](\d+)\s+\(', title):
                break
            await asyncio.sleep(1)
        
        print(f"[OK] Page loaded: {title}")
        
        # Extract localStorage for team/player code resolution
        try:
            self.local_storage = await self.page.evaluate(
                "() => Object.fromEntries(Object.entries(localStorage).map(([k, v]) => [k, v]))"
            )
            team_entries = sum(1 for k in self.local_storage if k.startswith('t_'))
            print(f"[STORE] Loaded localStorage: {len(self.local_storage)} entries ({team_entries} teams)")
        except Exception as e:
            print(f"[WARN] Could not extract localStorage: {e}")
            self.local_storage = {}
        
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
                            
            # Extract market odds from API (fields F and R)
            # F = Favorite team code, R = Odds in format "back+diff"
            fav_team_code = data.get("F", "").replace("^", "")
            if fav_team_code:
                # Resolve team code to name using localStorage
                fav_team_name = self.local_storage.get(f"t_{fav_team_code}_name", fav_team_code)
                self.match_state.market_fav_team = fav_team_name
            
            r_val = data.get("R", "")
            if r_val:
                r_str = str(r_val)
                if "+" in r_str:
                    parts = r_str.split("+")
                    back = parts[0]
                    diff = parts[1] if len(parts) > 1 else "0"
                    try:
                        lay = str(int(back) + int(diff))
                        self.match_state.market_back_odds = back
                        self.match_state.market_lay_odds = lay
                        # Calculate implied probability: 100 / (100 + odds)
                        # E.g., odds of 90 means favorite has ~52.6% implied prob
                        back_int = int(back)
                        if back_int > 0:
                            self.match_state.market_fav_prob = 100.0 / (100.0 + back_int)
                    except ValueError:
                        pass
                else:
                    self.match_state.market_back_odds = r_str
                    self.match_state.market_lay_odds = r_str
                    try:
                        back_int = int(r_str)
                        if back_int > 0:
                            self.match_state.market_fav_prob = 100.0 / (100.0 + back_int)
                    except ValueError:
                        pass
                        
        except Exception as e:
            print(f"[WARN] Error processing API data: {e}")
    
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
            print(f"[WARN] Error extracting match info: {e}")
    
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
            print(f"[WARN] Error in poll_and_predict: {e}")
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
            # Use generic venue name if not extracted from page (avoids "Unknown" warning)
            venue_name = self.match_state.venue
            if not venue_name or venue_name.strip() == "":
                # Use a generic but valid venue name that won't trigger warnings
                # The predictor will use default venue stats + CREX live venue stats override
                venue_name = "International Cricket Stadium"
                
            pred_state = PredictorMatchState(
                match_id="live_match",  # Required field
                venue=venue_name,
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
            self.last_calibrated_phase = getattr(self.predictor, 'last_calibrated_phase', win_prob)
            self.last_calibrated_per_over = getattr(self.predictor, 'last_calibrated_per_over', win_prob)
            
            return float(win_prob)
            
        except Exception as e:
            print(f"[WARN] Prediction error: {e}")
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
            print(f"[WARN] Error building features: {e}")
            return None
    
    async def run(self, poll_interval: float = 2.0):
        """Run the live predictor continuously."""
        self._running = True
        
        started = await self.start()
        if not started:
            print("[ERROR] Failed to start predictor")
            return
        
        print("\n" + "="*60)
        print("LIVE MATCH PREDICTION")
        print("="*60)
        print(f"   {self.match_state.batting_team} vs {self.match_state.bowling_team}")
        if self.match_state.venue:
            print(f"   Venue: {self.match_state.venue}")
        print("="*60)
        print("\n[...] Monitoring match... Press Ctrl+C to stop\n")
        
        try:
            while self._running:
                # Poll and predict
                win_prob = await self.poll_and_predict()
                
                # Display current state
                self._display_state(win_prob)
                
                await asyncio.sleep(poll_interval)
                
        except asyncio.CancelledError:
            print("\n[STOP] Predictor stopped")
        except KeyboardInterrupt:
            print("\n[STOP] Stopped by user")
        finally:
            await self.stop()
    
    def _display_state(self, win_prob: Optional[float]):
        """Display current match state and prediction."""
        state = self.match_state
        
        # Build display line
        display = f"\r{state.batting_team}: {state.total_runs}/{state.wickets} ({state.overs} ov)"
        
        if state.is_second_innings and state.target:
            runs_needed = state.target - state.total_runs
            display += f" | Need: {runs_needed}"
        else:
            display += f" | CRR: {state.current_run_rate}"
        
        if win_prob is not None:
            bar_len = 20
            filled = int(win_prob * bar_len)
            bar = "#" * filled + "-" * (bar_len - filled)
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
                "innings": 2 if state.is_second_innings else 1,
                "batting_team": state.batting_team,
                "bowling_team": state.bowling_team,
                "timestamp": datetime.now().isoformat()
            })
            
            # Persist history to file for page refresh resilience
            self._save_history()
            
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
                "calibrated_phase_prob": getattr(self, 'last_calibrated_phase', win_prob),
                "calibrated_per_over_prob": getattr(self, 'last_calibrated_per_over', win_prob),
                "league": self.league,  # League code if --league was specified
                "league_calibrated_prob": win_prob if self.league else None,  # Final league-calibrated prob
                "features": features,
                "history": self._prediction_history[-50:],  # Last 50 data points
                # Market odds from CREX
                "market_fav_team": state.market_fav_team,
                "market_back_odds": state.market_back_odds,
                "market_lay_odds": state.market_lay_odds,
                "market_fav_prob": state.market_fav_prob,
                # Monte Carlo simulation results (uses league-calibrated win_prob for betting edge)
                "monte_carlo": self._run_monte_carlo_simulation(model_prob=win_prob, use_ml_model=self.use_ml_model)
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
                print("\n[STOP] Browser closed")
            except Exception as e:
                print(f"\n[WARN] Browser close failed (ignored): {e}")
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
    parser.add_argument("--venue", default=None, help="Manually specify venue name")
    parser.add_argument(
        "--live-match-json",
        default=None,
        help="Optional richer per-match debug JSON (defaults to sibling livematch.json when --output-json is set)",
    )
    parser.add_argument(
        "--league",
        default=None,
        help="League code for league-specific calibration (e.g., 'ssm', 'bbl', 'sa20')",
    )
    parser.add_argument(
        "--use-ml-model",
        action="store_true",
        default=False,
        help="Use ML model for Monte Carlo terminal state evaluation (more accurate, ~50ms for 2000 sims)",
    )
    
    args = parser.parse_args()
    
    predictor = CrexLivePredictor(
        match_url=args.match_url,
        model_dir=args.model_dir,
        headless=args.headless,
        feature_store_dir=args.feature_store_dir,
        output_json=args.output_json,
        live_match_json=args.live_match_json,
        venue=args.venue,
        league=args.league,
        use_ml_model=args.use_ml_model,
    )
    
    await predictor.run(poll_interval=args.poll_interval)


if __name__ == "__main__":
    asyncio.run(main())
