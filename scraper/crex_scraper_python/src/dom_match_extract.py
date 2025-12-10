"""DOM match page extraction utilities.

Parses HTML from an individual match page and extracts required fields.
Designed to be independent of Playwright so tests can validate coverage
without launching a browser.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Any
import logging
from bs4 import BeautifulSoup

# Use standard logging for now to bypass structlog filtering if any
logger = logging.getLogger("dom_match_extract")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)

# Canonical selector list preserving synchronous scraper coverage
REQUIRED_SELECTORS: List[str] = [
    ".odds-view-btn .view:nth-child(2)",
    ".result-box span",
    ".team-run-rate .data",
    ".final-result.m-none",
    ".team-content",
    ".team-content .team-name",
    ".team-content .runs span:nth-child(1)",
    ".team-content .runs span:nth-child(2)",
    "div#slideOver .overs-slide",
    "div#slideOver .overs-slide span",
    "div#slideOver .overs-slide .over-ball",
    "div#slideOver .overs-slide .total",
    ".fav-odd .d-flex",
    ".fav-odd .d-flex .team-name span",
    ".fav-odd .d-flex .odd div",
    "span.ds-text-title-xs.ds-font-bold.ds-capitalize",
    "div.ds-w-full.ds-bg-fill-content-prime.ds-overflow-hidden.ds-rounded-xl.ds-border.ds-border-line.ds-mb-4",
    "a[href*='cricket-grounds']",
    "div.ds-px-4.ds-pb-3 p",
    "div.ds-px-4.ds-pb-3 span",
    "div.ds-text-tight-s.ds-font-bold.ds-ml-1",
]


def get_missing_selectors(html: str) -> List[str]:
    """Return selectors from REQUIRED_SELECTORS not found in HTML.

    For nth-child selectors we apply a tolerant presence check by evaluating
    parent selector existence when direct match fails.
    """
    soup = BeautifulSoup(html, "html.parser")
    missing = []
    for sel in REQUIRED_SELECTORS:
        # Basic lookup first
        found = soup.select(sel)
        if found:
            continue
        # Tolerant fallback for nth-child: strip :nth-child segment
        if ":nth-child" in sel:
            base = sel.split(":nth-child")[0].rstrip()
            if soup.select(base):
                continue
        missing.append(sel)
    return missing


def extract_match_dom_fields(html: str) -> Dict[str, Any]:
    """Extract structured match data from HTML.

    Returns keys: result, run_rate, teams (list), overs (list), odds (list), venue.
    Missing sections produce empty lists/None but selectors still validated via tests.
    """
    soup = BeautifulSoup(html, "html.parser")

    result_spans = [s.get_text(strip=True) for s in soup.select(".result-box span")]
    final_result = next((s.get_text(strip=True) for s in soup.select(".final-result.m-none")), None)
    run_rate = next((s.get_text(strip=True) for s in soup.select(".team-run-rate .data")), None)
    venue = next((a.get_text(strip=True) for a in soup.select("a[href*='cricket-grounds']")), None)

    team_blocks = soup.select(".team-content")
    teams = []
    for block in team_blocks:
        name_el = block.select_one(".team-name")
        runs_el = block.select_one(".runs span:nth-child(1)") or block.select_one(".runs span")
        overs_el = block.select_one(".runs span:nth-child(2)")
        teams.append({
            "name": name_el.get_text(strip=True) if name_el else None,
            "runs": runs_el.get_text(strip=True) if runs_el else None,
            "overs": overs_el.get_text(strip=True) if overs_el else None,
        })

    over_slides = soup.select("div#slideOver .overs-slide")
    overs = []
    for slide in over_slides:
        over_number_el = slide.select_one("span")
        total_el = slide.select_one(".total")
        ball_els = slide.select(".over-ball")
        overs.append({
            "overNumber": over_number_el.get_text(strip=True) if over_number_el else None,
            "balls": [b.get_text(strip=True) for b in ball_els],
            "totalRuns": total_el.get_text(strip=True) if total_el else None,
        })

    # Extract Batsman and Bowler data from Angular components
    batsman_data = []
    bowler_data = []
    
    # Parse Batsmen and Bowlers from app-match-live-player
    live_player_comp = soup.select_one("app-match-live-player")
    if live_player_comp:
        partnerships = live_player_comp.select(".batsmen-partnership")
        for p in partnerships:
            # Check if this is a bowler block
            is_bowler = False
            score_div = p.select_one(".batsmen-score")
            if score_div and "bowler" in score_div.get("class", []):
                is_bowler = True
            
            name_el = p.select_one(".batsmen-name p")
            if not name_el:
                continue
            name = name_el.get_text(strip=True)
            
            if is_bowler:
                # Bowler Extraction
                # Score format: "0-2" (Wickets-Runs)
                # Overs format: "(1.0)"
                score_text = score_div.get_text(strip=True) if score_div else ""
                overs_div = p.select_one(".batsmen-total-score")
                overs_text = overs_div.get_text(strip=True) if overs_div else ""
                
                # Parse score "0-2" -> wickets=0, runs=2
                wickets = "0"
                runs = "0"
                if "-" in score_text:
                    parts = score_text.split("-")
                    wickets = parts[0]
                    runs = parts[1]
                
                # Parse overs "(1.0)" -> "1.0"
                overs = overs_text.replace("(", "").replace(")", "")
                
                # Calculate balls bowled
                try:
                    oparts = overs.split(".")
                    o = int(oparts[0])
                    b = int(oparts[1]) if len(oparts) > 1 else 0
                    balls_bowled = o * 6 + b
                except:
                    balls_bowled = 0
                
                # Economy
                econ = "0.00"
                stats_wrapper = p.select_one(".batsmen-career-wrapper")
                if stats_wrapper:
                    strike_rates = stats_wrapper.select(".strike-rate")
                    for sr in strike_rates:
                        text = sr.get_text(strip=True)
                        if "Econ" in text:
                            val_span = sr.select("span")
                            if len(val_span) >= 2:
                                econ = val_span[1].get_text(strip=True)
                            break

                bowler_data.append({
                    "name": name,
                    "score": runs,
                    "runs_conceded": runs, # Legacy support
                    "ballsBowled": balls_bowled,
                    "balls_bowled": balls_bowled, # Legacy support
                    "wicketsTaken": wickets,
                    "wickets_taken": wickets, # Legacy support
                    "economyRate": econ,
                    "dotBalls": "0",
                    "dot_balls": "0" # Legacy support
                })
                
            else:
                # Batsman Extraction
                runs_el = score_div.select_one("p:nth-child(1)")
                balls_el = score_div.select_one("p:nth-child(2)")
                
                runs = runs_el.get_text(strip=True) if runs_el else "0"
                balls = balls_el.get_text(strip=True).replace("(", "").replace(")", "") if balls_el else "0"
                
                on_strike = bool(score_div.select_one(".circle-strike-icon"))
                
                fours = "0"
                sixes = "0"
                sr = "0.00"
                
                stats_wrapper = p.select_one(".batsmen-career-wrapper")
                if stats_wrapper:
                    strike_rates = stats_wrapper.select(".strike-rate")
                    for item in strike_rates:
                        text = item.get_text(strip=True)
                        val_span = item.select("span")
                        val = val_span[1].get_text(strip=True) if len(val_span) >= 2 else "0"
                        
                        if "4s" in text:
                            fours = val
                        elif "6s" in text:
                            sixes = val
                        elif "SR" in text:
                            sr = val

                batsman_data.append({
                    "name": name,
                    "score": runs,
                    "runs": runs, # Legacy support
                    "ballsFaced": balls,
                    "balls_faced": balls, # Legacy support
                    "fours": fours,
                    "sixes": sixes,
                    "strikeRate": sr,
                    "onStrike": on_strike,
                    "on_strike": on_strike # Legacy support
                })

    # Fallback to table extraction if Angular components not found (legacy support)
    if not batsman_data and not bowler_data:
        tables = soup.select("table")
        # ... existing table logic ...
        for i, table in enumerate(tables):
            headers = [th.get_text(strip=True).lower() for th in table.select("th")]
            
            # Batsman Table
            if any(h in headers for h in ["batter", "batsman"]):
                rows = table.select("tbody tr")
                for row in rows:
                    cols = row.select("td")
                    if len(cols) >= 3: # Name, Runs, Balls at minimum
                        name_el = cols[0]
                        name_text = name_el.get_text(strip=True)
                        on_strike = "*" in name_text
                        
                        runs = cols[1].get_text(strip=True) if len(cols) > 1 else "0"
                        balls = cols[2].get_text(strip=True) if len(cols) > 2 else "0"
                        fours = cols[3].get_text(strip=True) if len(cols) > 3 else "0"
                        sixes = cols[4].get_text(strip=True) if len(cols) > 4 else "0"
                        sr = cols[5].get_text(strip=True) if len(cols) > 5 else "0.00"

                        batsman_data.append({
                            "name": name_text.replace("*", "").strip(),
                            "score": runs,
                            "ballsFaced": balls,
                            "fours": fours,
                            "sixes": sixes,
                            "strikeRate": sr,
                            "onStrike": on_strike
                        })

            # Bowler Table
            elif any(h in headers for h in ["bowler"]):
                rows = table.select("tbody tr")
                for row in rows:
                    cols = row.select("td")
                    if len(cols) >= 4: # Name, O, M, R, W
                        name = cols[0].get_text(strip=True)
                        overs_text = cols[1].get_text(strip=True) if len(cols) > 1 else "0"
                        runs = cols[3].get_text(strip=True) if len(cols) > 3 else "0"
                        wickets = cols[4].get_text(strip=True) if len(cols) > 4 else "0"
                        er = cols[5].get_text(strip=True) if len(cols) > 5 else "0.00"
                        
                        try:
                            parts = overs_text.split(".")
                            o = int(parts[0])
                            b = int(parts[1]) if len(parts) > 1 else 0
                            balls_bowled = o * 6 + b
                        except:
                            balls_bowled = 0

                        bowler_data.append({
                            "name": name,
                            "score": runs, # Runs conceded
                            "ballsBowled": balls_bowled,
                            "wicketsTaken": wickets,
                            "economyRate": er,
                            "dotBalls": "0"
                        })

    # Extract Odds from .fav-odd structure
    fav_blocks = soup.select(".fav-odd .d-flex")
    odds = []
    for fav in fav_blocks:
        team_name_el = fav.select_one(".team-name span")
        # The odds values are in .odd .dark-odds
        odd_values = [d.get_text(strip=True) for d in fav.select(".odd .dark-odds")]
        if team_name_el and odd_values:
             odds.append({
                "team": team_name_el.get_text(strip=True),
                "values": odd_values,
            })

    logger.info(f"[DOM] Extracted {len(batsman_data)} batsman, {len(bowler_data)} bowlers, {len(odds)} odds")

    return {
        "result": final_result,
        "result_box": " ".join(result_spans) if result_spans else None,
        "run_rate": run_rate,
        "teams": teams,
        "overs_data": overs,
        "odds": odds,
        "venue": venue,
        "batsman_data": batsman_data,
        "bowler_data": bowler_data
    }


__all__ = [
    "REQUIRED_SELECTORS",
    "get_missing_selectors",
    "extract_match_dom_fields",
]
