#!/usr/bin/env python3
"""Test script to check if crex.com is accessible and what URLs are available."""

from playwright.sync_api import sync_playwright
import sys

def test_crex_domain():
    print("Testing crex.com domain...")
    
    with sync_playwright() as p:
        try:
            print("Launching browser...")
            browser = p.chromium.launch(headless=False)
            page = browser.new_page()
            
            # Try crex.com
            print("Navigating to https://crex.com...")
            response = page.goto("https://crex.com", timeout=30000, wait_until="networkidle")
            print(f"Response status: {response.status}")
            print(f"Final URL: {page.url}")
            
            # Wait a bit for content to load
            page.wait_for_timeout(5000)
            
            # Check for live-card elements
            live_cards = page.query_selector_all("div.live-card")
            print(f"\nFound {len(live_cards)} live-card elements")
            
            if live_cards:
                # Try to extract URLs
                live_divs = page.query_selector_all("div.live-card .live")
                print(f"Found {len(live_divs)} live match indicators")
                
                urls = []
                for i, live_div in enumerate(live_divs):
                    try:
                        parent = live_div.query_selector(":scope >> xpath=..")
                        grandparent = parent.query_selector(":scope >> xpath=..")
                        sibling = grandparent.query_selector(":scope >> xpath=following-sibling::*[1]")
                        url = sibling.get_attribute('href')
                        urls.append(url)
                        print(f"  Match {i+1}: {url}")
                    except Exception as e:
                        print(f"  Match {i+1}: Error - {e}")
                
                print(f"\nTotal URLs extracted: {len(urls)}")
            else:
                print("\nNo live-card elements found. Checking page title...")
                print(f"Page title: {page.title()}")
                
                # Take a screenshot for debugging
                page.screenshot(path="crex_com_test.png")
                print("Screenshot saved as crex_com_test.png")
            
            input("\nPress Enter to close browser...")
            browser.close()
            
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    return True

if __name__ == "__main__":
    success = test_crex_domain()
    sys.exit(0 if success else 1)
