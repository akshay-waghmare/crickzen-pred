#!/usr/bin/env python
"""
Startup script for the Cricket Scraper Service with structured logging.
"""

import atexit
import signal
import sys
import os
import threading
import time
from typing import Optional

# Add both current directory and parent directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)

sys.path.insert(0, current_dir)
sys.path.insert(0, parent_dir)

from src.crex_main_url import (
    SERVICE_SHUTDOWN_EVENT,
    app,
    initialize_database,
    job,
    shutdown_active_scrapes,
)
from src.config import get_settings
from src.monitoring import ensure_metrics_server

def auto_start_periodic_job(stop_event: Optional[threading.Event] = None) -> None:
    """Auto-start the periodic scraping job after a brief delay."""

    shutdown_event = stop_event or SERVICE_SHUTDOWN_EVENT
    if shutdown_event.wait(5):  # Wait for server to warm up unless shutting down
        return

    print("\n🚀 Auto-starting periodic scraping job...")
    print("   - Will check for live matches every 60 seconds")
    print("   - Backend will clean up old/finished matches")
    print("   - New matches will be automatically scraped\n")
    job(stop_event=shutdown_event)

if __name__ == "__main__":
    # Feature 007: Support staggered startup delay for multi-instance deployments
    startup_delay = int(os.environ.get("STARTUP_DELAY_SECONDS", "0"))
    if startup_delay > 0:
        print(f"⏳ Startup delay: waiting {startup_delay} seconds before starting...")
        time.sleep(startup_delay)
        print("✅ Startup delay complete. Starting service...")
    
    print("Starting Cricket Scraper Service...")
    print("Initializing database...")
    initialize_database()
    print("Database initialized successfully")

    settings = get_settings()
    if settings.enable_prometheus_metrics:
        try:
            ensure_metrics_server(settings)
            print(
                f"Metrics available on http://{settings.prometheus_host}:{settings.prometheus_port}/metrics"
            )
        except OSError as exc:
            print(f"Warning: failed to start metrics server ({exc})", file=sys.stderr)
    
    SERVICE_SHUTDOWN_EVENT.clear()

    periodic_thread = threading.Thread(
        target=auto_start_periodic_job,
        kwargs={"stop_event": SERVICE_SHUTDOWN_EVENT},
        daemon=True,
    )
    periodic_thread.start()

    shutdown_once = threading.Event()

    def initiate_shutdown(source: str) -> None:
        if shutdown_once.is_set():
            return
        shutdown_once.set()
        print(f"\n⚠️  Initiating scraper shutdown ({source})...")
        SERVICE_SHUTDOWN_EVENT.set()
        shutdown_active_scrapes(timeout_seconds=settings.graceful_shutdown_timeout_seconds)
        if periodic_thread.is_alive():
            periodic_thread.join(timeout=settings.graceful_shutdown_timeout_seconds)
        print("✅ Scraper shutdown complete.\n")

    def handle_signal(signum, _frame) -> None:
        initiate_shutdown(f"signal {signum}")

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    atexit.register(lambda: initiate_shutdown("process exit"))

    print("\nServer starting on http://0.0.0.0:5000")
    print("Periodic scraping will auto-start in 5 seconds...")
    print("Press CTRL+C to quit\n")

    try:
        app.run(host="0.0.0.0", port=5000, debug=False)
    except KeyboardInterrupt:
        initiate_shutdown("keyboard interrupt")
    finally:
        initiate_shutdown("server stopped")
