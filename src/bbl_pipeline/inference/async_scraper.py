"""
Async ESPN Cricinfo Live Match Scraper
Uses async Playwright with stealth to scrape live match data.
"""
import asyncio
import re
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime

from playwright.async_api import async_playwright, Page, Browser


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
    extras_type: Optional[str]  # "lb", "wd", "nb", etc.
    commentary: str
    batsman_name: str
    bowler_name: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class MatchState:
    """Current match state."""
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
    batsman1_on_strike: bool = False
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


class AsyncCricInfoScraper:
    """Async scraper for ESPN Cricinfo live matches."""
    
    def __init__(
        self,
        match_url: str,
        on_ball_callback: Optional[Callable[[BallData, MatchState], None]] = None,
        headless: bool = True
    ):
        self.match_url = match_url
        self.on_ball_callback = on_ball_callback
        self.headless = headless
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.match_state = MatchState()
        self.processed_balls: set = set()
        self.last_commentary_text: str = ""
        self._running = False
        
    async def start(self):
        """Start the scraper."""
        print(f"🏏 Starting async scraper for: {self.match_url}")
        
        playwright = await async_playwright().start()
        
        # Launch browser with stealth settings
        self.browser = await playwright.chromium.launch(headless=self.headless)
        
        # Create context with realistic browser fingerprint
        context = await self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080},
            locale='en-US',
            timezone_id='Asia/Kolkata',
        )
        
        # Add stealth scripts to avoid detection
        await context.add_init_script("""
            // Overwrite navigator.webdriver
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            
            // Overwrite chrome property
            window.chrome = {
                runtime: {}
            };
            
            // Overwrite permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
            
            // Overwrite plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            
            // Overwrite languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });
        """)
        
        self.page = await context.new_page()
        
        print(f"🌐 Opening match page...")
        await self.page.goto(self.match_url, timeout=60000)
        await asyncio.sleep(5)  # Wait for page to fully load
        
        # Check if page loaded successfully
        title = await self.page.title()
        if "Access Denied" in title:
            print("❌ Access Denied - Bot detection triggered")
            return False
            
        print(f"✅ Page loaded: {title}")
        
        # Extract initial match info
        await self._extract_match_info()
        
        return True
    
    async def _extract_match_info(self):
        """Extract static match information (venue, toss, etc.)."""
        try:
            # Extract venue from match details table
            venue_el = self.page.locator("a[href*='cricket-grounds']").first
            if await venue_el.count() > 0:
                self.match_state.venue = await venue_el.inner_text()
                print(f"📍 Venue: {self.match_state.venue}")
            
            # Extract toss information
            toss_row = self.page.locator("text=Toss").locator("..").locator("td").last
            if await toss_row.count() > 0:
                toss_text = await toss_row.inner_text()
                # Parse "Kathmandu Gorkhas (NPL), elected to bat first"
                match = re.match(r'^(.+?),\s*elected to\s+(.+)$', toss_text)
                if match:
                    self.match_state.toss_winner = match.group(1).strip()
                    self.match_state.toss_decision = match.group(2).strip()
                    print(f"🪙 Toss: {self.match_state.toss_winner} elected to {self.match_state.toss_decision}")
                    
        except Exception as e:
            print(f"⚠️ Could not extract match info: {e}")
    
    async def _extract_scorecard(self):
        """Extract current scorecard (batters and bowlers)."""
        try:
            # Find the batters table
            batter_rows = self.page.locator("table tbody tr").filter(has=self.page.locator("a[href*='cricketers']"))
            
            count = await batter_rows.count()
            batters_found = 0
            
            for i in range(min(count, 4)):  # Max 2 batters + 2 bowlers
                row = batter_rows.nth(i)
                cells = row.locator("td")
                cell_count = await cells.count()
                
                if cell_count >= 6:
                    # Get player name
                    name_el = row.locator("a[href*='cricketers'] span").first
                    if await name_el.count() > 0:
                        name = await name_el.inner_text()
                        name = name.replace("*", "").replace("\xa0", "").strip()
                        
                        # Check if this is a batter row (has R, B, 4s, 6s, SR columns)
                        first_cell_text = await cells.nth(0).inner_text()
                        
                        if batters_found < 2 and "rhb" in first_cell_text.lower() or "lhb" in first_cell_text.lower() or await cells.nth(1).inner_text() != "":
                            # This is a batter
                            try:
                                runs = int(await cells.nth(1).locator("strong").inner_text())
                            except:
                                runs = 0
                            try:
                                balls = int(await cells.nth(2).inner_text())
                            except:
                                balls = 0
                            
                            # Check for strike indicator (*)
                            on_strike = "*" in await cells.nth(0).inner_text()
                            
                            if batters_found == 0:
                                self.match_state.batsman1_name = name
                                self.match_state.batsman1_runs = runs
                                self.match_state.batsman1_balls = balls
                                self.match_state.batsman1_on_strike = on_strike
                            else:
                                self.match_state.batsman2_name = name
                                self.match_state.batsman2_runs = runs
                                self.match_state.batsman2_balls = balls
                            
                            batters_found += 1
            
            # Extract bowler info from the Bowlers section
            bowler_section = self.page.locator("th:text('Bowlers')").locator("..").locator("..").locator("..").locator("tbody tr").first
            if await bowler_section.count() > 0:
                bowler_name_el = bowler_section.locator("a[href*='cricketers'] span").first
                if await bowler_name_el.count() > 0:
                    self.match_state.bowler1_name = (await bowler_name_el.inner_text()).replace("\xa0", "").strip()
                    
                    cells = bowler_section.locator("td")
                    if await cells.count() >= 5:
                        try:
                            self.match_state.bowler1_overs = float(await cells.nth(1).inner_text())
                        except:
                            pass
                        try:
                            self.match_state.bowler1_runs = int(await cells.nth(3).inner_text())
                        except:
                            pass
                        try:
                            self.match_state.bowler1_wickets = int(await cells.nth(4).inner_text())
                        except:
                            pass
                            
        except Exception as e:
            print(f"⚠️ Could not extract scorecard: {e}")
    
    async def _extract_match_score(self):
        """Extract current match score from end-of-over summary or score header."""
        try:
            # Try to find end-of-over summary which has the score
            eoo_div = self.page.locator("div.ds-border-l-4.ds-border-ui-stroke-primary.ds-bg-raw-blue\\/20").first
            
            if await eoo_div.count() > 0:
                score_el = eoo_div.locator("span.ds-text-tight-m.ds-font-bold").last
                if await score_el.count() > 0:
                    score_text = await score_el.inner_text()
                    # Parse "KAG: 40/4"
                    match = re.match(r'^(\w+):\s*(\d+)/(\d+)$', score_text)
                    if match:
                        self.match_state.batting_team = match.group(1)
                        self.match_state.total_runs = int(match.group(2))
                        self.match_state.wickets = int(match.group(3))
                
                # Extract CRR
                crr_el = eoo_div.locator("text=/CRR:/")
                if await crr_el.count() > 0:
                    crr_text = await crr_el.inner_text()
                    crr_match = re.search(r'CRR:\s*([\d.]+)', crr_text)
                    if crr_match:
                        self.match_state.current_run_rate = float(crr_match.group(1))
                        
        except Exception as e:
            print(f"⚠️ Could not extract match score: {e}")
    
    async def _parse_ball_commentary(self, commentary_div) -> Optional[BallData]:
        """Parse a single ball commentary div into BallData."""
        try:
            # Extract ball number (e.g., "8.3")
            ball_num_el = commentary_div.locator("span.ds-text-tight-s.ds-font-regular.ds-text-typo-mid1").first
            if await ball_num_el.count() == 0:
                return None
                
            ball_number = await ball_num_el.inner_text()
            ball_number = ball_number.strip()
            
            # Validate ball number format
            if not re.match(r'^\d+\.\d+$', ball_number):
                return None
            
            # Parse over and ball
            over_match = re.match(r'^(\d+)\.(\d+)$', ball_number)
            over_number = int(over_match.group(1))
            ball_in_over = int(over_match.group(2))
            
            # Extract runs/event indicator
            runs_el = commentary_div.locator("div.ds-text-tight-m.ds-font-bold span").first
            runs_text = "0"
            if await runs_el.count() > 0:
                runs_text = await runs_el.inner_text()
                runs_text = runs_text.strip()
            
            # Parse runs and events
            runs = 0
            is_wicket = False
            is_dot = False
            is_boundary = False
            is_six = False
            extras = 0
            extras_type = None
            
            if runs_text == "•":
                is_dot = True
            elif runs_text == "W":
                is_wicket = True
            elif runs_text == "4":
                runs = 4
                is_boundary = True
            elif runs_text == "6":
                runs = 6
                is_six = True
            elif runs_text.isdigit():
                runs = int(runs_text)
            elif "lb" in runs_text.lower():
                extras_type = "lb"
                extras = int(re.search(r'\d+', runs_text).group()) if re.search(r'\d+', runs_text) else 1
            elif "wd" in runs_text.lower():
                extras_type = "wd"
                extras = int(re.search(r'\d+', runs_text).group()) if re.search(r'\d+', runs_text) else 1
            elif "nb" in runs_text.lower():
                extras_type = "nb"
                extras = int(re.search(r'\d+', runs_text).group()) if re.search(r'\d+', runs_text) else 1
            
            # Extract commentary text
            comm_el = commentary_div.locator("div.ds-ml-4.ds-text-typo-mid1, div.ds-ml-3.ds-text-typo-mid1").first
            commentary = ""
            if await comm_el.count() > 0:
                commentary = await comm_el.inner_text()
                commentary = commentary.strip()
            
            # Parse bowler and batsman from commentary
            # Format: "Gautam to Simpson, 1 run"
            bowler_name = ""
            batsman_name = ""
            comm_match = re.match(r'^(\w+)\s+to\s+(\w+),', commentary)
            if comm_match:
                bowler_name = comm_match.group(1)
                batsman_name = comm_match.group(2)
            
            return BallData(
                ball_number=ball_number,
                over_number=over_number,
                ball_in_over=ball_in_over,
                runs=runs,
                is_wicket=is_wicket,
                is_dot=is_dot,
                is_boundary=is_boundary,
                is_six=is_six,
                extras=extras,
                extras_type=extras_type,
                commentary=commentary,
                batsman_name=batsman_name,
                bowler_name=bowler_name
            )
            
        except Exception as e:
            print(f"⚠️ Error parsing ball commentary: {e}")
            return None
    
    async def poll_for_new_ball(self) -> Optional[BallData]:
        """Poll for a new ball delivery."""
        if not self.page:
            return None
            
        try:
            # Find all commentary divs
            commentary_divs = self.page.locator("div.lg\\:hover\\:ds-bg-ui-fill-translucent.ds-hover-parent.ds-relative")
            
            count = await commentary_divs.count()
            if count == 0:
                return None
            
            # Get the first (latest) commentary div
            first_div = commentary_divs.first
            current_text = await first_div.inner_text()
            current_text = current_text.strip()
            
            # Skip if text hasn't changed
            if current_text == self.last_commentary_text:
                return None
            
            self.last_commentary_text = current_text
            
            # Parse the ball data
            ball_data = await self._parse_ball_commentary(first_div)
            
            if ball_data is None:
                return None
            
            # Skip if we've already processed this ball
            if ball_data.ball_number in self.processed_balls:
                return None
            
            # Mark as processed
            self.processed_balls.add(ball_data.ball_number)
            
            # Update match state
            await self._extract_scorecard()
            await self._extract_match_score()
            
            print(f"🏏 Ball {ball_data.ball_number}: {ball_data.commentary}")
            
            return ball_data
            
        except Exception as e:
            print(f"⚠️ Error polling for new ball: {e}")
            return None
    
    async def run(self, poll_interval: float = 1.0):
        """Run the scraper continuously."""
        self._running = True
        
        started = await self.start()
        if not started:
            print("❌ Failed to start scraper")
            return
        
        print("⏳ Waiting for balls to be bowled...")
        print("⌨️ Press Ctrl+C to stop\n")
        
        try:
            while self._running:
                ball_data = await self.poll_for_new_ball()
                
                if ball_data and self.on_ball_callback:
                    self.on_ball_callback(ball_data, self.match_state)
                
                await asyncio.sleep(poll_interval)
                
        except asyncio.CancelledError:
            print("\n✋ Scraper stopped")
        finally:
            await self.stop()
    
    async def stop(self):
        """Stop the scraper and close browser."""
        self._running = False
        if self.browser:
            await self.browser.close()
            print("🛑 Browser closed")


async def main():
    """Test the scraper."""
    def on_ball(ball: BallData, state: MatchState):
        print(f"\n📊 Ball Update:")
        print(f"   Ball: {ball.ball_number}")
        print(f"   Runs: {ball.runs}, Wicket: {ball.is_wicket}")
        print(f"   Commentary: {ball.commentary}")
        print(f"   Score: {state.batting_team} {state.total_runs}/{state.wickets}")
        print(f"   Batsman: {state.batsman1_name} ({state.batsman1_runs})")
        print(f"   Bowler: {state.bowler1_name}")
    
    url = "https://www.espncricinfo.com/series/nepal-premier-league-2025-26-1510976/kathmandu-gorkhas-npl-vs-lumbini-lions-npl-eliminator-1511006/live-cricket-score"
    
    scraper = AsyncCricInfoScraper(
        match_url=url,
        on_ball_callback=on_ball,
        headless=True
    )
    
    await scraper.run()


if __name__ == "__main__":
    asyncio.run(main())
