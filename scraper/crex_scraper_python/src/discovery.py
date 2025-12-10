"""
Live Match Discovery Service.
Periodically scrapes the main page to find new live matches and syncs them with the backend.
"""

import asyncio
import logging
from typing import List, Optional

from playwright.async_api import Page

from .config import get_settings
from .browser_pool import AsyncBrowserPool
from .cricket_data_service import CricketDataService

logger = logging.getLogger(__name__)

class LiveMatchDiscoverer:
    """
    Discovers live matches from the main listing page.
    """

    def __init__(self, pool: AsyncBrowserPool):
        self.pool = pool
        self.settings = get_settings()
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self.base_url = "https://crex.com"

    async def start(self):
        """Start the discovery loop."""
        self._running = True
        self._task = asyncio.create_task(self._discovery_loop())
        logger.info("LiveMatchDiscoverer started.")

    async def stop(self):
        """Stop the discovery loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("LiveMatchDiscoverer stopped.")

    async def _discovery_loop(self):
        """Periodic discovery loop."""
        while self._running:
            try:
                await self._discover_and_sync()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Discovery loop error: {e}")
                print(f"[DISCOVERY] Error: {e}", flush=True)
                
                if "Connection closed" in str(e) or "Target closed" in str(e):
                    print("[DISCOVERY] Critical browser error detected. Pool should auto-recover on next cycle.", flush=True)
                
                # If we hit a connection error here, it might be transient or fatal for the browser
                # The pool should handle invalidation, but we should back off a bit
                await asyncio.sleep(10)
            
            # Wait for next cycle (default 60s)
            await asyncio.sleep(60)

    async def _discover_and_sync(self):
        """Scrape main page and sync live matches."""
        logger.info("Starting live match discovery...")
        print("[DISCOVERY] Starting live match discovery cycle...", flush=True)
        
        try:
            async with self.pool.get_context() as context:
                page = None
                try:
                    page = await context.new_page()
                    # Use the specific live matches URL
                    target_url = "https://crex.com/live-matches"
                    logger.info(f"Navigating to {target_url} for discovery...")
                    print(f"[DISCOVERY] Navigating to {target_url}...", flush=True)
                    
                    await page.goto(target_url, timeout=60000)
                    
                    # Wait for content to load - try multiple selectors
                    try:
                        # Try the list item selector from the provided HTML
                        await page.wait_for_selector("li.live-card", timeout=15000)
                        print("[DISCOVERY] Found li.live-card elements.", flush=True)
                    except Exception:
                        try:
                            # Fallback to div.live-card (legacy)
                            await page.wait_for_selector("div.live-card", timeout=5000)
                            print("[DISCOVERY] Found div.live-card elements.", flush=True)
                        except Exception:
                            logger.warning("No live cards found on live-matches page (timeout).")
                            print("[DISCOVERY] No live cards found (timeout).", flush=True)
                            await page.close()
                            return

                    # Extract URLs using robust logic based on provided HTML
                    urls = await page.evaluate("""() => {
                        const urls = [];
                        
                        // Strategy 1: Look for li.live-card > a (New structure)
                        const listItems = document.querySelectorAll('li.live-card a');
                        listItems.forEach(a => {
                            const href = a.getAttribute('href');
                            if (href && href.includes('/scoreboard/')) {
                                urls.push(href);
                            }
                        });
                        
                        // Strategy 2: Look for div.live-card > a (Legacy structure)
                        if (urls.length === 0) {
                            const divItems = document.querySelectorAll('div.live-card a');
                            divItems.forEach(a => {
                                const href = a.getAttribute('href');
                                if (href && href.includes('/scoreboard/')) {
                                    urls.push(href);
                                }
                            });
                        }

                        return urls;
                    }""")
                finally:
                    if page:
                        try:
                            await page.close()
                        except Exception:
                            pass
        except Exception as e:
            logger.error(f"Discovery failed: {e}")
            raise e
                
        # Clean and format URLs
        valid_urls = []
        for url in urls:
            if url:
                if not url.startswith("http"):
                    url = "https://crex.com" + url
                valid_urls.append(url)
        
        # Remove duplicates
        valid_urls = list(set(valid_urls))
        
        logger.info(f"Discovered {len(valid_urls)} live matches: {valid_urls}")
        print(f"[DISCOVERY] Found {len(valid_urls)} matches: {valid_urls}", flush=True)
        
        if valid_urls:
            # Sync with backend
            token = await asyncio.to_thread(CricketDataService.get_bearer_token)
            await asyncio.to_thread(CricketDataService.add_live_matches, valid_urls, token)
            logger.info("Synced live matches with backend.")
            print("[DISCOVERY] Synced with backend.", flush=True)
        else:
            print("[DISCOVERY] No valid URLs found to sync.", flush=True)

