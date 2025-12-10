import sys
import time
import csv
import re
import os
from playwright.sync_api import sync_playwright

def parse_batsman_stats(stat_str):
    """Parse batsman statistics string into components"""
    match = re.match(r'(\d+) \((\d+)b(?: (\d+)x4)?(?: (\d+)x6)?\)', stat_str)
    if match:
        return {
            'runs': int(match.group(1)),
            'balls': int(match.group(2)),
            'fours': int(match.group(3)) if match.group(3) else 0,
            'sixes': int(match.group(4)) if match.group(4) else 0
        }
    return None

def parse_bowler_stats(stat_str):
    """Parse bowler statistics string into components"""
    match = re.match(r'(\d+)-(\d+)-(\d+)-(\d+)', stat_str)
    if match:
        return {
            'overs': float(match.group(1)),
            'maidens': int(match.group(2)),
            'runs': int(match.group(3)),
            'wickets': int(match.group(4))
        }
    return None

def extract_end_of_over_data(end_of_over_div):
    """Extract and transform detailed ball-by-ball statistics"""
    over_stats = {
        'batsman1_name': '', 'batsman1_runs': 0, 'batsman1_balls_faced': 0, 'batsman1_fours': 0, 'batsman1_sixes': 0,
        'batsman2_name': '', 'batsman2_runs': 0, 'batsman2_balls_faced': 0, 'batsman2_fours': 0, 'batsman2_sixes': 0,
        'bowler1_name': '', 'bowler1_overs_bowled': 0, 'bowler1_maidens_bowled': 0, 'bowler1_runs_conceded': 0, 'bowler1_wickets_taken': 0,
        'bowler2_name': '', 'bowler2_overs_bowled': 0, 'bowler2_maidens_bowled': 0, 'bowler2_runs_conceded': 0, 'bowler2_wickets_taken': 0
    }
    
    try:
        # Extract batsmen stats
        batsmen_stats = end_of_over_div.locator(
            "xpath=.//div[contains(@class, 'ds-w-1/2') and contains(@class, 'ds-pl-')]//div[contains(@class, 'ds-flex') and contains(@class, 'ds-justify-between')]"
        )
        
        for j in range(min(2, batsmen_stats.count())):
            name = batsmen_stats.nth(j).locator("span:nth-child(1)").inner_text().strip()
            stat_str = batsmen_stats.nth(j).locator("span:nth-child(2)").inner_text().strip()
            
            stats = parse_batsman_stats(stat_str)
            if stats:
                prefix = f"batsman{j+1}_"
                over_stats[f"{prefix}name"] = name
                over_stats[f"{prefix}runs"] = stats['runs']
                over_stats[f"{prefix}balls_faced"] = stats['balls']
                over_stats[f"{prefix}fours"] = stats['fours']
                over_stats[f"{prefix}sixes"] = stats['sixes']

        # Extract bowler stats
        bowler_stats = end_of_over_div.locator(
            "xpath=.//div[contains(@class, 'ds-border-l')]//div[contains(@class, 'ds-flex') and contains(@class, 'ds-justify-between')]"
        )
        
        for k in range(min(2, bowler_stats.count())):
            name = bowler_stats.nth(k).locator("xpath=.//span[contains(@class, 'ds-mt-px')]").inner_text().strip()
            stat_str = bowler_stats.nth(k).locator("span:nth-child(2)").inner_text().strip()
            
            stats = parse_bowler_stats(stat_str)
            if stats:
                prefix = f"bowler{k+1}_"
                over_stats[f"{prefix}name"] = name
                over_stats[f"{prefix}overs_bowled"] = stats['overs']
                over_stats[f"{prefix}maidens_bowled"] = stats['maidens']
                over_stats[f"{prefix}runs_conceded"] = stats['runs']
                over_stats[f"{prefix}wickets_taken"] = stats['wickets']
                
    except Exception as e:
        print(f"Error in extract_end_of_over_data: {e}")
    
    return over_stats

