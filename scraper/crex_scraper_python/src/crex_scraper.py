"""
Main Scraper Service.
Coordinates browser pool, scheduler, cache, and adapters.
"""

import asyncio
import logging
import signal
from typing import Optional, Dict, Any

from .config import get_settings
from .browser_pool import AsyncBrowserPool
from .scheduler import AsyncScheduler, ScrapeTask
from .cache import ScrapeCache
from .metrics import MetricsCollector
from .health import HealthGrader
from .adapters.registry import AdapterRegistry
from .cricket_data_service import CricketDataService
from .discovery import LiveMatchDiscoverer

logger = logging.getLogger(__name__)

class CrexScraperService:
    """
    High-reliability async scraper service.
    """

    def __init__(self):
        self.settings = get_settings()
        self.pool = AsyncBrowserPool()
        self.scheduler = AsyncScheduler()
        self.cache = ScrapeCache()
        self.metrics = MetricsCollector()
        self.health = HealthGrader()
        self.discovery = LiveMatchDiscoverer(self.pool)
        self._running = False
        self._workers = []
        self._monitor_task: Optional[asyncio.Task] = None
        self._poll_task: Optional[asyncio.Task] = None
        self._fast_poll_task: Optional[asyncio.Task] = None  # Persistent pages poll loop
        self._auth_token: Optional[str] = None
        
        # Persistent page pool and fast poll service (Feature 007 - Phase 2)
        self.persistent_page_pool = None
        self.fast_poll_service = None
        self._active_match_ids: set = set()  # Track matches being polled
        
        if self.settings.enable_persistent_pages:
            from .core.persistent_page_pool import PersistentPagePool
            from .core.fast_poll_service import FastPollService
            
            self.persistent_page_pool = PersistentPagePool(
                max_pages=self.settings.persistent_page_max_count,
                max_age_seconds=self.settings.persistent_page_max_age_seconds,
                max_errors=self.settings.persistent_page_max_errors,
            )
            self.fast_poll_service = FastPollService(
                poll_interval_ms=self.settings.fast_poll_interval_ms,
                timeout_ms=5000,
            )
            logger.info("Persistent pages feature enabled")
        
        # Fast update manager (Feature 007)
        # Must be initialized before registry so we can wire callbacks
        self.fast_update_manager = None
        on_sv3_callback = None
        on_sc4_callback = None
        
        if self.settings.enable_fast_updates:
            from .core.fast_update_manager import FastUpdateManager
            self.fast_update_manager = FastUpdateManager(
                metrics=self.metrics,
            )
            on_sv3_callback = self.fast_update_manager.on_sv3_update
            on_sc4_callback = self.fast_update_manager.on_sc4_update
        
        # Create registry with callbacks wired and auth token provider for immediate push
        # Also pass cache for localStorage caching (Feature 007)
        self.registry = AdapterRegistry(
            on_sv3_update=on_sv3_callback,
            on_sc4_update=on_sc4_callback,
            auth_token_provider=lambda: self._auth_token,  # Provide current token for immediate pushes
            cache=self.cache,  # Pass cache for localStorage caching
        )

    async def start(self):
        """Start the scraper service."""
        logger.info("Starting CrexScraperService...")
        self._running = True
        
        # Initialize components
        await self.cache.connect()
        await self.scheduler.setup()
        await self.pool.setup()
        
        # Fetch initial auth token
        try:
            self._auth_token = await asyncio.to_thread(CricketDataService.get_bearer_token)
            if self._auth_token:
                logger.info("Initial auth token obtained.")
            else:
                logger.warning("Failed to obtain initial auth token.")
        except Exception as e:
            logger.error(f"Auth token fetch failed: {e}")

        # Start worker tasks
        for i in range(self.settings.concurrency_cap):
            worker = asyncio.create_task(self._worker_loop(i))
            self._workers.append(worker)
            
        # Start monitor task
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        
        # Start poll task
        self._poll_task = asyncio.create_task(self._poll_loop())
        
        # Start fast poll task for persistent pages (Feature 007 - Phase 2)
        if self.persistent_page_pool and self.fast_poll_service:
            self._fast_poll_task = asyncio.create_task(self._fast_poll_loop())
            logger.info("Fast poll loop started for persistent pages")

        # Start discovery task
        await self.discovery.start()
        
        # Start fast update manager (Feature 007)
        if self.fast_update_manager:
            await self.fast_update_manager.start()
            logger.info("FastUpdateManager started.")
            
        logger.info(f"Started {len(self._workers)} worker tasks.")

    async def stop(self):
        """Stop the scraper service."""
        logger.info("Stopping CrexScraperService...")
        self._running = False
        
        if self._monitor_task:
            self._monitor_task.cancel()
        
        if self._poll_task:
            self._poll_task.cancel()
        
        if self._fast_poll_task:
            self._fast_poll_task.cancel()

        await self.discovery.stop()
        
        # Stop fast update manager (Feature 007)
        if self.fast_update_manager:
            await self.fast_update_manager.stop()
            logger.info("FastUpdateManager stopped.")
        
        # Stop persistent page pool and fast poll service (Feature 007 - Phase 2)
        if self.fast_poll_service:
            await self.fast_poll_service.stop_all()
            logger.info("FastPollService stopped.")
        if self.persistent_page_pool:
            await self.persistent_page_pool.close_all()
            logger.info("PersistentPagePool closed.")

        try:
            if self._monitor_task: await self._monitor_task
            if self._poll_task: await self._poll_task
            if self._fast_poll_task: await self._fast_poll_task
        except asyncio.CancelledError:
            pass

        await self.scheduler.shutdown()
        await self.pool.shutdown()
        await self.cache.close()
        
        # Cancel workers
        for worker in self._workers:
            worker.cancel()
        
        await asyncio.gather(*self._workers, return_exceptions=True)
        logger.info("CrexScraperService stopped.")

    async def _poll_loop(self):
        """Periodic backend polling loop."""
        logger.info("Backend poller started.")
        while self._running:
            try:
                # Refresh token if needed
                if not self._auth_token:
                     self._auth_token = await asyncio.to_thread(CricketDataService.get_bearer_token)

                matches = await asyncio.to_thread(CricketDataService.get_live_matches, self._auth_token)
                
                for match in matches:
                    # Handle both dict (from JSON) and string (if backend returns list of strings)
                    url = None
                    if isinstance(match, dict):
                        url = match.get('url') or match.get('matchUrl')
                    elif isinstance(match, str):
                        url = match
                    
                    if url:
                        # Use URL as ID or extract it. For now URL is unique enough.
                        match_id = url 
                        await self.submit_task(match_id, url, "LIVE")
                
                await asyncio.sleep(self.settings.polling_interval_seconds)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Poll loop error: {e}")
                await asyncio.sleep(5)

    async def _fast_poll_loop(self):
        """
        Fast poll loop for persistent pages (Feature 007 - Phase 2).
        
        For each live match:
        1. Get or create persistent page
        2. Poll sV3 data via JavaScript fetch
        3. Push data to backend immediately on change
        """
        logger.info("Fast poll loop started.")
        
        while self._running:
            try:
                if not self._auth_token:
                    await asyncio.sleep(1)
                    continue
                
                # Get current live matches from backend
                matches = await asyncio.to_thread(
                    CricketDataService.get_live_matches, 
                    self._auth_token
                )
                
                current_match_urls = set()
                
                for match in matches:
                    url = None
                    if isinstance(match, dict):
                        url = match.get('url') or match.get('matchUrl')
                    elif isinstance(match, str):
                        url = match
                    
                    if not url:
                        continue
                    
                    current_match_urls.add(url)
                    
                    # Extract match ID from URL
                    match_id = self._extract_match_id(url)
                    if not match_id:
                        continue
                    
                    # Check if we already have a persistent page with interceptor
                    if self.persistent_page_pool.is_page_active(match_id):
                        # Page already active with network interceptor - no action needed
                        # sV3 updates come automatically via response listener
                        continue
                    else:
                        # Create new persistent page and attach interceptor
                        try:
                            async with self.pool.get_context() as context:
                                page = await self.persistent_page_pool.get_or_create(
                                    match_id=match_id,
                                    context=context,
                                    url=url,
                                )
                                # Attach network interceptor - sV3 updates flow via callback
                                await self.fast_poll_service.attach_to_page(
                                    page=page,
                                    match_id=match_id,
                                    match_url=url,
                                    on_data=self._on_sv3_intercepted,
                                )
                                logger.info(f"[FASTPOLL] Attached interceptor to {match_id}")
                        except Exception as e:
                            logger.error(f"[FASTPOLL] Failed to create page for {match_id}: {e}")
                
                # Clean up pages for matches that are no longer live
                pool_match_ids = self.persistent_page_pool.match_ids.copy()
                for match_id in pool_match_ids:
                    # Match ID is like "crex:karb-vs-sial-final-quaid-e-azam-trophy-2025"
                    # URL contains the slug like "/karb-vs-sial-final-quaid-e-azam-trophy-2025/"
                    # Extract slug from match_id (remove "crex:" prefix)
                    slug = match_id.replace("crex:", "") if match_id.startswith("crex:") else match_id
                    still_live = any(slug in url for url in current_match_urls)
                    if not still_live:
                        logger.debug(f"[FASTPOLL] Match {match_id} slug={slug} not found in {len(current_match_urls)} URLs")
                        logger.info(f"[FASTPOLL] Match {match_id} no longer live, removing page")
                        self.fast_poll_service.detach(match_id)
                        await self.persistent_page_pool.remove(match_id)
                    else:
                        logger.debug(f"[FASTPOLL] Match {match_id} still live")
                
                # Log pool stats periodically
                if self.persistent_page_pool.size > 0:
                    stats = self.persistent_page_pool.get_stats()
                    poll_stats = self.fast_poll_service.get_stats()
                    logger.debug(f"[FASTPOLL] Pool: {stats}, Intercepts: {poll_stats}")
                
                # Wait before checking for new matches (interceptors run passively)
                await asyncio.sleep(5)  # Check for new/ended matches every 5s
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[FASTPOLL] Fast poll loop error: {e}")
                await asyncio.sleep(2)
    
    async def _on_sv3_intercepted(self, match_url: str, data: Dict):
        """Callback when sV3 data is intercepted from a persistent page."""
        try:
            match_id = self._extract_match_id(match_url) or match_url
            
            # Record success metric
            self.metrics.record_fast_poll(match_id, "success", 0, "intercept")
            
            # Get cached localStorage for team name decoding (Feature 007)
            local_storage = None
            if match_id:
                try:
                    local_storage = await self.cache.get_local_storage(match_id)
                    if local_storage:
                        logger.debug(f"[FASTPOLL] Got localStorage for {match_id}: {len(local_storage)} items")
                    else:
                        logger.debug(f"[FASTPOLL] No localStorage cached for {match_id}")
                except Exception as e:
                    logger.debug(f"Failed to get localStorage for {match_id}: {e}")
            
            # Push to backend
            if self._auth_token:
                push_success = await asyncio.to_thread(
                    CricketDataService.push_immediate_sv3,
                    data,
                    self._auth_token,
                    match_url,  # source_url parameter
                    local_storage,  # Pass localStorage for team name decoding
                )
                if push_success:
                    logger.info(f"[FASTPOLL] Pushed intercepted sV3 for {match_id}")
                    self.metrics.record_scrape_result("crex_fastpoll", "success", 0.001)
                else:
                    logger.warning(f"[FASTPOLL] Failed to push sV3 for {match_id}")
                    self.metrics.record_persistent_page_error(match_id, "push_failed")
            
            # Update pool metrics
            self.metrics.update_pool_size(self.persistent_page_pool.size)
            
        except Exception as e:
            logger.error(f"[FASTPOLL] Error in sV3 callback: {e}")
    
    async def _poll_and_push_DEPRECATED(self, match_id: str, page):
        """DEPRECATED: Replaced by network interception approach."""
        pass
    
    def _extract_match_id(self, url: str) -> Optional[str]:
        """Extract match ID from URL in the same format as crex_adapter.
        
        Expected: /scoreboard/{codes}/{codes}/{match-type}/{codes}/{codes}/{slug}/live
        Returns: crex:{slug}
        """
        try:
            if "/scoreboard/" in url:
                # Split and get the slug part before /live or /scorecard
                parts = url.split("/scoreboard/")[1].split("/")
                # The slug is typically the 6th part (0-indexed: code/code/match-num/code/code/slug)
                if len(parts) >= 6:
                    slug = parts[5].split("/")[0]  # Remove trailing /live etc
                    return f"crex:{slug}"
            
            # Legacy URL pattern: /match/{id}/...
            import re
            match = re.search(r'/match/(\d+)', url)
            if match:
                return f"crex:{match.group(1)}"
        except Exception:
            pass
        return None

    async def _monitor_loop(self):
        """Periodic health monitoring loop."""
        logger.info("Health monitor started.")
        while self._running:
            try:
                # Check for stalls
                if self.health.check_stall():
                    logger.warning("Stall detected by monitor.")
                
                # Check for recovery trigger
                if self.health.should_trigger_recovery():
                    logger.warning("Triggering automated recovery...")
                    self.health.record_recovery_attempt()
                    try:
                        await self.pool.recycle()
                        self.metrics.browser_restarts.labels(reason="stall_recovery").inc()
                        self.health.add_audit_log("recovery_executed", {"action": "browser_recycle"}, level="WARNING")
                    except Exception as e:
                        logger.error(f"Recovery failed: {e}")
                        self.health.add_audit_log("recovery_failed", {"error": str(e)}, level="ERROR")

                # Update health score metric for Prometheus
                summary = self.health.get_summary()
                self.metrics.health_score.set(summary.score)

                await asyncio.sleep(5)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitor loop error: {e}")
                await asyncio.sleep(5)

    async def _worker_loop(self, worker_id: int):
        """Main worker loop processing tasks from scheduler."""
        logger.debug(f"Worker {worker_id} started.")
        while self._running:
            try:
                task = await self.scheduler.next_task()
                self.metrics.queue_depth.set(self.scheduler.qsize)
                self.metrics.active_tasks.inc()
                
                try:
                    await self._process_task(task)
                except Exception as e:
                    logger.error(f"Worker {worker_id} failed task {task.match_id}: {e}")
                    self.health.record_failure(str(e))
                    self.metrics.domain_failures.labels(domain="crex", error_type=type(e).__name__).inc()
                    
                    # Record adapter failure if we can determine the adapter
                    # For now assuming crex
                    adapter = self.registry.get_adapter("crex")
                    if adapter:
                        adapter.reliability.record_failure()
                finally:
                    await self.scheduler.task_done(task)
                    self.metrics.active_tasks.dec()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker {worker_id} loop error: {e}")
                await asyncio.sleep(1)

    async def _process_task(self, task: ScrapeTask):
        """Process a single scrape task."""
        start_time = asyncio.get_running_loop().time()
        
        # Determine adapter (hardcoded to crex for now, logic can be expanded)
        adapter = self.registry.get_adapter("crex")
        if not adapter:
            logger.warning("Adapter 'crex' not available/enabled")
            return

        # Check negative cache
        canonical_id = adapter.get_canonical_id(task.match_id)
        if await self.cache.is_negative_cached(canonical_id):
            logger.info(f"Skipping {canonical_id} (negative cache)")
            return

        async with self.pool.get_context() as context:
            data = await adapter.fetch_match(context, task.url)
            
            # Check validity (if only metadata exists, assume scrape failed/empty)
            if len(data) <= 2: # source_url + adapter
                logger.warning(f"Match {canonical_id} returned no content, setting negative cache")
                await self.cache.set_negative_cache(canonical_id, ttl=60)
                return

            # Fetch match info if not present in cache
            previous_snapshot = await self.cache.get_snapshot(canonical_id)
            match_info = previous_snapshot.get("match_info") if previous_snapshot else None
            match_info_fetched_now = False
            info_url = None
            
            # Check persistent cache for match info if not in snapshot
            # This handles cases where snapshot expired but we still have the static info
            if not match_info:
                match_info = await self.cache.get_match_info(canonical_id)

            if not match_info:
                try:
                    # Construct info URL (assuming standard Crex URL structure)
                    # e.g. .../live -> .../info
                    info_url = task.url.replace("/live", "/info").replace("/scorecard", "/info")
                    # If URL didn't change (no /live or /scorecard), append /info if not present
                    if info_url == task.url and "/info" not in info_url:
                         info_url = task.url.rstrip("/") + "/info"
                         
                    logger.info(f"Fetching match info for {canonical_id} from {info_url}")
                    match_info = await adapter.fetch_match_info(context, info_url)
                    if match_info:
                        match_info_fetched_now = True
                        # Persist match info separately with long TTL
                        await self.cache.set_match_info(canonical_id, match_info)
                except Exception as e:
                    logger.error(f"Failed to fetch match info for {canonical_id}: {e}")
            
            if match_info:
                data["match_info"] = match_info

            # Overs Data Caching Logic
            # If current scrape has overs, cache them.
            # If current scrape has NO overs, try to retrieve from cache.
            current_overs = data.get("overs_data")
            if current_overs and isinstance(current_overs, list) and len(current_overs) > 0:
                await self.cache.set_latest_overs(canonical_id, current_overs)
            elif not current_overs:
                cached_overs = await self.cache.get_latest_overs(canonical_id)
                if cached_overs:
                    data["overs_data"] = cached_overs
                    logger.info(f"Used cached overs_data for {canonical_id} (fallback)")

            # Canonical ID check
            # canonical_id already computed above
            if canonical_id != task.match_id:
                logger.warning(f"ID mismatch: task={task.match_id} canonical={canonical_id}")

            # Cache result
            # previous_snapshot already fetched above
            
            status = str(data.get("status", "")).lower()
            is_completed = status in ("completed", "result", "finished", "abandoned")

            if is_completed:
                logger.info(f"Match {canonical_id} completed ({status}), archiving.")
                await self.cache.push_history(canonical_id, data)
                await self.cache.archive_match(canonical_id)
            else:
                await self.cache.set_snapshot(canonical_id, data, ttl=self.settings.cache_live_ttl)
                await self.cache.push_history(canonical_id, data)
                await self.cache.update_freshness(canonical_id, start_time)
            
            # Delta emission
            if previous_snapshot:
                delta = self.cache.compute_delta(previous_snapshot, data)
                if delta:
                    logger.debug(f"Delta for {canonical_id}: {list(delta.keys())}")
            
            # Push to Backend (Task 8.4)
            # We push even if no delta, to ensure backend is in sync (or we could optimize to only push on delta)
            # For now, push every successful scrape to match legacy behavior
            if self._auth_token:
                # Run in thread to avoid blocking loop
                push_success = await asyncio.to_thread(
                    CricketDataService.push_match_data, 
                    data, 
                    self._auth_token, 
                    task.url
                )
                if not push_success:
                    logger.warning(f"Failed to push data for {canonical_id}")
                
                # Push match info if newly fetched
                if match_info_fetched_now and match_info:
                     # Use info_url if available, else derive it again
                     if not info_url:
                        info_url = task.url.replace("/live", "/info").replace("/scorecard", "/info")
                        if info_url == task.url and "/info" not in info_url:
                             info_url = task.url.rstrip("/") + "/info"

                     await asyncio.to_thread(
                        CricketDataService.push_match_info,
                        match_info,
                        self._auth_token,
                        info_url
                     )
                
                # Push sC4 stats if available
                if data.get("match_stats"):
                     logger.info(f"Pushing sC4 stats for {canonical_id}. Data keys: {list(data['match_stats'].keys()) if isinstance(data['match_stats'], dict) else 'Not a dict'}")
                     await asyncio.to_thread(
                        CricketDataService.push_sc4_stats,
                        data["match_stats"],
                        self._auth_token,
                        task.url
                     )
            else:
                logger.warning(f"Skipping push for {canonical_id} (no auth token)")

            # Metrics & Health
            duration = asyncio.get_running_loop().time() - start_time
            self.metrics.record_scrape_result("crex", "success", duration)
            self.metrics.update_freshness(canonical_id, "crex", 0) # 0s age immediately after scrape
            self.health.record_success()
            self.health.record_freshness(0.0)
            adapter.reliability.record_success()
            
            logger.info(f"Scraped {canonical_id} in {duration:.2f}s")

    async def submit_task(self, match_id: str, url: str, task_type: str = "LIVE") -> bool:
        """Submit a task to the scheduler."""
        # Ensure canonical ID usage if possible, or rely on caller
        result = await self.scheduler.enqueue(match_id, url, task_type)
        self.metrics.queue_depth.set(self.scheduler.qsize)
        return result
