"""
Fast Poll Service for sub-second sV3 updates.
Uses network interception to capture sV3 responses from persistent pages.

The crex.com page naturally polls sV3 data from api-v1.com every few seconds.
We intercept those responses and push updates immediately.

Feature: 007-fast-updates
"""
import asyncio
import json
import logging
import time
from dataclasses import dataclass
from typing import Dict, Optional, Any, Callable, Awaitable
from playwright.async_api import Page, Response

logger = logging.getLogger(__name__)


@dataclass
class PollResult:
    """Result of a poll operation."""
    success: bool
    data: Optional[Dict[str, Any]]
    latency_ms: int
    source: str  # 'intercept' or 'cache'
    error: Optional[str] = None


class FastPollService:
    """
    Intercepts sV3 data from persistent pages via network monitoring.
    
    The crex.com page's JavaScript naturally polls sV3 data from api-v1.com.
    This service attaches a response listener to capture those responses
    and immediately pushes updates.
    
    Key insight: We DON'T need to fetch - we just listen!
    The page is already polling, we just intercept and forward.
    """
    
    def __init__(
        self,
        poll_interval_ms: int = 1000,  # Not used for active polling, kept for compat
        timeout_ms: int = 5000,
    ):
        self._timeout = timeout_ms
        self._active_pages: Dict[str, Page] = {}
        self._last_data: Dict[str, Dict] = {}
        self._callbacks: Dict[str, Callable[[str, Dict], Awaitable[None]]] = {}
        self._stats = {
            "total_intercepts": 0,
            "successful_intercepts": 0,
            "failed_intercepts": 0,
            "data_changes": 0,
            "avg_latency_ms": 0,
        }
        logger.info(f"[FASTPOLL] Initialized network intercept mode")
    
    async def attach_to_page(
        self, 
        page: Page, 
        match_id: str,
        match_url: str,
        on_data: Callable[[str, Dict[str, Any]], Awaitable[None]],
    ):
        """
        Attach sV3 response interception to a page.
        
        Args:
            page: Open Playwright page showing a match
            match_id: Match ID for callbacks
            match_url: Original match URL for reference
            on_data: Async callback when sV3 data arrives - (match_url, data)
        """
        if match_id in self._active_pages:
            logger.debug(f"[FASTPOLL] Already attached to {match_id}")
            return
        
        self._active_pages[match_id] = page
        self._callbacks[match_id] = on_data
        
        # Create response handler for this page
        async def handle_response(response: Response):
            await self._on_response(response, match_id, match_url)
        
        page.on("response", handle_response)
        logger.info(f"[FASTPOLL] Attached network interceptor to {match_id}")
    
    async def _on_response(self, response: Response, match_id: str, match_url: str):
        """Handle intercepted response - check for sV3 data."""
        try:
            url = response.url
            
            # Check if this is an sV3 response
            if "sV3" not in url:
                return
            
            start_time = time.time()
            self._stats["total_intercepts"] += 1
            
            # Check status
            if response.status != 200:
                logger.debug(f"[FASTPOLL] sV3 non-200: {response.status} for {match_id}")
                return
            
            # Parse JSON
            try:
                data = await response.json()
            except Exception as e:
                logger.warning(f"[FASTPOLL] Failed to parse sV3 JSON for {match_id}: {e}")
                self._stats["failed_intercepts"] += 1
                return
            
            latency_ms = int((time.time() - start_time) * 1000)
            self._update_latency_stats(latency_ms)
            self._stats["successful_intercepts"] += 1
            
            # Check if data changed
            if self._data_changed(match_id, data):
                self._stats["data_changes"] += 1
                self._last_data[match_id] = data
                
                # Fire callback
                callback = self._callbacks.get(match_id)
                if callback:
                    try:
                        await callback(match_url, data)
                        logger.debug(f"[FASTPOLL] Pushed sV3 update for {match_id} in {latency_ms}ms")
                    except Exception as e:
                        logger.error(f"[FASTPOLL] Callback error for {match_id}: {e}")
            else:
                logger.debug(f"[FASTPOLL] sV3 unchanged for {match_id}")
                
        except Exception as e:
            logger.error(f"[FASTPOLL] Error processing sV3 response for {match_id}: {e}")
            self._stats["failed_intercepts"] += 1
    
    def _data_changed(self, match_id: str, new_data: Dict) -> bool:
        """Check if data has changed since last intercept."""
        last = self._last_data.get(match_id)
        if last is None:
            return True
        
        # Quick check: compare key fields that typically change
        # This is faster than full JSON comparison
        try:
            # Common changing fields in sV3
            for key in ['sc', 'ov', 'bt', 'ws', 'rb']:
                if last.get(key) != new_data.get(key):
                    return True
            return False
        except Exception:
            # Fallback to full comparison
            try:
                return json.dumps(last, sort_keys=True) != json.dumps(new_data, sort_keys=True)
            except Exception:
                return True
    
    def _update_latency_stats(self, latency_ms: int):
        """Update rolling average latency."""
        total = self._stats["total_intercepts"]
        old_avg = self._stats["avg_latency_ms"]
        self._stats["avg_latency_ms"] = (old_avg * 0.9 + latency_ms * 0.1) if total > 1 else latency_ms
    
    def detach(self, match_id: str):
        """Stop intercepting for a match."""
        self._active_pages.pop(match_id, None)
        self._callbacks.pop(match_id, None)
        self._last_data.pop(match_id, None)
        logger.info(f"[FASTPOLL] Detached from {match_id}")
    
    async def stop_all(self):
        """Stop all interception."""
        match_ids = list(self._active_pages.keys())
        for match_id in match_ids:
            self.detach(match_id)
        logger.info("[FASTPOLL] All interceptors stopped")
    
    def get_stats(self) -> Dict:
        """Get interception statistics."""
        return {
            **self._stats,
            "active_pages": len(self._active_pages),
            "cached_matches": len(self._last_data),
        }
    
    # Legacy compatibility methods
    async def poll_once(self, page: Page, match_id: str) -> PollResult:
        """
        Legacy method - not used in intercept mode.
        Returns cached data if available.
        """
        cached = self._last_data.get(match_id)
        if cached:
            return PollResult(
                success=True,
                data=cached,
                latency_ms=0,
                source="cache",
            )
        return PollResult(
            success=False,
            data=None,
            latency_ms=0,
            source="none",
            error="No cached data - waiting for intercept",
        )
    
    async def poll_with_diff(self, page: Page, match_id: str) -> Optional[Dict[str, Any]]:
        """Legacy method - returns None, data comes via callbacks."""
        return None
    
    async def start_continuous_poll(
        self,
        page: Page,
        match_id: str,
        on_data: Callable[[Dict[str, Any]], Awaitable[None]],
        on_error: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> asyncio.Task:
        """Legacy method - use attach_to_page instead."""
        logger.warning(f"[FASTPOLL] start_continuous_poll is deprecated, use attach_to_page")
        return asyncio.create_task(asyncio.sleep(0))
    
    async def stop_continuous_poll(self, match_id: str):
        """Legacy method - use detach instead."""
        self.detach(match_id)
    
    def clear_last_data(self, match_id: str):
        """Clear cached data for a match."""
        self._last_data.pop(match_id, None)
