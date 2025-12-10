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

def test_status_degraded(client):
    """
    Test that /status endpoint reflects DEGRADED state.
    """
    with patch('crex_scraper_python.src.app.scraper_service') as mock_service:
        mock_health = MagicMock()
        mock_service.health = mock_health
        
        summary = HealthSummary(
            state=HealthState.DEGRADED,
            score=70,
            uptime_seconds=100,
            pids_count=5,
            memory_usage_mb=100.0,
            last_scrape_timestamp=1000.0,
            active_matches=2,
            details={"reason": "Freshness lag"}
        )
        mock_health.get_summary.return_value = summary
        
        response = client.get('/status')
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert data["data"]["state"] == "degraded"
        assert data["data"]["score"] == 70
