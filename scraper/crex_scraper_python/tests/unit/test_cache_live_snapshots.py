import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from crex_scraper_python.src.cache import ScrapeCache

@pytest.mark.asyncio
async def test_snapshot_caching_live_ttl():
    """
    Test that snapshots are cached with the correct TTL.
    """
    with patch('crex_scraper_python.src.cache.redis.from_url') as mock_redis_cls:
        mock_redis = AsyncMock()
        mock_redis_cls.return_value = mock_redis
        
        cache = ScrapeCache()
        # Mock settings
        cache.settings = MagicMock()
        cache.settings.redis_url = "redis://localhost"
        
        await cache.connect()
        
        match_id = "test_match_1"
        data = {"id": match_id, "score": "100/2"}
        ttl = 15
        
        # Test set_snapshot
        await cache.set_snapshot(match_id, data, ttl=ttl)
        
        # Verify redis.set called with ex=ttl
        mock_redis.set.assert_called_with(
            f"match:{match_id}:snapshot",
            json.dumps(data),
            ex=ttl
        )

@pytest.mark.asyncio
async def test_snapshot_retrieval():
    """
    Test retrieving a snapshot.
    """
    with patch('crex_scraper_python.src.cache.redis.from_url') as mock_redis_cls:
        mock_redis = AsyncMock()
        mock_redis_cls.return_value = mock_redis
        
        cache = ScrapeCache()
        await cache.connect()
        
        match_id = "test_match_1"
        data = {"id": match_id, "score": "100/2"}
        
        # Mock redis.get return value
        mock_redis.get.return_value = json.dumps(data)
        
        result = await cache.get_snapshot(match_id)
        assert result == data
        mock_redis.get.assert_called_with(f"match:{match_id}:snapshot")

@pytest.mark.asyncio
async def test_snapshot_miss():
    """
    Test retrieving a missing snapshot.
    """
    with patch('crex_scraper_python.src.cache.redis.from_url') as mock_redis_cls:
        mock_redis = AsyncMock()
        mock_redis_cls.return_value = mock_redis
        
        cache = ScrapeCache()
        await cache.connect()
        
        mock_redis.get.return_value = None
        
        result = await cache.get_snapshot("missing_id")
        assert result is None
