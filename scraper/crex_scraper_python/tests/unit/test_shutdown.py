import threading
import time

from src import crex_main_url
from src.shared import scraping_tasks
from src.core.scraper_context import ScraperContext


def setup_function() -> None:
    scraping_tasks.clear()
    crex_main_url.scraper_registry.clear()
    crex_main_url.SERVICE_SHUTDOWN_EVENT.clear()


def teardown_function() -> None:
    scraping_tasks.clear()
    crex_main_url.scraper_registry.clear()
    crex_main_url.SERVICE_SHUTDOWN_EVENT.clear()


def test_shutdown_active_scrapes_signals_threads():
    context = ScraperContext(match_id="match-shutdown", url="https://example.com")
    crex_main_url.scraper_registry.register(context)

    def worker() -> None:
        try:
            while not context.shutdown_requested:
                time.sleep(0.01)
        finally:
            context.shutdown()

    thread = threading.Thread(target=worker, daemon=True)
    scraping_tasks[context.url] = {
        "thread": thread,
        "status": "running",
        "context": context,
        "match_id": context.match_id,
    }

    thread.start()
    crex_main_url.shutdown_active_scrapes(timeout_seconds=1.0)

    thread.join(timeout=1.0)
    assert not thread.is_alive()
    assert context.is_shutdown is True
    assert context.url not in scraping_tasks
    assert crex_main_url.SERVICE_SHUTDOWN_EVENT.is_set() is True
