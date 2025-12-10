import pytest
from crex_scraper_python.src.app import app, scraper_service

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_status_provenance_fields(client):
    # Add a warning
    scraper_service.health.record_reconciliation_warning("Test warning")
    
    response = client.get("/status")
    assert response.status_code == 200
    data = response.get_json()
    
    details = data["data"]["details"]
    assert "reconciliation_warnings" in details
    assert len(details["reconciliation_warnings"]) > 0
    assert "Test warning" in details["reconciliation_warnings"][0]
