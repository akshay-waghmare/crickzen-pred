import pytest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from crex_scraper_python.src.crex_scraper import CrexScraperService
from crex_scraper_python.src.scheduler import ScrapeTask

@pytest.mark.asyncio
async def test_overload_plateau():
    """
    Integration test: Submit many tasks and verify queue size plateaus.
    """
    with patch('crex_scraper_python.src.crex_scraper.AsyncBrowserPool') as MockPool, \
         patch('crex_scraper_python.src.crex_scraper.ScrapeCache') as MockCache, \
         patch('crex_scraper_python.src.crex_scraper.AdapterRegistry') as MockRegistry, \
         patch('crex_scraper_python.src.scheduler.get_settings') as mock_settings:

        # Setup settings
        mock_settings.return_value.max_queue_size = 5
        mock_settings.return_value.rate_limit_burst = 100
        mock_settings.return_value.rate_limit_tokens_per_sec = 100.0
        mock_settings.return_value.concurrency_cap = 1

        # Setup mocks
        mock_pool = AsyncMock()
        MockPool.return_value = mock_pool
        mock_pool.get_context.return_value.__aenter__.return_value = AsyncMock()
        
        mock_cache = AsyncMock()
        MockCache.return_value = mock_cache
        
        mock_registry = MagicMock()
        MockRegistry.return_value = mock_registry
        
        service = CrexScraperService()
        # We don't start the service (workers), so tasks will pile up in queue
        
        # Submit 10 tasks
        results = []
        for i in range(10):
            res = await service.submit_task(f"match_{i}", f"url_{i}")
            results.append(res)
            
        # Verify queue size is capped at 5
        assert service.scheduler.qsize == 5
        
        # Verify first 5 succeeded, last 5 failed (dropped)
        assert all(results[:5])
        assert not any(results[5:])
