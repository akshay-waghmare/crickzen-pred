import pytest
from crex_scraper_python.src.app import app, scraper_service
from crex_scraper_python.src.health import HealthState

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_status_recovering(client):
    # Force state to RECOVERING
    scraper_service.health.transition_to(HealthState.RECOVERING, "Test recovery")
    
    response = client.get("/status")
    assert response.status_code == 200
    data = response.get_json()
    
    assert data["data"]["state"] == "recovering"
    assert data["data"]["score"] == 50
    
    # Reset state
    scraper_service.health.transition_to(HealthState.HEALTHY, "Test end")
