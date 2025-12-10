import pytest
import json
from unittest.mock import MagicMock, patch
from crex_scraper_python.src.app import app
from crex_scraper_python.src.health import HealthSummary, HealthState

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_status_freshness_fields(client):
    """
    Test that /status endpoint returns freshness metrics in details.
    """
    with patch('crex_scraper_python.src.app.scraper_service') as mock_service:
        # Mock health summary
        mock_health = MagicMock()
        mock_service.health = mock_health
        
        summary = HealthSummary(
            state=HealthState.HEALTHY,
            score=100,
            uptime_seconds=120,
            pids_count=10,
            memory_usage_mb=50.0,
            last_scrape_timestamp=1000.0,
            active_matches=5,
            details={
                "freshness": {
                    "p50": 1.5,
                    "p90": 2.0,
                    "p99": 5.0
                }
            }
        )
        mock_health.get_summary.return_value = summary
        
        response = client.get('/status')
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert data["status"] == "success"
        assert "freshness" in data["data"]["details"]
        assert data["data"]["details"]["freshness"]["p50"] == 1.5
        assert data["data"]["details"]["freshness"]["p99"] == 5.0
