import json
from playwright.sync_api import sync_playwright
import logging
from dataclasses import dataclass, asdict

# Configure logging
logging.basicConfig(
    filename='crex_scraper.log',
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s'
)

# Helper function to extract text from selectors
def get_inner_text(page, selector, default_value):
    try:
        element = page.query_selector(selector)
        return element.inner_text().strip() if element else default_value
    except Exception as e:
        logging.error(f"Error retrieving text from {selector}: {e}")
        return default_value

@dataclass
class MatchInfo:
    match_date: str
    venue: str
    match_name: str
    team_form: dict
    team_comparison: dict
    venue_stats: dict
    playing_xi: dict
    toss_info: str

def scrape_match_info(url):
    logging.info(f"Scraping match info page: {url}")
    with sync_playwright() as p:
        # Set headless=False for debugging
        browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'])
        context = browser.new_context()
        page = context.new_page()

        # Define console handler to capture console messages from the page
        def on_console(msg):
            if msg.type == 'error':
                for arg in msg.args:
                    text = arg.json_value()
                    logging.error(f"Console error: {text}")
                    print(f"Console error: {text}")  # Optional: Print to stdout
            elif msg.type == 'warning':
                for arg in msg.args:
                    text = arg.json_value()
                    logging.warning(f"Console warning: {text}")
                    print(f"Console warning: {text}")  # Optional: Print to stdout
            else:
                for arg in msg.args:
                    text = arg.json_value()
                    logging.info(f"Console {msg.type}: {text}")
                    print(f"Console {msg.type}: {text}")  # Optional: Print to stdout

        # Attach console handler
        page.on("console", on_console)

        try:
            # Navigate to the URL
            page.goto(url, timeout=60000)

            # Scrape toss information
            toss_info = get_inner_text(page, '.toss-wrap p', 'No toss information')

            # Scrape match details (date, venue, teams)
            match_date = get_inner_text(page, '.match-date', 'No match date')
            venue = get_inner_text(page, '.match-venue', 'No venue info')
            match_name = get_inner_text(page, '.s-name', 'No match name')

            # Scrape team form
            team_form = page.evaluate('''() => {
                const teamsData = {};

                // Query for all team sections containing the team forms
                const teamSections = document.querySelectorAll('.format-match-exp');

                console.log(`Number of team sections found: ${teamSections.length}`);

                teamSections.forEach(section => {
                    const teamId = section.id || 'Unknown Team';
                    console.log(`Processing Team ID: ${teamId}`);
                    const last_matches = [];

                    // Find all match cards within the team section
                    const match_cards = section.querySelectorAll('.format-card-wrap');
                    console.log(`Found ${match_cards.length} match cards for team ${teamId}`);

                    match_cards.forEach((card, cardIdx) => {
                        console.log(`Processing Match Card ${cardIdx + 1} for team ${teamId}`);
                        const teams = [];

                        // Extract team details
                        const team_details = card.querySelectorAll('.form-team-detail');
                        team_details.forEach((teamDetail, detailIdx) => {
                            const teamName = teamDetail.querySelector('.team-name')?.innerText.trim() || 'Unknown';
                            console.log(`Team ${detailIdx + 1} Name: ${teamName}`);

                            // Extract scores and overs, filtering out ampersands
                            const innings_scores = teamDetail.querySelectorAll('.team-score');
                            const innings_overs = teamDetail.querySelectorAll('.team-over');

                            // Convert NodeLists to Arrays and filter out ampersands
                            const inningsScoresArray = Array.from(innings_scores).filter(el => el.innerText.trim() !== '&');
                            const inningsOversArray = Array.from(innings_overs).filter(el => el.innerText.trim() !== '&');

                            const scores = [];
                            inningsScoresArray.forEach((scoreElement, idx) => {
                                const score = scoreElement.innerText.trim();
                                const over = inningsOversArray[idx]?.innerText.trim() || 'N/A';
                                console.log(`Innings ${idx + 1} - Score: ${score}, Over: ${over}`);
                                scores.push({
                                    "team_score": score,
                                    "team_over": over
                                });
                            });

                            teams.push({
                                "team_name": teamName,
                                "innings": scores
                            });
                        });

                        // Extract match info
                        const match_info = card.querySelector('.form-match-no');
                        const match_name = match_info.querySelector('.match-name')?.innerText.trim() || 'Unknown Match';
                        const series_name = match_info.querySelector('.series-name')?.innerText.trim() || 'Unknown Series';

                        // Extract result
                        const resultElement = card.querySelector('.win.match, .loss.match, .draw.match');
                        const result = resultElement?.innerText.trim() || 'Unknown Result';

                        console.log(`Match Name: ${match_name}, Series Name: ${series_name}, Result: ${result}`);

                        last_matches.push({
                            "match_name": match_name,
                            "series_name": series_name,
                            "teams": teams,
                            "result": result
                        });
                    });

                    // Store team form data in the final result
                    teamsData[teamId] = last_matches;
                });

                return teamsData;
            }''') if page.query_selector('.format-match-exp') else {}

            # Scrape team comparison
            team_comparison = page.evaluate('''() => {
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
            }''') if page.query_selector('#table tbody tr') else {}

            # Scrape venue stats
            venue_stats = page.evaluate('''() => {
                const stats = {};
                stats.matches = document.querySelector('.match-count')?.innerText.trim() || 'No data';
                stats.win_bat_first = document.querySelector('.win-bat-first .match-win-per')?.innerText.trim() || 'No data';
                stats.win_bowl_first = document.querySelector('.win-bowl-first .match-win-per')?.innerText.trim() || 'No data';
                stats.avg_1st_inns = document.querySelector('.venue-avg-sec-inn .venue-avg-val')?.innerText.trim() || 'No data';
                stats.avg_2nd_inns = document.querySelector('.venue-avg-wrap .venue-avg-val')?.innerText.trim() || 'No data';
                return stats;
            }''') if page.query_selector('.match-count') else {}

            # Scrape playing XI for both teams
            playing_xi = {}
            buttons = page.query_selector_all('.playingxi-button')
            for button in buttons:
                team_name = button.inner_text().strip()
                button.click()
                page.wait_for_selector('.playingxi-card-row')  # Ensure playing XI loads
                players = page.evaluate('''() => {
                    const playersList = [];
                    document.querySelectorAll('.playingxi-card-row').forEach(player => {
                        const playerName = player.querySelector('.player-name')?.innerText.trim() || 'Unknown Player';
                        const playerRole = player.querySelector('.bat-ball-type')?.innerText.trim() || 'Unknown Role';
                        playersList.push({ playerName, playerRole });
                    });
                    return playersList;
                }''')
                playing_xi[team_name] = players

            # Logging scraped data
            match_info_dict = asdict(MatchInfo(
                match_date=match_date,
                venue=venue,
                match_name=match_name,
                team_form=team_form,
                team_comparison=team_comparison,
                venue_stats=venue_stats,
                playing_xi=playing_xi,
                toss_info=toss_info
            ))

            logging.info("Match Info Data: " + json.dumps(match_info_dict, indent=4))

            # Print the scraped data
            # print(json.dumps(match_info_dict, indent=4))

            # Return scraped data as a dataclass
            return match_info_dict

        except Exception as e:
            logging.error(f"Error scraping match info page: {e}")
            print(f"Error scraping match info page: {e}")
            return {}

        finally:
            if browser:
                browser.close()
                logging.info("Browser closed after scraping match info page.")

# Example usage
if __name__ == "__main__":
    match_info_url = "https://crex.live/scoreboard/R1V/1OC/4th-Match/19/70/can-vs-nep-4th-match-canada-t20i-triseries-2024/info"
    scraped_data = scrape_match_info(match_info_url)
    # Print the final data
    # print(json.dumps(scraped_data, indent=4))
