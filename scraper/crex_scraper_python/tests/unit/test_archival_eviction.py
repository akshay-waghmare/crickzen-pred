import pytest
from unittest.mock import AsyncMock
from crex_scraper_python.src.cache import ScrapeCache

@pytest.mark.asyncio
async def test_archival_eviction():
    cache = ScrapeCache()
    cache._redis = AsyncMock()
    
    match_id = "test_match_completed"
    
    await cache.archive_match(match_id)
    
    # Verify delete called for snapshot and freshness
    expected_keys = [
        f"match:{match_id}:snapshot",
        f"match:{match_id}:freshness"
    ]
    cache._redis.delete.assert_called_with(*expected_keys)