def scrape_innings(page, innings_label, output_file):
    """
    Scrapes the commentary data for the current innings loaded in the page.
    The innings_label can be used to save a CSV file specific to this innings.
    """
    
    batting_team = get_current_batting_team(page)
    print(f"Scraping commentary for {batting_team} ({innings_label} innings)...")
    
    # OPTIONAL: scroll to load all commentary content.
    retry_scroll_up = 0
    while True:
        commentary_locator = page.locator("xpath=//div[contains(@class, 'lg:hover:ds-bg-ui-fill-translucent ds-hover-parent ds-relative')]")
        previous_div_count = commentary_locator.count()
        page.mouse.wheel(0, 5000)
        time.sleep(1)
        new_div_count = commentary_locator.count()
        if new_div_count == previous_div_count:
            retry_scroll_up += 1
            for _ in range(3):
                page.mouse.wheel(0, -1000)
                time.sleep(1)
            page.mouse.wheel(0, 1000)
            time.sleep(1)
            if retry_scroll_up >= 10:
                print("No more new commentary divs found.")
                break
        else:
            retry_scroll_up = 0

    # Initialize variables for over-level metrics
    ball_data = []
    current_over = None
    current_over_metrics = {
        "batting_team": batting_team,
        "over_number": None,
        "ball_number": None,
        "runs_scored": 0,
        "boundaries": 0,
        "dot_balls": 0,
        "wickets": 0,
        "extras": 0,
        "batsman1_name": "", "batsman1_runs": 0, "batsman1_balls_faced": 0, "batsman1_fours": 0, "batsman1_sixes": 0,
        "batsman2_name": "", "batsman2_runs": 0, "batsman2_balls_faced": 0, "batsman2_fours": 0, "batsman2_sixes": 0,
        "bowler1_name": "", "bowler1_overs_bowled": 0, "bowler1_maidens_bowled": 0, "bowler1_runs_conceded": 0, "bowler1_wickets_taken": 0,
        "bowler2_name": "", "bowler2_overs_bowled": 0, "bowler2_maidens_bowled": 0, "bowler2_runs_conceded": 0, "bowler2_wickets_taken": 0
    }

    commentary_divs = page.locator(
        "xpath=//div[contains(@class, 'lg:hover:ds-bg-ui-fill-translucent ds-hover-parent ds-relative')]"
    )
    # Adjust this locator if necessary so that it selects only end-of-over elements.
    end_of_over_divs = page.locator(
        "xpath=//div[contains(@class, 'ds-text-tight-s ds-font-regular')]"
    )

    end_over_index = 0
    num_commentary = commentary_divs.count()

    for i in range(num_commentary):
        try:
            div = commentary_divs.nth(i)
            ball_number = div.locator(
                "xpath=//span[contains(@class, 'ds-text-tight-s') and contains(@class, 'ds-font-regular') and contains(@class, 'ds-text-typo-mid1')]"
            ).inner_text().strip()
            runs_or_event = div.locator(
                "xpath=.//div[contains(@class, 'ds-text-tight-m') and contains(@class, 'ds-font-bold')]/span"
            ).inner_text().strip()
            short_commentary = div.locator(
                "xpath=.//div[contains(@class, 'ds-leading-')]"
            ).evaluate_all("nodes => nodes.map(node => node.textContent.trim()).join(' ')")
            _ = div.locator("xpath=.//p[contains(@class, 'ci-html-content')]").inner_text().strip()

            ball_over = int(float(ball_number))
            
            # If we've moved to a new over, attach the end-of-over stats and reset metrics.
            if current_over is not None and ball_over != current_over:
                try:
                    if end_of_over_divs.count() > end_over_index:
                        end_of_over_div = end_of_over_divs.nth(end_over_index)
                        end_over_index += 1
                        extra_stats = extract_end_of_over_data(end_of_over_div)
                        current_over_metrics.update(extra_stats)
                    else:
                        print(f"No end-of-over div found for over {current_over}")
                except Exception as e:
                    print(f"Error processing end-of-over stats for over {current_over}: {e}")
                
                ball_data.append(current_over_metrics)
                current_over_metrics = {
                    "batting_team": batting_team,
                    "over_number": ball_over,
                    "ball_number": None,
                    "runs_scored": 0,
                    "boundaries": 0,
                    "dot_balls": 0,
                    "wickets": 0,
                    "extras": 0,
                    "batsman1_name": "", "batsman1_runs": 0, "batsman1_balls_faced": 0, "batsman1_fours": 0, "batsman1_sixes": 0,
                    "batsman2_name": "", "batsman2_runs": 0, "batsman2_balls_faced": 0, "batsman2_fours": 0, "batsman2_sixes": 0,
                    "bowler1_name": "", "bowler1_overs_bowled": 0, "bowler1_maidens_bowled": 0, "bowler1_runs_conceded": 0, "bowler1_wickets_taken": 0,
                    "bowler2_name": "", "bowler2_overs_bowled": 0, "bowler2_maidens_bowled": 0, "bowler2_runs_conceded": 0, "bowler2_wickets_taken": 0
                }
            current_over = ball_over
            current_over_metrics["over_number"] = current_over
            current_over_metrics["ball_number"] = ball_number

            if runs_or_event.isdigit():
                runs = int(runs_or_event)
                current_over_metrics["runs_scored"] += runs
                if runs in [4, 6]:
                    current_over_metrics["boundaries"] += 1
            elif runs_or_event == "W":
                current_over_metrics["wickets"] += 1
            if runs_or_event == "•":
                current_over_metrics["dot_balls"] += 1
            if "wide" in short_commentary or "no ball" in short_commentary or "leg bye" in short_commentary:
                current_over_metrics["extras"] += 1
                match = re.match(r'(\d+)', runs_or_event)
                runs = int(match.group(1)) if match else 0
                current_over_metrics["runs_scored"] += runs

        except Exception as e:
            print(f"Error processing ball data at index {i}: {e}")

    # Process the final over.
    if current_over is not None:
        try:
            if end_of_over_divs.count() > end_over_index:
                end_of_over_div = end_of_over_divs.nth(end_over_index)
                extra_stats = extract_end_of_over_data(end_of_over_div)
                current_over_metrics.update(extra_stats)
            else:
                print(f"No end-of-over div found for over {current_over_metrics['over_number']}")
        except Exception as e:
            print(f"Error processing end-of-over stats for final over {current_over_metrics['over_number']}: {e}")
        ball_data.append(current_over_metrics)

    # Save the data to a CSV file unique to the innings.
    fieldnames = [
        "batting_team", "over_number", "ball_number", "runs_scored", "boundaries", 
        "dot_balls", "wickets", "extras",
        "batsman1_name", "batsman1_runs", "batsman1_balls_faced", "batsman1_fours", "batsman1_sixes",
        "batsman2_name", "batsman2_runs", "batsman2_balls_faced", "batsman2_fours", "batsman2_sixes",
        "bowler1_name", "bowler1_overs_bowled", "bowler1_maidens_bowled", "bowler1_runs_conceded", "bowler1_wickets_taken",
        "bowler2_name", "bowler2_overs_bowled", "bowler2_maidens_bowled", "bowler2_runs_conceded", "bowler2_wickets_taken"
    ]

    with open(output_file, "w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(ball_data)  # ball_data now contains the detailed metrics

    print(f"Data saved successfully to {output_file}.")

def select_other_innings(page):
    """
    Clicks the innings dropdown, and selects the other innings.
    In this example, we assume that the dropdown shows two options (for example: MI and CSK),
    and that the currently selected innings is indicated by a bold style (ds-font-bold).
    We then select the li option that does NOT have the ds-font-bold class.
    """
    print("Switching innings...")
    # Click the dropdown button (the outer container that toggles the dropdown)
    dropdown_button_selector = 'div.ds-flex.ds-items-center.ds-cursor-pointer'
    page.wait_for_selector(dropdown_button_selector)
    page.click(dropdown_button_selector)
    time.sleep(1)  # Wait for the dropdown list to appear

    # Get all list items in the dropdown.
    # (The dropdown content appears inside a div with a specific class.)
    li_locator = page.locator("xpath=//ul[contains(@class, 'ds-flex')]/li")
    li_count = li_locator.count()
    target_option = None

    # Loop through each li element and select the one that is not currently selected.
    # Here, the currently selected innings is indicated by a bold font (ds-font-bold).
    for i in range(li_count):
        li_element = li_locator.nth(i)
        # Look for the inner div that holds the innings name.
        inner_div = li_element.locator("div.ds-cursor-pointer")
        # Read its class attribute.
        class_attr = inner_div.get_attribute("class") or ""
        # If ds-font-bold is present, it means this option is currently selected.
        if "ds-font-bold" not in class_attr:
            target_option = inner_div
            break

    if target_option is not None:
        target_option.click()
        time.sleep(2)  # Allow time for the page to update to the selected innings
        # Optionally, you can verify that the page updated by checking some element.
        print("Other innings selected.")
    else:
        print("No alternative innings option found.")
        
def get_current_batting_team(page):
    """
    Extract the name of the team currently batting from the dropdown or page header.
    """
    try:
        # Locate the dropdown and extract the team name from the <span>
        team_name = page.locator("div.ds-flex.ds-items-center.ds-cursor-pointer span.ds-text-tight-s.ds-font-regular").first.inner_text().strip()
        print(f"Currently batting team: {team_name}")
        return team_name
    except Exception as e:
        print(f"Error fetching the batting team: {e}")
        return "Unknown"

def get_match_info_from_url(url):
    """
    Extracts the season folder and match ID from the given URL.
    Example URL format:
    https://www.espncricinfo.com/series/ipl-2020-21-1210595/mumbai-indians-vs-chennai-super-kings-1st-match-1216492/...
    
    Returns:
        tuple: (season_folder, match_id)
        - season_folder: e.g. 'ipl-2020-21-1210595'
        - match_id: e.g. '1216492'
    """
    # Use regex to extract season folder and match ID
    match = re.search(r'/series/([^/]+)/([^/]+)/', url)
    if (match):
        season_folder = match.group(1)  # Gets 'ipl-2020-21-1210595'
        match_id = match.group(2)       # Gets 'mumbai-indians-vs-chennai-super-kings-1st-match-1216492'
        
        # Extract just the numeric match ID from the end
        match_id_num = re.search(r'(\d+)$', match_id)
        if match_id_num:
            match_id = match_id_num.group(1)
        
        return season_folder, match_id
    return "default_season", "default_match"

def main(url=None):
    """Modified main function to accept URL parameter"""
    if not url:
        # Get URL from command line arguments if not provided
        if len(sys.argv) != 2:
            print("Usage: python espnscraper_ballbyball.py <match_url>")
            sys.exit(1)
        url = sys.argv[1]
    
    # Convert scorecard URL to ball-by-ball URL if needed
    if "full-scorecard" in url:
        url = url.replace("full-scorecard", "ball-by-ball-commentary")
    elif "live-cricket-score" in url:
        url = url.replace("live-cricket-score", "ball-by-ball-commentary")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        # Navigate to the commentary page
        page.goto(url, timeout=60000)
        time.sleep(3)
        
        # Get match info and create directory structure
        season_folder, match_id = get_match_info_from_url(url)
        current_dir = os.path.dirname(os.path.abspath(__file__))
        ball_by_ball_dir = os.path.join(current_dir, season_folder, match_id, 'ball_by_ball')
        
        # Create directory if it doesn't exist
        if not os.path.exists(ball_by_ball_dir):
            os.makedirs(ball_by_ball_dir)

        # Scrape both innings and save in the ball_by_ball directory
        for innings in ["First", "Second"]:
            if innings == "Second":
                select_other_innings(page)
                time.sleep(3)
            
            output_file = os.path.join(ball_by_ball_dir, f"{innings}_innings_summary.csv")
            scrape_innings(page, innings, output_file)

        browser.close()

if __name__ == "__main__":
    main()
