
import asyncio
import json
import logging
import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

from src.dom_match_extract import extract_match_dom_fields

def verify_parity():
    print("=== Scraper Parity Verification ===")
    
    # 1. Load Test HTML
    html_path = Path(__file__).parent / "test_match.html"
    with open(html_path, "r", encoding="utf-8") as f:
        html_content = f.read()
        
    # 2. Run New Scraper Extraction
    print("\n[New Scraper] Extracting data from DOM...")
    new_data = extract_match_dom_fields(html_content)
    print(json.dumps(new_data, indent=2))
    
    # 3. Define Legacy Data Structure (based on code analysis)
    legacy_structure = {
        "player_data": {"p_123": "Player Name", "count": "Hundreds of entries"},
        "team_data": {"t_IND": "India", "count": "Tens of entries"},
        "series_data": {"s_456": "Series Name"},
        "innings_stats": {
            "innings": {
                "1st_inning": {
                    "team_code": "IND",
                    "team_score": "250/5",
                    "bowlers_stats": {"B1": {"overs": 10, "runs": 45, "wickets": 2}},
                    "batsman_stats": {"P1": {"runs": 100, "balls": 90}}
                }
            }
        },
        "match_info": "Detailed JSON from network interception"
    }
    
    # 4. Compare
    print("\n[Comparison]")
    print("Legacy Scraper Source: localStorage + Network Interception")
    print("New Scraper Source:    DOM Parsing (BeautifulSoup)")
    
    print("\n[Missing in New Scraper]")
    print("- Full Player Map (localStorage)")
    print("- Full Team Map (localStorage)")
    print("- Detailed Innings Stats (Network JSON)")
    print("- Ball-by-ball data")
    
    print("\n[Conclusion]")
    print("The new scraper is currently a 'Lite' version. It extracts high-level match status")
    print("(score, result, current over) but lacks the deep statistical data provided by the")
    print("legacy scraper. It also does NOT push data to the backend API yet.")

if __name__ == "__main__":
    verify_parity()
