import pytest
import asyncio
import time
from unittest.mock import MagicMock, AsyncMock, patch
from crex_scraper_python.src.crex_scraper import CrexScraperService
from crex_scraper_python.src.scheduler import ScrapeTask

@pytest.mark.asyncio
async def test_multi_match_freshness_sla():
    """
    Integration test: Simulate multiple matches and verify freshness SLA.
    """
    with patch('crex_scraper_python.src.crex_scraper.AsyncBrowserPool') as MockPool, \
         patch('crex_scraper_python.src.crex_scraper.ScrapeCache') as MockCache, \
         patch('crex_scraper_python.src.crex_scraper.AdapterRegistry') as MockRegistry:

        # Setup mocks
        mock_pool = AsyncMock()
        MockPool.return_value = mock_pool
        mock_context = AsyncMock()
        
        # Mock get_context to return an async context manager
        cm = MagicMock()
        cm.__aenter__.return_value = mock_context
        cm.__aexit__.return_value = None
        mock_pool.get_context = MagicMock(return_value=cm)

        mock_cache = AsyncMock()
        MockCache.return_value = mock_cache
        mock_cache.compute_delta = MagicMock(return_value={})
        
        mock_registry = MagicMock()
        MockRegistry.return_value = mock_registry
        
        mock_adapter = MagicMock()
        mock_adapter.fetch_match = AsyncMock(return_value={"match_id": "123", "status": "Live"})
        mock_adapter.get_canonical_id.side_effect = lambda x: x
        mock_registry.get_adapter.return_value = mock_adapter

        # Initialize service
        service = CrexScraperService()
        service.pool = mock_pool
        service.cache = mock_cache
        service.registry = mock_registry
        
        # We use real HealthGrader and MetricsCollector (default init)
        # But we need to make sure they are initialized in service.__init__
        # which they are.
        
        # Simulate 5 matches
        tasks = []
        for i in range(5):
            task = ScrapeTask(match_id=f"match_{i}", url=f"http://test.com/{i}", priority=1, task_type="LIVE")
            tasks.append(task)
            
        # Process tasks sequentially (simulating worker loop)
        for task in tasks:
            # Simulate some processing time
            await asyncio.sleep(0.01)
            await service._process_task(task)
            
        # Check health stats
        stats = service.health.get_freshness_stats()
        
        # We recorded 0.0 freshness for all 5 matches
        assert stats["p50"] == 0.0
        assert stats["p99"] == 0.0
        
        # Verify SLA (e.g. < 5s)
        assert stats["p99"] < 5.0
