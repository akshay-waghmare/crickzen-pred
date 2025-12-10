from playwright.sync_api import sync_playwright
from ipl_scraper.espnscraper import fetch_team_names_and_player_sections, fetch_player_links_with_teams, fetch_and_save_player_stats

def test_player_stats():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        # URL of the page
        url = "https://www.espncricinfo.com/series/ipl-2020-21-1210595/mumbai-indians-vs-chennai-super-kings-1st-match-1216492/full-scorecard"
        page.goto(url)
        page.wait_for_timeout(30000)

        # Get team sections
        team_sections = fetch_team_names_and_player_sections(page)
        
        # Fetch all player links
        player_links = fetch_player_links_with_teams(team_sections)

        print(f"Found {len(player_links)} players. Fetching their stats...")

        # Fetch and save player stats
        fetch_and_save_player_stats(player_links)

        browser.close()

if __name__ == "__main__":
    test_player_stats()