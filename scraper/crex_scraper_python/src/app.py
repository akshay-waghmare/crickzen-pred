"""
Flask Application Entry Point.
Exposes API endpoints and manages scraper lifecycle.
"""

import asyncio
import logging
import threading
from typing import Optional

from flask import Flask, jsonify, Response, request
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from .config import get_settings
from .crex_scraper import CrexScraperService
from .loggers.adapters import configure_logging

# Configure logging immediately
configure_logging(level=logging.INFO)

logger = logging.getLogger(__name__)

app = Flask(__name__)
settings = get_settings()
scraper_service = CrexScraperService()

# Global event loop for the scraper service
scraper_loop: Optional[asyncio.AbstractEventLoop] = None

def start_scraper_background():
    """Start the scraper service in a background thread."""
    global scraper_loop
    scraper_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(scraper_loop)
    
    try:
        scraper_loop.run_until_complete(scraper_service.start())
        # Keep the loop running for background tasks
        scraper_loop.run_forever()
    except Exception as e:
        logger.error(f"Scraper background loop failed: {e}")
    finally:
        scraper_loop.close()

@app.route("/health")
@app.route("/status")
def health_check():
    """
    Return service health status.
    """
    summary = scraper_service.health.get_summary()
    return jsonify({
        "status": "success",
        "data": {
            "state": summary.state,
            "score": summary.score,
            "uptime": summary.uptime_seconds,
            "pids": summary.pids_count,
            "memory_mb": summary.memory_usage_mb,
            "last_scrape": summary.last_scrape_timestamp,
            "details": summary.details
        }
    })

@app.route("/metrics")
def metrics():
    """
    Expose Prometheus metrics.
    """
    return Response(generate_latest(scraper_service.metrics.registry), mimetype=CONTENT_TYPE_LATEST)

@app.route("/recycle", methods=["POST"])
def manual_recycle():
    """
    Trigger manual browser recycle.
    """
    # Stub for now, will implement full logic later
    return jsonify({"status": "success", "message": "Recycle triggered (stub)"})

# Start scraper on app startup (if not running in a separate worker process manager that handles this)
# For simple deployment, we start it here.
threading.Thread(target=start_scraper_background, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
