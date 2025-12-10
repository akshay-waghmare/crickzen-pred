#!/usr/bin/env python3
"""Test a single match URL to see if it loads"""

from playwright.sync_api import sync_playwright

def test_match_url():
    # URL from our earlier test
    test_url = "https://crex.com/scoreboard/VB7/1VP/1st-T20/V/R/nz-vs-wi-1st-t20-west-indies-tour-of-new-zealand-2025/live"
    
    print(f"Testing URL: {test_url}")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        
        try:
            print("Navigating to URL...")
            response = page.goto(test_url, timeout=30000, wait_until="domcontentloaded")
            print(f"Response status: {response.status}")
            print(f"Final URL: {page.url}")
            print(f"Page title: {page.title()}")
            
            # Wait to see the page
            input("\nPress Enter to close...")
            
        except Exception as e:
            print(f"Error: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    test_match_url()
