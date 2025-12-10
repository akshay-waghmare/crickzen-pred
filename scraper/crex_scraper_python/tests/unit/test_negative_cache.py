import pytest
from unittest.mock import AsyncMock
from crex_scraper_python.src.cache import ScrapeCache

@pytest.mark.asyncio
async def test_negative_cache_expiry():
    cache = ScrapeCache()
    cache._redis = AsyncMock()
    
    match_id = "test_match_1"
    
    # Test set
    await cache.set_negative_cache(match_id, ttl=60)
    cache._redis.set.assert_called_with(f"match:{match_id}:missing", "1", ex=60)
    
    # Test check (exists)
    cache._redis.exists.return_value = 1
    assert await cache.is_negative_cached(match_id) is True
    
    # Test check (expired/missing)
    cache._redis.exists.return_value = 0
    assert await cache.is_negative_cached(match_id) is False
