"""
Async Browser Pool for managing Playwright browser contexts.
Handles lifecycle, concurrency limits, and resource cleanup.
"""

import asyncio
import logging
from typing import Optional, List, AsyncGenerator
from contextlib import asynccontextmanager
from playwright.async_api import async_playwright, Browser, BrowserContext, Playwright, Error as PlaywrightError

from .config import get_settings

logger = logging.getLogger(__name__)

class AsyncBrowserPool:
    """
    Manages a pool of Playwright browser contexts with concurrency limits.
    """

    def __init__(self):
        self.settings = get_settings()
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._active_contexts: List[BrowserContext] = []
        self._lock: Optional[asyncio.Lock] = None
        self._shutting_down = False
        self._context_pool: List[BrowserContext] = [] # Reusable contexts

    async def setup(self):
        """Initialize the browser pool."""
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self.settings.concurrency_cap)
        if self._lock is None:
            self._lock = asyncio.Lock()

        if self._playwright and self._browser:
            return

        logger.info("Initializing AsyncBrowserPool...")
        if not self._playwright:
            self._playwright = await async_playwright().start()
        
        # Launch browser with optimized args
        launch_args = [
            "--disable-gpu",
            "--disable-dev-shm-usage",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-extensions",
        ]
        
        if not self._browser:
            self._browser = await self._playwright.chromium.launch(
                headless=True,  # Always headless in prod
                args=launch_args
            )
        logger.info("Browser launched successfully.")

    async def _create_context(self) -> BrowserContext:
        """Create a new configured context."""
        if not self._browser:
            await self.setup()
            
        try:
            context = await self._browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
                java_script_enabled=True
            )
            # Block resources to save bandwidth
            await context.route("**/*.{png,jpg,jpeg,gif,webp,svg,css,woff,woff2}", lambda route: route.abort())
            return context
        except Exception as e:
            logger.error(f"Failed to create context: {e}")
            # Invalidate browser so it gets recreated
            if self._browser:
                try:
                    await self._browser.close()
                except Exception:
                    pass
                self._browser = None
            raise

    @asynccontextmanager
    async def get_context(self) -> AsyncGenerator[BrowserContext, None]:
        """
        Acquire a browser context from the pool.
        Blocks if concurrency limit is reached.
        Reuses contexts if available.
        """
        if self._shutting_down:
            raise RuntimeError("Browser pool is shutting down")

        if not self._browser:
            await self.setup()

        async with self._semaphore:
            # Try to get from pool
            context = None
            async with self._lock:
                if self._context_pool:
                    context = self._context_pool.pop()
            
            if not context:
                try:
                    context = await self._create_context()
                except Exception:
                    # Retry once if creation failed (likely due to browser crash)
                    logger.warning("Context creation failed, retrying...")
                    context = await self._create_context()
            
            async with self._lock:
                self._active_contexts.append(context)
            
            success = False
            try:
                yield context
                success = True
            except Exception as e:
                logger.warning(f"Context usage failed: {e}")
                # If it's a critical error, we might want to recycle the whole pool
                if "Target closed" in str(e) or "Connection closed" in str(e):
                     logger.error("Browser connection lost, invalidating browser and playwright.")
                     if self._browser:
                         try:
                             await self._browser.close()
                         except Exception:
                             pass
                         self._browser = None
                     
                     # Restart Playwright as well to ensure driver is clean
                     if self._playwright:
                         try:
                             await self._playwright.stop()
                         except Exception:
                             pass
                         self._playwright = None
                raise
            finally:
                async with self._lock:
                    if context in self._active_contexts:
                        self._active_contexts.remove(context)
                    
                    # Return to pool if success, not shutting down and pool not full
                    if success and not self._shutting_down and len(self._context_pool) < self.settings.concurrency_cap:
                        # Clear cookies/storage before reuse? 
                        # For now, we just reuse. In a real scraper, we might want to clear cookies.
                        try:
                            await context.clear_cookies()
                            self._context_pool.append(context)
                        except Exception:
                            # If clearing cookies fails, discard context
                            try:
                                await context.close()
                            except:
                                pass
                    else:
                        # Close if pool full, shutting down, or usage failed
                        try:
                            await context.close()
                        except Exception as e:
                            logger.debug(f"Error closing context: {e}")

    async def shutdown(self):
        """Gracefully shutdown the browser pool."""
        logger.info("Shutting down AsyncBrowserPool...")
        self._shutting_down = True
        
        async with self._lock:
            # Close all active contexts
            for context in self._active_contexts:
                try:
                    await context.close()
                except Exception as e:
                    logger.warning(f"Error closing context during shutdown: {e}")
            self._active_contexts.clear()
            
            # Close pooled contexts
            for context in self._context_pool:
                try:
                    await context.close()
                except Exception as e:
                    logger.warning(f"Error closing pooled context during shutdown: {e}")
            self._context_pool.clear()

        if self._browser:
            await self._browser.close()
            self._browser = None
            
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
            
        logger.info("AsyncBrowserPool shutdown complete.")

    async def recycle(self):
        """
        Recycle the browser process.
        Closes all contexts and restarts the browser.
        """
        logger.warning("Recycling browser pool...")
        async with self._lock:
            # Close all active contexts immediately
            for context in self._active_contexts:
                try:
                    await context.close()
                except Exception as e:
                    logger.error(f"Error closing context during recycle: {e}")
            self._active_contexts.clear()
            
            # Close pooled contexts
            for context in self._context_pool:
                try:
                    await context.close()
                except Exception as e:
                    logger.error(f"Error closing pooled context during recycle: {e}")
            self._context_pool.clear()

        if self._browser:
            try:
                await self._browser.close()
            except Exception as e:
                logger.error(f"Error closing browser during recycle: {e}")
            self._browser = None

        # Re-setup will happen on next get_context call or we can do it now
        # Doing it now to ensure readiness
        try:
            await self.setup()
            logger.info("Browser pool recycled successfully.")
        except Exception as e:
            logger.error(f"Failed to recycle browser pool: {e}")
            raise
