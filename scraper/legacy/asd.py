import csv
import re
from playwright.sync_api import sync_playwright
from batting_stats import BattingHistoryDownloader
from enum import Enum
import requests
from bs4 import BeautifulSoup

class IPLTeam(Enum):
    MI = "Mumbai Indians"
    DC = "Delhi Capitals"
    SRH = "Sunrisers Hyderabad"
    RCB = "Royal Challengers Bangalore"
    KKR = "Kolkata Knight Riders"
    KXIP = "Kings XI Punjab"
    CSK = "Chennai Super Kings"
    RR = "Rajasthan Royals"

def fetch_team_names_and_player_sections(page):
    team_sections = []
    team_name_elements = page.locator('span.ds-text-title-xs.ds-font-bold.ds-capitalize')

    for i in range(team_name_elements.count()):
        team_name = team_name_elements.nth(i).inner_text().strip()
        all_divs = page.locator('div.ds-w-full.ds-bg-fill-content-prime.ds-overflow-hidden.ds-rounded-xl.ds-border.ds-border-line.ds-mb-4')
        player_section = all_divs.nth(i)
        team_sections.append({"team_name": team_name, "player_section": player_section})
    return team_sections

def fetch_player_links_with_teams(team_sections):
    player_links = []

    for section in team_sections:
        team_name = section["team_name"]
        team_name = next((team.name for team in IPLTeam if team.value == team_name), team_name)
        player_section = section["player_section"]
        players = player_section.locator('a[href^="/cricketers/"]')

        for player_index in range(players.count()):
            try:
                player_name = players.nth(player_index).inner_text().strip()
                player_link = players.nth(player_index).get_attribute("href")
                player_id_match = re.search(r'/cricketers/.*?-(\d+)', player_link)
                if player_id_match:
                    player_id = player_id_match.group(1)
                    player_links.append({
                        "name": player_name,
                        "link": f"https://www.espncricinfo.com{player_link}",
                        "id": player_link.replace('/cricketers/', ''),
                        "team": team_name
                    })
            except Exception as e:
                print(f"Error fetching player link for team {team_name}: {e}")

    return player_links

def fetch_and_save_player_stats(player_links):
    downloader = BattingHistoryDownloader()
    batting_stats = []
    bowling_stats = []

    for player in player_links:
        player_id = player["id"]
        player_name = player["name"]
        player_team = player["team"]
        print(f"Fetching IPL stats for {player_name} (ID: {player_id})...")

        try:
            batting_df, bowling_df = downloader.get_ipl_batting_stats(player_id)

            if batting_df is not None and not batting_df.empty:
                for _, row in batting_df.iterrows():
                    batting_stats.append({
                        "player_name": player_name,
                        "player_team": player_team,
                        "matches": row.get("Matches", ""),
                        "innings": row.get("Innings", ""),
                        "not_outs": row.get("Not Outs", ""),
                        "runs": row.get("Runs", ""),
                        "balls": row.get("Balls Faced", ""),
                        "fours": row.get("Fours", ""),
                        "sixes": row.get("Sixes", ""),
                        "average": row.get("Average", ""),
                        "strike_rate": row.get("Strike Rate", "")
                    })

            if bowling_df is not None and not bowling_df.empty:
                for _, row in bowling_df.iterrows():
                    bowling_stats.append({
                        "player_name": player_name,
                        "player_team": player_team,
                        "matches": row.get("Matches", ""),
                        "innings": row.get("Innings", ""),
                        "overs": row.get("Overs", ""),
                        "maidens": row.get("Maidens", ""),
                        "runs_conceded": row.get("Runs Conceded", ""),
                        "wickets": row.get("Wickets", ""),
                        "average": row.get("Average", ""),
                        "economy": row.get("Economy", ""),
                        "strike_rate": row.get("Strike Rate", "")
                    })

        except Exception as e:
            print(f"Error fetching stats for {player_name}: {e}")

    save_to_csv_players(batting_stats, "all_players_ipl_batting_stats.csv", is_batting=True)
    save_to_csv_players(bowling_stats, "all_players_ipl_bowling_stats.csv", is_batting=False)

def save_to_csv_players(data, filename, is_batting=True):
    if is_batting:
        fieldnames = ["player_name", "player_team", "matches", "innings", "not_outs", "runs", 
                      "balls", "fours", "sixes", "average", "strike_rate"]
    else:
        fieldnames = ["player_name", "player_team", "matches", "innings", "overs", "maidens", 
                      "runs_conceded", "wickets", "average", "economy", "strike_rate"]

    with open(filename, "w", newline='') as outfile:
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()
        for row in data:
            writer.writerow(row)
    print(f"Data saved to {filename}")

def get_venue_stats(page):
    venue_selector = 'a[href*="cricket-grounds"]'
    venue_element = page.locator(venue_selector)
    venue_info = venue_element.inner_text().strip()
    venue_link = venue_element.get_attribute("href")
    print(f"Venue Info: {venue_info}, Link: {venue_link}")
    return venue_info

def scrape_all_overs_data(page, venue_stats):
    slider_selector = "div.ds-absolute.ds-w-0\\.5.ds-h-\\[200px\\]"
    page.wait_for_selector(slider_selector, timeout=30000)
    slider = page.locator(slider_selector)
    graph_selector = "div.ds-w-\\[300px\\].ds-relative"
    graph_box = page.locator(graph_selector).bounding_box()

    if not graph_box:
        print("Graph bounding box not found!")
        return

    graph_x_start = graph_box["x"]
    graph_x_end = graph_x_start + graph_box["width"]
    graph_y_center = graph_box["y"] + graph_box["height"] / 2
    total_overs = 20
    steps_per_over = 10
    step_size = (graph_x_end - graph_x_start) / (total_overs * steps_per_over)
    all_overs_data = []

    for step in range(total_overs * steps_per_over + 1):
        current_x = graph_x_start + step * step_size
        slider.hover()
        page.mouse.down()
        page.mouse.move(current_x, graph_y_center)
        page.mouse.up()
        over_details = page.locator("div.ds-px-4.ds-pb-3 p").inner_text()
        all_live_forecasts = page.locator("div.ds-px-4.ds-pb-3 span").all_inner_texts()
        win_probabilities = page.locator("div.ds-text-tight-s.ds-font-bold.ds-ml-1").all_inner_texts()

        data = {
            "over_details": over_details,
            "live_forecasts": ";".join(all_live_forecasts),
            "win_probabilities": ";".join(win_probabilities),
            "venue": venue_stats
        }
        all_overs_data.append(data)

    with open('all_overs_data.csv', 'w', newline='') as outfile:
        fieldnames = ["over_details", "live_forecasts", "win_probabilities", "venue"]
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()
        for data in all_overs_data:
            writer.writerow(data)
    print("Scraped data written to all_overs_data.csv")

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        url = "https://www.espncricinfo.com/series/ipl-2020-21-1210595/mumbai-indians-vs-chennai-super-kings-1st-match-1216492/full-scorecard"
        page.goto(url)
        page.wait_for_timeout(30000)

        venue_stats = get_venue_stats(page)
        scrape_all_overs_data(page, venue_stats)

        team_sections = fetch_team_names_and_player_sections(page)
        player_links = fetch_player_links_with_teams(team_sections)
        fetch_and_save_player_stats(player_links)

        browser.close()

if __name__ == "__main__":
    main()
