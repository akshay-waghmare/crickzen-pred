import logging
from datetime import datetime, timedelta
from typing import Optional
from uuid import uuid4

from flask import Flask, jsonify, request
from flask_cors import CORS
from playwright.sync_api import sync_playwright
import requests
from .cricket_data_service import CricketDataService
import threading
import time
import sqlite3
import sys
import os
import logging_config
from src import monitoring
from .config import get_settings
from .core.scraper_context import (
    ScraperContext,
    ScraperRegistry,
    derive_match_id,
    utcnow,
)

# Add parent directory to path to import root-level match data scraper
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, parent_dir)
from crex_match_data_scraper import fetchData as fetch_match_data  # The detailed match scraper
from .shared import scraping_tasks
from .loggers.adapters import get_logger, bind_correlation_id

app = Flask(__name__)
CORS(app, resources={
    r"/add-lead": {
        "origins": "*",
        "methods": ["POST", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    }
})

# Configure structured JSON logging
SETTINGS = get_settings()
logging_config.setup_logging(SETTINGS)
logger = get_logger(component="crex_main_url")
SERVICE_START_TIME = utcnow()
# Track single live matches scraping thread to prevent runaway browser leaks
LIVE_MATCHES_THREAD: Optional[threading.Thread] = None
LIVE_MATCHES_LOCK = threading.RLock()

def _orphan_cleanup_worker():
    """Background task that forces container restart at configured interval.
    
    Simple periodic restart to prevent PID/memory accumulation from browser processes.
    Also checks for stale scraper contexts between restarts.
    """
    settings = SETTINGS
    staleness_threshold = settings.staleness_threshold_seconds * 3
    restart_interval_seconds = settings.container_restart_interval_minutes * 60
    
    print(f"[ORPHAN_WORKER] Starting - will restart container every {restart_interval_seconds//60} minutes", flush=True)
    logger.info("orphan_cleanup_worker_started", metadata={"restart_interval_minutes": restart_interval_seconds//60})
    
    start_time = time.time()
    
    while not SERVICE_SHUTDOWN_EVENT.is_set():
        time.sleep(30)
        try:
            # Check if it's time for periodic restart
            elapsed = time.time() - start_time
            if elapsed >= restart_interval_seconds:
                logger.warning(
                    "periodic_container_restart",
                    metadata={
                        "uptime_minutes": elapsed // 60,
                        "reason": f"{restart_interval_seconds//60}_minute_periodic_restart",
                        "action": "graceful_container_restart"
                    }
                )
                print(f"[ORPHAN_WORKER] {restart_interval_seconds//60} minutes elapsed - restarting container", flush=True)
                
                # Mark container as unhealthy for graceful degradation
                CONTAINER_UNHEALTHY.set()
                
                # Schedule container exit after brief delay for health propagation
                def delayed_exit():
                    time.sleep(10)
                    logger.critical("exiting_container_for_restart", metadata={"source": "periodic_10min_restart"})
                    os._exit(1)  # Force exit entire process
                
                threading.Thread(target=delayed_exit, daemon=False).start()
                return  # Exit worker loop after triggering restart
            
            # Check for stale contexts between restarts
            for ctx in scraper_registry.all_contexts():
                if ctx.staleness_seconds >= staleness_threshold and not ctx.restart_requested:
                    ctx.request_restart("orphan_stale", grace_seconds=settings.memory_restart_grace_seconds)
        except Exception as e:
            # Defensive: never let monitoring worker crash
            logger.error("orphan_cleanup_worker_error", metadata={"error": str(e)})
            continue

# Initialize global state before starting background workers
scraper_registry = ScraperRegistry()
SERVICE_SHUTDOWN_EVENT = threading.Event()
# Flag to mark container as unhealthy before exit (allows graceful degradation)
CONTAINER_UNHEALTHY = threading.Event()

# Start orphan cleanup worker (must be after SERVICE_SHUTDOWN_EVENT is defined)
threading.Thread(target=_orphan_cleanup_worker, daemon=True).start()


def _maybe_schedule_restart(
    *,
    url: str,
    match_id: str,
    reason: Optional[str],
    metadata: dict[str, object],
    requested_at: Optional[datetime],
    deadline: Optional[datetime],
) -> None:
    if SERVICE_SHUTDOWN_EVENT.is_set():
        logger.info(
            "scrape.restart.skip_shutdown",
            metadata={
                "url": url,
                "match_id": match_id,
                "reason": reason or "unspecified",
            },
        )
        return

    # Avoid scheduling duplicate restarts if another job already registered for this URL
    if url in scraping_tasks:
        existing = scraping_tasks.get(url) or {}
        status = existing.get("status")
        logger.debug(
            "scrape.restart.skip_existing",
            metadata={"url": url, "match_id": match_id, "status": status},
        )
        return

    now = utcnow()
    effective_deadline = deadline or now + timedelta(seconds=SETTINGS.memory_restart_grace_seconds)
    remaining = max((effective_deadline - now).total_seconds(), 0.0)
    delay = max(0.0, min(5.0, remaining))

    metadata_copy = dict(metadata)
    reason_text = reason or "unspecified"
    payload: dict[str, object] = {
        "url": url,
        "match_id": match_id,
        "reason": reason_text,
        "delay_seconds": round(delay, 2),
        "deadline": effective_deadline.isoformat(),
        "requested_at": requested_at.isoformat() if requested_at else None,
    }
    if metadata_copy:
        payload["metadata"] = metadata_copy

    logger.warning("scrape.restart.scheduled", metadata=payload)

    _launch_scrape_job(
        url,
        match_id,
        restart=True,
        restart_reason=reason_text,
        restart_metadata=metadata_copy,
        delay_seconds=delay,
    )


def _finalize_context(
    context: ScraperContext,
    *,
    url: str,
    match_id: str,
    task_state: dict[str, object],
) -> None:
    should_restart = context.restart_requested and not SERVICE_SHUTDOWN_EVENT.is_set()
    restart_reason = context.restart_reason
    restart_metadata = context.restart_metadata
    restart_deadline = context.restart_deadline
    restart_requested_at = context.restart_requested_at

    context.shutdown()
    scraper_registry.remove_by_url(url)
    monitoring.clear_scraper_gauges(match_id)
    monitoring.set_active_scrapers(len(scraper_registry.all_contexts()))

    if task_state.get("status") != "cancelled":
        task_state["status"] = "stopped"

    if scraping_tasks.get(url) is task_state:
        scraping_tasks.pop(url, None)

    if should_restart:
        _maybe_schedule_restart(
            url=url,
            match_id=match_id,
            reason=restart_reason,
            metadata=restart_metadata,
            requested_at=restart_requested_at,
            deadline=restart_deadline,
        )


def _launch_scrape_job(
    url: str,
    match_id: str,
    *,
    correlation_id: Optional[str] = None,
    restart: bool = False,
    restart_reason: Optional[str] = None,
    restart_metadata: Optional[dict[str, object]] = None,
    delay_seconds: float = 0.0,
) -> Optional[ScraperContext]:
    if SERVICE_SHUTDOWN_EVENT.is_set():
        logger.info(
            "scrape.job.skip_shutdown",
            metadata={"url": url, "match_id": match_id},
        )
        return None

    correlation = correlation_id or str(uuid4())
    metadata_copy = dict(restart_metadata or {})

    context = ScraperContext(match_id=match_id, url=url, settings=SETTINGS)
    scraper_registry.register(context)
    monitoring.update_context_metrics(context)
    monitoring.set_active_scrapers(len(scraper_registry.all_contexts()))

    task_state: dict[str, object] = {
        "thread": None,
        "status": "scheduled" if delay_seconds > 0 else "running",
        "context": context,
        "match_id": match_id,
        "correlation_id": correlation,
    }

    def scrape_with_context() -> None:
        bind_correlation_id(correlation)
        try:
            if delay_seconds > 0:
                wait_until = time.monotonic() + delay_seconds
                while True:
                    remaining = wait_until - time.monotonic()
                    if remaining <= 0:
                        break
                    if SERVICE_SHUTDOWN_EVENT.is_set() or context.shutdown_requested:
                        task_state["status"] = "cancelled"
                        logger.info(
                            "scrape.job.cancelled_before_start",
                            metadata={
                                "url": url,
                                "match_id": match_id,
                                "reason": "shutdown" if SERVICE_SHUTDOWN_EVENT.is_set() else "shutdown_requested",
                            },
                        )
                        return
                    time.sleep(min(1.0, remaining))

            with logging_config.scraper_logging_context(context=context):
                if context.shutdown_requested or SERVICE_SHUTDOWN_EVENT.is_set():
                    task_state["status"] = "cancelled"
                    logger.info(
                        "scrape.job.skipped",
                        metadata={
                            "url": url,
                            "match_id": match_id,
                            "reason": "shutdown_requested",
                        },
                    )
                    return

                task_state["status"] = "running"

                start_metadata = {
                    "url": url,
                    "match_id": match_id,
                    "thread_id": str(threading.get_ident()),
                }
                if restart:
                    start_metadata["restart"] = True
                if restart_reason:
                    start_metadata["restart_reason"] = restart_reason
                if metadata_copy:
                    start_metadata["restart_metadata"] = metadata_copy

                logger.info("scrape.job.started", metadata=start_metadata)

                try:
                    start_time = time.perf_counter()
                    fetch_match_data(url, context=context)  # Pass context for restart management
                    latency = time.perf_counter() - start_time
                    context.record_update()
                    context.update_resource_usage()
                    monitoring.record_scraper_update(match_id, latency_seconds=latency)
                    monitoring.update_context_metrics(context)
                    logger.info(
                        "scrape.job.complete",
                        metadata={"url": url, "match_id": match_id},
                    )
                except KeyboardInterrupt:
                    context.record_error()
                    monitoring.record_scraper_error(match_id, "KeyboardInterrupt")
                    context.update_resource_usage()
                    monitoring.update_context_metrics(context)
                    logger.warning(
                        "scrape.job.interrupted",
                        metadata={"url": url, "match_id": match_id},
                    )
                except Exception as exc:  # pragma: no cover - defensive catch
                    context.record_error()
                    monitoring.record_scraper_error(match_id, type(exc).__name__)
                    context.update_resource_usage()
                    monitoring.update_context_metrics(context)
                    logger.error(
                        "scrape.job.failed",
                        metadata={
                            "url": url,
                            "match_id": match_id,
                            "error": str(exc),
                            "error_type": type(exc).__name__,
                        },
                    )
        finally:
            _finalize_context(
                context,
                url=url,
                match_id=match_id,
                task_state=task_state,
            )

    thread = threading.Thread(target=scrape_with_context, daemon=True)
    task_state["thread"] = thread
    scraping_tasks[url] = task_state
    thread.start()

    return context

def _determine_overall_status(scraper_payloads):
    if not scraper_payloads:
        return "healthy"
    statuses = {payload.get("status") for payload in scraper_payloads}
    if statuses == {"healthy"}:
        return "healthy"
    if "failing" in statuses:
        return "degraded"
    if "degraded" in statuses:
        return "degraded"
    return "healthy"


def _build_health_response():
    contexts = scraper_registry.all_contexts()
    now = utcnow()
    scraper_payloads = []
    total_memory_mb = 0.0

    for context in contexts:
        try:
            # Skip resource update to avoid psutil hanging on Windows
            # context.update_resource_usage()
            pass
        except Exception:
            logger.debug("health.resource_update_failed", metadata={"match_id": context.match_id})
        
        try:
            monitoring.update_context_metrics(context)
        except Exception:
            logger.debug("health.metrics_update_failed", metadata={"match_id": context.match_id})
        
        payload = context.to_health_payload()
        scraper_payloads.append(payload)
        total_memory_mb += payload.get("memory_mb", 0.0)

    monitoring.set_active_scrapers(len(contexts))

    overall_status = _determine_overall_status(scraper_payloads)
    uptime_seconds = int((now - SERVICE_START_TIME).total_seconds())

    data = {
        "overall_status": overall_status,
        "active_scraper_count": len(scraper_payloads),
        "scrapers": scraper_payloads,
        "total_memory_mb": round(total_memory_mb, 2),
        "uptime_seconds": max(uptime_seconds, 0),
        "service_shutdown_requested": SERVICE_SHUTDOWN_EVENT.is_set(),
    }

    body = {
        "success": True,
        "data": data,
        "error": None,
        "timestamp": now.isoformat(),
    }

    logger.info(
        "health.snapshot",
        metadata={
            "active_scrapers": data["active_scraper_count"],
            "overall_status": overall_status,
        },
    )

    return body, 200


@app.route("/health", methods=["GET"])
def health():
    # Check if container is marked unhealthy (PID threshold exceeded, preparing to restart)
    if CONTAINER_UNHEALTHY.is_set():
        return jsonify({
            "success": False,
            "data": {
                "overall_status": "unhealthy",
                "reason": "container_restart_pending",
                "message": "PID threshold exceeded, container will restart shortly"
            },
            "error": "Service unavailable - container restarting",
            "timestamp": utcnow().isoformat()
        }), 503
    
    body, status_code = _build_health_response()
    return jsonify(body), status_code


@app.route("/monitoring/performance", methods=["GET"])
def performance_metrics():
    """
    Performance monitoring endpoint to track when batching becomes necessary.
    Returns real-time metrics and batching recommendations.
    """
    from datetime import timedelta
    
    # Get current scraper stats
    all_scrapers = scraper_registry.all_contexts()
    active_matches = len(all_scrapers)
    
    # Calculate API call rates (estimate based on active scrapers)
    # Each scraper updates every 2.5 seconds = 24 calls/min per match
    estimated_api_calls_per_min = active_matches * 24
    
    # Calculate memory usage across all scrapers
    total_memory_mb = sum(ctx.memory_bytes / (1024 * 1024) for ctx in all_scrapers)
    avg_memory_per_scraper = total_memory_mb / active_matches if active_matches > 0 else 0
    
    # Calculate uptime
    uptime_seconds = (utcnow() - SERVICE_START_TIME).total_seconds()
    
    # Batching recommendation logic
    should_batch = False
    readiness_score = 0
    reasons = []
    
    # Factor 1: API call rate (threshold: 500/min warns, 1000/min critical)
    if estimated_api_calls_per_min < 500:
        reasons.append(f"✅ API call rate healthy ({estimated_api_calls_per_min}/min vs 500 threshold)")
        readiness_score += 0
    elif estimated_api_calls_per_min < 1000:
        reasons.append(f"⚠️ API call rate elevated ({estimated_api_calls_per_min}/min, consider batching)")
        readiness_score += 40
    else:
        reasons.append(f"🔴 API call rate critical ({estimated_api_calls_per_min}/min, batching recommended)")
        should_batch = True
        readiness_score += 80
    
    # Factor 2: Memory usage (threshold: 4GB warns, 8GB critical)
    if total_memory_mb < 4000:
        reasons.append(f"✅ Memory usage healthy ({int(total_memory_mb)} MB vs 4000 threshold)")
        readiness_score += 0
    elif total_memory_mb < 8000:
        reasons.append(f"⚠️ Memory usage elevated ({int(total_memory_mb)} MB, monitor closely)")
        readiness_score += 30
    else:
        reasons.append(f"🔴 Memory usage critical ({int(total_memory_mb)} MB, batching recommended)")
        should_batch = True
        readiness_score += 60
    
    # Factor 3: Concurrent matches (threshold: 10+ matches)
    if active_matches < 10:
        reasons.append(f"✅ Match concurrency healthy ({active_matches} active)")
        readiness_score += 0
    elif active_matches < 20:
        reasons.append(f"⚠️ High match concurrency ({active_matches} active, consider batching)")
        readiness_score += 30
    else:
        reasons.append(f"🔴 Very high match concurrency ({active_matches} active, batching recommended)")
        should_batch = True
        readiness_score += 50
    
    # Calculate avg response time (simplified - would need actual tracking in production)
    avg_response_time_ms = 85  # Placeholder
    
    response = {
        "timestamp": utcnow().isoformat(),
        "uptime_seconds": int(uptime_seconds),
        "uptime_human": str(timedelta(seconds=int(uptime_seconds))),
        
        "current_performance": {
            "active_matches": active_matches,
            "estimated_api_calls_per_minute": estimated_api_calls_per_min,
            "total_memory_mb": int(total_memory_mb),
            "avg_memory_per_scraper_mb": int(avg_memory_per_scraper),
            "avg_response_time_ms": avg_response_time_ms,
        },
        
        "batching_recommendation": {
            "should_enable_batching": should_batch,
            "readiness_score": min(readiness_score, 100),
            "score_interpretation": (
                "🟢 No batching needed" if readiness_score < 40 else
                "🟡 Batching may help" if readiness_score < 70 else
                "🔴 Batching recommended"
            ),
            "reasons": reasons,
        },
        
        "thresholds": {
            "api_calls_per_min_warn": 500,
            "api_calls_per_min_critical": 1000,
            "memory_mb_warn": 4000,
            "memory_mb_critical": 8000,
            "concurrent_matches_warn": 10,
            "concurrent_matches_critical": 20,
        },
        
        "scraper_details": [
            {
                "match_id": ctx.match_id,
                "memory_mb": int(ctx.memory_bytes / (1024 * 1024)),
                "age_seconds": int(ctx.uptime_seconds),
                "error_count": ctx.error_count,
                "status": ctx.health_status
            }
            for ctx in all_scrapers[:10]  # Limit to first 10 for brevity
        ] if len(all_scrapers) <= 10 else [
            {
                "total_scrapers": len(all_scrapers),
                "showing": "Use /health for full details"
            }
        ]
    }
    
    return jsonify(response), 200


class ScrapeError(Exception):
    pass

class NetworkError(ScrapeError):
    pass

class DOMChangeError(ScrapeError):
    pass

DB_FILE = 'url_state.db'

def initialize_database():
    """Creates database and tables if they don't exist."""
    logger.info("database.init", metadata={"message": "Initializing database"})
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scraped_urls (
                url TEXT PRIMARY KEY,
                deletion_attempts INTEGER DEFAULT 0
            )
        ''')
        cursor.execute('DELETE FROM scraped_urls')
        
        # Add leads table creation
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_name TEXT NOT NULL,
                website TEXT,
                contact_email TEXT,
                phone_number TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        logger.info("database.clear", metadata={"message": "All URLs removed from the table"})
        logger.info("database.init_complete", metadata={"message": "Database initialized successfully"})
    except Exception as e:
        logger.error("database.init_error", metadata={"error": str(e)})
    finally:
        conn.close()

def store_urls(urls):
    logger.info("urls.store", metadata={"url_count": len(urls)})
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.executemany("INSERT INTO scraped_urls (url, deletion_attempts) VALUES (?, 0) ON CONFLICT(url) DO UPDATE SET deletion_attempts = 0", [(url,) for url in urls])
        conn.commit()
        logger.info("urls.store_complete", metadata={"message": "URLs stored successfully"})
    except Exception as e:
        logger.error("urls.store_error", metadata={"error": str(e)})
    finally:
        conn.close()
    

def load_previous_urls():
    logger.info("urls.load", metadata={"message": "Loading previous URLs"})
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT url FROM scraped_urls")
        results = cursor.fetchall()
        logger.info("urls.load_complete", metadata={"count": len(results)})
        return [row[0] for row in results]
    except Exception as e:
        logger.error("urls.load_error", metadata={"error": str(e)})
        return []
    finally:
        conn.close()

def get_changes(new_urls):
    logger.info("urls.diff", metadata={"new_url_count": len(new_urls)})
    previous_urls = load_previous_urls()
    added_urls = set(new_urls) - set(previous_urls)
    deleted_urls = set(previous_urls) - set(new_urls)
    logger.info("urls.diff_complete", metadata={"added": len(added_urls), "deleted": len(deleted_urls)})
    return added_urls, deleted_urls

def job(stop_event: Optional[threading.Event] = None):
    stop_event = stop_event or SERVICE_SHUTDOWN_EVENT
    correlation_id = bind_correlation_id()
    logger.info(
        "job.start",
        metadata={
            "correlation_id": correlation_id,
            "shutdown_requested": stop_event.is_set(),
        },
    )
    browser = None
    page = None

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-dev-shm-usage'],
            )
            page = browser.new_page()

            while not stop_event.is_set():
                try:
                    scrape(page, "https://crex.com")
                except Exception as exc:  # Broad catch to keep scheduler alive
                    logger.error(
                        "job.cycle_error",
                        metadata={
                            "error": str(exc),
                            "error_type": type(exc).__name__,
                            "correlation_id": correlation_id,
                        },
                    )
                if stop_event.wait(60):
                    break
    finally:
        if page is not None:
            try:
                page.close()
            except Exception:
                pass
        if browser is not None:
            try:
                browser.close()
            except Exception:
                pass
        logger.info(
            "job.stop",
            metadata={"correlation_id": correlation_id, "shutdown_requested": stop_event.is_set()},
        )

def scrape(page, url):
    logging.info(f"Scraping URL: {url}")
    try:
        page.goto(url)
        page.wait_for_timeout(10000)
        
        if not page.query_selector("div.live-card"):  
            raise DOMChangeError("Cannot locate essential 'div.live-card' element")
        
        live_divs = page.query_selector_all("div.live-card .live")

        urls = []
        for live_div in live_divs:
            parent_element = live_div.query_selector(":scope >> xpath=..")
            grandparent_element = parent_element.query_selector(":scope >> xpath=..")
            sibling_element = grandparent_element.query_selector(":scope >> xpath=following-sibling::*[1]")
            url = sibling_element.get_attribute('href')
            urls.append(url)

        logging.info(f"Scraped URLs: {urls}")

        # Convert relative URLs to absolute URLs
        urls = ['https://crex.com' + url for url in urls]
        logging.info(f"Full URLs: {urls}")
        
        previous_urls = load_previous_urls()
        added_urls, deleted_urls = get_changes(urls)    
        if not previous_urls:
            added_urls = urls
            deleted_urls = []
        store_urls(urls)
        
        # CRITICAL: Sync complete list of live matches with backend on EVERY scrape
        # This allows backend to mark old/finished matches for deletion
        # NOTE: /cricket-data/add-live-matches is PUBLIC (no auth required)
        try:
            logger.info("backend.sync_live_matches.start", metadata={"url_count": len(urls)})
            token = CricketDataService.get_bearer_token()
            # Send matches regardless of token (endpoint is public)
            CricketDataService.add_live_matches(urls, token)
            logger.info("backend.sync_live_matches.complete", metadata={"url_count": len(urls), "synced": True})
        except Exception as e:
            logger.warning("backend.sync_live_matches.error", metadata={"error": str(e), "message": "Backend sync failed, continuing with local scraping"})
        
        # Log changes for visibility
        if added_urls:
            logger.info("matches.new_detected", metadata={"count": len(added_urls), "urls": list(added_urls)})
        if deleted_urls:
            logger.info("matches.deleted_detected", metadata={"count": len(deleted_urls), "urls": list(deleted_urls)})

        # Ensure scraper is running for ALL current live URLs
        # This handles both new matches AND matches that were interrupted/stopped (e.g. Stumps)
        for i, url in enumerate(urls):
            is_running = False
            if url in scraping_tasks:
                task = scraping_tasks[url]
                thread = task.get('thread')
                if thread and thread.is_alive():
                    is_running = True
            
            if not is_running:
                logger.info("matches.ensure_running", metadata={"url": url, "reason": "live_but_not_running"})
                
                # Add a small delay between requests to avoid overwhelming the system
                if i > 0:
                    time.sleep(2)
                
                try:
                    response = requests.post('http://127.0.0.1:5000/start-scrape', json={'url': url})
                    if response.status_code == 200:
                        logger.info("matches.scrape_started", metadata={"url": url})
                    else:
                        logger.error("matches.scrape_failed", metadata={"url": url, "status_code": response.status_code})
                except Exception as e:
                    logger.error("matches.scrape_request_failed", metadata={"url": url, "error": str(e)})
                
        time.sleep(60)                
        return {'status': 'Scraping finished', 'match_urls': urls}
    except NetworkError as ne:
        logging.error(f"Network error occurred: {ne}")
        raise ne
    except DOMChangeError as de:
        logging.error(f"DOM change error occurred: {de}")
        raise de
    except Exception as e:
        logging.error(f"Error during navigation: {e}")
        raise ScrapeError(f"Error during navigation: {e}")


def shutdown_active_scrapes(timeout_seconds: float = 30.0, *, stop_event: Optional[threading.Event] = None) -> None:
    """Attempt to gracefully stop all active scraping threads."""

    stop_signal = stop_event or SERVICE_SHUTDOWN_EVENT
    stop_signal.set()

    active_items = list(scraping_tasks.items())
    if not active_items:
        logger.info("shutdown.scrapers.none", metadata={"timeout_seconds": timeout_seconds})
        monitoring.set_active_scrapers(len(scraper_registry.all_contexts()))
        return

    logger.info(
        "shutdown.scrapers.start",
        metadata={"active": len(active_items), "timeout_seconds": timeout_seconds},
    )

    start_time = time.perf_counter()
    deadline = start_time + max(0.0, float(timeout_seconds))
    remaining_threads = 0

    for url, task in active_items:
        thread = task.get("thread")
        context: Optional[ScraperContext] = task.get("context")

        if context:
            context.request_shutdown()

        if thread and thread.is_alive():
            wait_timeout = max(0.0, deadline - time.perf_counter())
            if wait_timeout > 0:
                thread.join(timeout=wait_timeout)
        if thread and thread.is_alive():
            remaining_threads += 1

        if context:
            if not context.is_shutdown:
                context.shutdown()
            monitoring.clear_scraper_gauges(context.match_id)

        scraper_registry.remove_by_url(url)
        task['status'] = 'stopped'
        scraping_tasks.pop(url, None)

    monitoring.set_active_scrapers(len(scraper_registry.all_contexts()))

    metadata = {
        "elapsed": round(time.perf_counter() - start_time, 2),
        "remaining_threads": remaining_threads,
    }

    if remaining_threads:
        logger.warning("shutdown.scrapers.incomplete", metadata=metadata)
    else:
        logger.info("shutdown.scrapers.complete", metadata=metadata)


@app.route('/scrape-live-matches-link', methods=['GET'])
def scrape_live_matches():
    """Start (or reuse) the continuous live matches discovery thread.

    Prevents spawning multiple persistent browser loops which previously
    caused thousands of orphaned Chromium processes and thread exhaustion.
    """
    global LIVE_MATCHES_THREAD
    try:
        with LIVE_MATCHES_LOCK:
            if LIVE_MATCHES_THREAD and LIVE_MATCHES_THREAD.is_alive():
                return jsonify({'status': 'Already running'}), 200
            logging.info("Starting live matches discovery thread")
            LIVE_MATCHES_THREAD = threading.Thread(target=job, kwargs={"stop_event": SERVICE_SHUTDOWN_EVENT}, daemon=True)
            LIVE_MATCHES_THREAD.start()
        return jsonify({'status': 'Scraping started'})
    except ScrapeError as se:
        logging.error(f"Scraping error occurred: {se}")
        return jsonify({'status': 'Scraping error', 'error_message': str(se)}), 500
    except Exception as e:
        logging.error(f"Error occurred: {e}")
        return jsonify({'status': 'Error occurred', 'error_message': str(e)}), 500

@app.route('/start-scrape', methods=['POST'])
def start_scrape():
    payload = request.get_json(silent=True) or {}
    url = payload.get('url')

    if not url:
        logger.warning("scrape.request.no_url", metadata={"source": "start_scrape"})
        response = jsonify({'status': 'No url provided'}), 400
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response

    match_id = payload.get('match_id') or derive_match_id(url)

    if SERVICE_SHUTDOWN_EVENT.is_set():
        logger.warning(
            "scrape.request.rejected_shutdown",
            metadata={"url": url, "match_id": match_id},
        )
        response = jsonify({'status': 'Shutdown in progress, start rejected'}), 503
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response

    # Bind correlation ID for this scraping job
    correlation_id = bind_correlation_id()
    with logging_config.scraper_logging_context(match_id=match_id):
        logger.info(
            "scrape.request.received",
            metadata={"url": url, "correlation_id": correlation_id, "match_id": match_id},
        )

    if _launch_scrape_job(
        url,
        match_id,
        correlation_id=correlation_id,
    ) is None:
        response = jsonify({'status': 'Shutdown in progress, start rejected'}), 503
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response

    with logging_config.scraper_logging_context(match_id=match_id):
        logger.info(
            "scrape.job.enqueued",
            metadata={"url": url, "match_id": match_id, "correlation_id": correlation_id},
        )

    response = jsonify({
        'status': 'Scraping started for url: ' + url,
        'correlation_id': correlation_id,
        'match_id': match_id,
    })
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response
    
@app.route('/stop-scrape', methods=['POST'])
def stop_scrape():
    payload = request.get_json(silent=True) or {}
    url = payload.get('url')
    if not url:
        return jsonify({'status': 'No url provided'}), 400

    task_data = scraping_tasks.get(url)
    if not task_data:
        return jsonify({'status': 'No scraping task found for url: ' + url}), 400

    match_id = task_data.get('match_id')
    with logging_config.scraper_logging_context(match_id=match_id):
        logger.info("scrape.stop.request", metadata={"url": url})

    task_data['status'] = 'stopping'
    thread = task_data.get('thread')
    context: Optional[ScraperContext] = task_data.get('context')

    if context:
        context.request_shutdown()

    timeout_seconds = float(SETTINGS.graceful_shutdown_timeout_seconds)
    deadline = time.perf_counter() + max(0.0, timeout_seconds)

    if thread and thread.is_alive():
        remaining = max(0.0, deadline - time.perf_counter())
        if remaining > 0:
            thread.join(timeout=remaining)
        if thread.is_alive():
            logger.warning(
                "scrape.stop.thread_alive",
                metadata={"url": url, "match_id": match_id, "timeout_seconds": timeout_seconds},
            )
        else:
            logger.info(
                "scrape.stop.thread_joined",
                metadata={"url": url, "match_id": match_id},
            )

    if context and not context.is_shutdown:
        context.shutdown()

    task_data['status'] = 'stopped'

    scraper_registry.remove_by_url(url)
    if match_id:
        monitoring.clear_scraper_gauges(match_id)
    monitoring.set_active_scrapers(len(scraper_registry.all_contexts()))
    scraping_tasks.pop(url, None)

    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM scraped_urls WHERE url=?", (url,))
            conn.commit()
    except sqlite3.Error as exc:
        logger.warning("scrape.stop.cleanup_failed", metadata={"url": url, "error": str(exc)})

    return jsonify({'status': f'Stopped scraping for url: {url}'})

@app.route("/api/v1/scraper/health", methods=["GET"])
def scraper_health():
    body, status_code = _build_health_response()
    return jsonify(body), status_code

@app.route("/add-lead", methods=["POST", "OPTIONS"])
def add_lead():
    if request.method == "OPTIONS":
        response = jsonify({"message": "OK"})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        response.headers.add('Access-Control-Allow-Methods', 'POST')
        return response

    try:
        data = request.json
        company_name = data.get("company_name")
        website = data.get("website")
        contact_email = data.get("contact_email", "")
        phone_number = data.get("phone_number", "")
        notes = data.get("notes", "")

        if not company_name or not website:
            return jsonify({"error": "Company name and website are required"}), 400

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO leads (company_name, website, contact_email, phone_number, notes) 
            VALUES (?, ?, ?, ?, ?)""",
            (company_name, website, contact_email, phone_number, notes))
        conn.commit()
        lead_id = cursor.lastrowid
        conn.close()

        logging.info(f"New lead added: {company_name}")
        response = jsonify({"message": "Lead added successfully", "lead_id": lead_id})
        return response, 201

    except Exception as e:
        logging.error(f"Error adding lead: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/view-leads", methods=["GET"])
def view_leads():
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, company_name, website, contact_email, phone_number, notes, created_at 
            FROM leads 
            ORDER BY created_at DESC""")
        leads = cursor.fetchall()
        conn.close()

        lead_list = []
        for lead in leads:
            lead_list.append({
                "id": lead[0],
                "company_name": lead[1],
                "website": lead[2],
                "contact_email": lead[3],
                "phone_number": lead[4],
                "notes": lead[5],
                "created_at": lead[6]
            })

        return jsonify({"leads": lead_list}), 200

    except Exception as e:
        logging.error(f"Error fetching leads: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/update-lead/<int:lead_id>", methods=["PUT"])
def update_lead(lead_id):
    try:
        data = request.json
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM leads WHERE id = ?", (lead_id,))
        if not cursor.fetchone():
            conn.close()
            return jsonify({"error": "Lead not found"}), 404

        update_fields = []
        values = []
        for field in ["company_name", "website", "contact_email", "phone_number", "notes"]:
            if field in data:
                update_fields.append(f"{field} = ?")
                values.append(data[field])
        
        if update_fields:
            values.append(lead_id)
            query = f"UPDATE leads SET {', '.join(update_fields)} WHERE id = ?"
            cursor.execute(query, values)
            conn.commit()
            
        conn.close()
        logging.info(f"Lead {lead_id} updated successfully")
        return jsonify({"message": "Lead updated successfully"}), 200

    except Exception as e:
        logging.error(f"Error updating lead: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/delete-lead/<int:lead_id>", methods=["DELETE"])
def delete_lead(lead_id):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM leads WHERE id = ?", (lead_id,))
        if not cursor.fetchone():
            conn.close()
            return jsonify({"error": "Lead not found"}), 404

        cursor.execute("DELETE FROM leads WHERE id = ?", (lead_id,))
        conn.commit()
        conn.close()
        
        logging.info(f"Lead {lead_id} deleted successfully")
        return jsonify({"message": "Lead deleted successfully"}), 200

    except Exception as e:
        logging.error(f"Error deleting lead: {e}")
        return jsonify({"error": str(e)}), 500
    
if __name__ == "__main__":
    initialize_database()
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)