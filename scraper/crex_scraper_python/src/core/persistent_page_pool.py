"""
Persistent Page Pool for fast sV3 polling.
Keeps browser pages open for live matches.

Feature: 007-fast-updates
"""
import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Dict, Optional, Set, Callable, Awaitable
from playwright.async_api import Page, BrowserContext

logger = logging.getLogger(__name__)


@dataclass
class PageEntry:
    """Metadata for a persistent page."""
    page: Page
    context: BrowserContext
    created_at: float
    last_used_at: float
    url: str
    error_count: int = 0


class PersistentPagePool:
    """
    Manages persistent browser pages for live matches.
    
    Each live match gets its own page that stays open until:
    - Match completes
    - Page becomes stale (errors, memory)
    - Max age exceeded
    - Manual cleanup triggered
    
    Resource limits:
    - Max pages: configurable (default 15)
    - Max age: 2 hours (force refresh)
    - Error threshold: recycle after N errors
    
    Benefits over page-per-scrape:
    - Update latency: 20-30s → 1-3s
    - Reduced PID churn (fewer open/close cycles)
    - More stable resource usage
    """
    
    def __init__(
        self, 
        max_pages: int = 15, 
        max_age_seconds: int = 7200,
        max_errors: int = 5,
    ):
        self._entries: Dict[str, PageEntry] = {}
        self._lock = asyncio.Lock()
        self._max_pages = max_pages
        self._max_age = max_age_seconds
        self._max_errors = max_errors
        logger.info(f"[POOL] Initialized with max_pages={max_pages}, max_age={max_age_seconds}s")
    
    async def get_or_create(
        self, 
        match_id: str, 
        context: BrowserContext,
        url: str,
        setup_fn: Optional[Callable[[Page], Awaitable[None]]] = None,
    ) -> Page:
        """
        Get existing page for match or create a new one.
        
        Args:
            match_id: Unique match identifier
            context: Browser context to create page in
            url: URL to navigate to (only used if creating new page)
            setup_fn: Optional async function to call after page creation
                     Signature: async (page: Page) -> None
        
        Returns:
            Page ready for polling
        """
        async with self._lock:
            # Check if page exists and is valid
            if match_id in self._entries:
                entry = self._entries[match_id]
                
                # Check if page is still valid
                if not entry.page.is_closed():
                    age = time.time() - entry.created_at
                    
                    # Check age limit
                    if age < self._max_age:
                        # Check error threshold
                        if entry.error_count < self._max_errors:
                            entry.last_used_at = time.time()
                            logger.debug(f"[POOL] Reusing page for {match_id} (age: {age:.0f}s, errors: {entry.error_count})")
                            return entry.page
                        else:
                            logger.info(f"[POOL] Page for {match_id} exceeded error threshold ({entry.error_count}), recreating")
                    else:
                        logger.info(f"[POOL] Page for {match_id} expired (age: {age:.0f}s), recreating")
                else:
                    logger.info(f"[POOL] Page for {match_id} was closed, recreating")
                
                # Page invalid, clean up
                await self._cleanup_entry(match_id)
            
            # Check pool size limit
            if len(self._entries) >= self._max_pages:
                # Evict oldest/least recently used page
                await self._evict_one()
            
            # Create new page
            logger.info(f"[POOL] Creating new page for {match_id}")
            page = await context.new_page()
            
            try:
                # Navigate to URL
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                
                # Wait for initial content to load
                try:
                    await page.wait_for_selector(".match-header", timeout=5000)
                except Exception:
                    pass  # Continue even if selector not found
                
                # Run setup function if provided
                if setup_fn:
                    await setup_fn(page)
                
                # Store entry
                now = time.time()
                self._entries[match_id] = PageEntry(
                    page=page,
                    context=context,
                    created_at=now,
                    last_used_at=now,
                    url=url,
                    error_count=0,
                )
                
                logger.info(f"[POOL] Page created for {match_id}. Pool size: {len(self._entries)}")
                return page
                
            except Exception as e:
                # Clean up on failure
                if not page.is_closed():
                    await page.close()
                logger.error(f"[POOL] Failed to create page for {match_id}: {e}")
                raise
    
    async def _evict_one(self):
        """Evict the oldest/least recently used page."""
        if not self._entries:
            return
        
        # Find LRU entry
        lru_id = min(self._entries, key=lambda k: self._entries[k].last_used_at)
        logger.info(f"[POOL] Evicting LRU page: {lru_id}")
        await self._cleanup_entry(lru_id)
    
    async def _cleanup_entry(self, match_id: str):
        """Clean up a single page entry."""
        if match_id not in self._entries:
            return
            
        entry = self._entries.pop(match_id)
        
        if not entry.page.is_closed():
            try:
                await entry.page.close()
                logger.debug(f"[POOL] Closed page for {match_id}")
            except Exception as e:
                logger.warning(f"[POOL] Error closing page {match_id}: {e}")
    
    def record_error(self, match_id: str):
        """Record an error for a page (for threshold tracking)."""
        if match_id in self._entries:
            self._entries[match_id].error_count += 1
            logger.debug(f"[POOL] Error count for {match_id}: {self._entries[match_id].error_count}")
    
    def reset_errors(self, match_id: str):
        """Reset error count for a page (on success)."""
        if match_id in self._entries:
            self._entries[match_id].error_count = 0
    
    async def remove(self, match_id: str):
        """Remove and close a match's page."""
        async with self._lock:
            await self._cleanup_entry(match_id)
            logger.info(f"[POOL] Removed page for {match_id}. Pool size: {len(self._entries)}")
    
    async def close_all(self):
        """Close all pages (for shutdown)."""
        async with self._lock:
            match_ids = list(self._entries.keys())
            for match_id in match_ids:
                await self._cleanup_entry(match_id)
            logger.info("[POOL] All pages closed")
    
    def get_page(self, match_id: str) -> Optional[Page]:
        """Get page for match if exists (without creating)."""
        if match_id in self._entries and not self._entries[match_id].page.is_closed():
            return self._entries[match_id].page
        return None
    
    @property
    def size(self) -> int:
        """Number of pages in pool."""
        return len(self._entries)
    
    @property
    def match_ids(self) -> Set[str]:
        """Set of match IDs with active pages."""
        return set(self._entries.keys())
    
    def is_page_active(self, match_id: str) -> bool:
        """Check if a page exists and is not closed."""
        if match_id not in self._entries:
            return False
        return not self._entries[match_id].page.is_closed()
    
    def get_stats(self) -> Dict:
        """Get pool statistics for monitoring."""
        now = time.time()
        ages = [now - e.created_at for e in self._entries.values()]
        errors = [e.error_count for e in self._entries.values()]
        
        return {
            "size": len(self._entries),
            "max_size": self._max_pages,
            "oldest_age_seconds": max(ages) if ages else 0,
            "avg_age_seconds": sum(ages) / len(ages) if ages else 0,
            "total_errors": sum(errors),
            "match_ids": list(self._entries.keys()),
        }
