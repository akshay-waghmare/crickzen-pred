import pytest
import json
from crex_scraper_python.src.health import HealthGrader, HealthSummary, HealthState

def test_health_summary_serialization():
    grader = HealthGrader()
    summary = grader.get_summary()
    
    # Convert to dict (simulating what Flask/FastAPI does via dataclasses or custom encoder)
    # Since HealthSummary is a dataclass, we can use asdict or just access fields.
    # But we want to ensure it's JSON serializable.
    
    # We need to handle Enum serialization if using standard json.dumps
    # Flask's jsonify handles some of this, but let's verify the structure.
    
    data = {
        "state": summary.state.value,
        "score": summary.score,
        "uptime_seconds": summary.uptime_seconds,
        "pids_count": summary.pids_count,
        "memory_usage_mb": summary.memory_usage_mb,
        "last_scrape_timestamp": summary.last_scrape_timestamp,
        "active_matches": summary.active_matches,
        "details": summary.details
    }
    
    json_str = json.dumps(data)
    parsed = json.loads(json_str)
    
    assert parsed["state"] == "healthy"
    assert parsed["score"] == 100
    assert "uptime_seconds" in parsed
