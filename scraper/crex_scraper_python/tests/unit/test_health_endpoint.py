from src.core.scraper_context import ScraperContext
from src import crex_main_url


def setup_function():
    crex_main_url.scraper_registry.clear()


def teardown_function():
    crex_main_url.scraper_registry.clear()


def test_health_endpoint_without_scrapers():
    with crex_main_url.app.test_client() as client:
        response = client.get("/health")
        assert response.status_code == 200
        body = response.get_json()
        assert body["success"] is True
        assert body["data"]["active_scraper_count"] == 0
        assert body["data"]["overall_status"] == "healthy"
    assert body["data"]["service_shutdown_requested"] is False


def test_health_endpoint_with_active_scraper():
    context = ScraperContext(match_id="match-abc", url="https://example.com/match/abc")
    crex_main_url.scraper_registry.register(context)

    with crex_main_url.app.test_client() as client:
        response = client.get("/health")
        assert response.status_code == 200
        body = response.get_json()
        assert body["data"]["active_scraper_count"] == 1
        assert body["data"]["scrapers"][0]["match_id"] == "match-abc"
        assert "timestamp" in body
    assert body["data"]["service_shutdown_requested"] is False
