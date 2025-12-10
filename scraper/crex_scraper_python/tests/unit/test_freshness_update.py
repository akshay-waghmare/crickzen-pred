import pytest
import asyncio
import time
from unittest.mock import MagicMock, AsyncMock, patch
from crex_scraper_python.src.crex_scraper import CrexScraperService
from crex_scraper_python.src.scheduler import ScrapeTask

@pytest.mark.asyncio
async def test_freshness_update_on_success():
    """
    Test that freshness timestamp is updated in cache and metrics upon successful scrape.
    """
    # Mock dependencies
    with patch('crex_scraper_python.src.crex_scraper.AsyncBrowserPool') as MockPool, \
         patch('crex_scraper_python.src.crex_scraper.AsyncScheduler') as MockScheduler, \
         patch('crex_scraper_python.src.crex_scraper.ScrapeCache') as MockCache, \
         patch('crex_scraper_python.src.crex_scraper.MetricsCollector') as MockMetrics, \
         patch('crex_scraper_python.src.crex_scraper.HealthGrader') as MockHealth, \
         patch('crex_scraper_python.src.crex_scraper.AdapterRegistry') as MockRegistry:

        # Setup mocks
        mock_cache = AsyncMock()
        MockCache.return_value = mock_cache
        
        mock_metrics = MagicMock()
        MockMetrics.return_value = mock_metrics
        
        mock_registry = MagicMock()
        MockRegistry.return_value = mock_registry
        
        mock_adapter = MagicMock()
        mock_adapter.fetch_match = AsyncMock(return_value={"match_id": "123", "status": "Live"})
        mock_adapter.get_canonical_id.return_value = "123"
        mock_registry.get_adapter.return_value = mock_adapter

        mock_pool = AsyncMock()
        MockPool.return_value = mock_pool
        mock_context = AsyncMock()
        
        # Mock get_context to return an async context manager
        cm = MagicMock()
        cm.__aenter__.return_value = mock_context
        cm.__aexit__.return_value = None
        mock_pool.get_context = MagicMock(return_value=cm)

        # Initialize service
        service = CrexScraperService()
        service.pool = mock_pool
        service.cache = mock_cache
        service.metrics = mock_metrics
        service.registry = mock_registry
        service.health = MockHealth.return_value

        # Create a task
        task = ScrapeTask(match_id="123", url="http://test.com", priority=1, task_type="LIVE")

        # Execute _process_task
        await service._process_task(task)

        # Verify cache.update_freshness was called
        # We expect it to be called with match_id and a timestamp (float)
        assert mock_cache.update_freshness.called
        args = mock_cache.update_freshness.call_args[0]
        assert args[0] == "123"
        assert isinstance(args[1], float)
        
        # Verify metrics.update_freshness was called
        assert mock_metrics.update_freshness.called
        metrics_args = mock_metrics.update_freshness.call_args
        assert metrics_args[0][0] == "123"
        assert metrics_args[0][1] == "crex"
        # The age should be close to 0
        assert metrics_args[0][2] >= 0
