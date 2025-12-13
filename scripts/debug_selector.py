from playwright.sync_api import sync_playwright
import time

def debug_selectors(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080}
        )
        page = context.new_page()
        print(f"Opening {url}...")
        page.goto(url, timeout=60000)
        time.sleep(5)  # Wait for load

        print(f"Page Title: {page.title()}")
        
        # Dump HTML to file
        with open("page_dump.html", "w", encoding="utf-8") as f:
            f.write(page.content())
        print("Dumped HTML to page_dump.html")

        print("\n--- Searching for Commentary ---")
        
        # Try a few broad selectors
        selectors = [
            "div.ds-text-tight-m.ds-font-regular.ds-flex", # Common container
            "div[class*='ds-hover-parent']", # Hover parent often used for rows
            "span.ds-text-tight-s.ds-font-regular.ds-text-typo-mid1" # Often the ball number
        ]

        for sel in selectors:
            count = page.locator(sel).count()
            print(f"Selector '{sel}': found {count} elements")
            if count > 0:
                print(f"First element text: {page.locator(sel).first.inner_text()[:100]}")

        # Dump some HTML to analyze
        print("\n--- HTML Dump of potential commentary area ---")
        # Look for a container that might hold commentary
        # Usually commentary is in a large column.
        
        # Let's try to find a ball number and see its parents
        ball_num = page.locator("text=/^\\d+\\.\\d+$/").first
        if ball_num.count() > 0:
            print(f"Found ball number: {ball_num.inner_text()}")
            parent = ball_num.locator("..").locator("..").locator("..") # Go up a few levels
            print(f"Grandparent HTML: {parent.inner_html()[:500]}")
            print(f"Grandparent Classes: {parent.get_attribute('class')}")
        else:
            print("Could not find any ball number (e.g. '14.2') on the page.")

        browser.close()

if __name__ == "__main__":
    debug_selectors("https://www.espncricinfo.com/series/nepal-premier-league-2025-26-1510976/kathmandu-gorkhas-npl-vs-lumbini-lions-npl-eliminator-1511006/live-cricket-score")
