import pytest
import asyncio
from unittest.mock import MagicMock, patch
from crex_scraper_python.src.scheduler import AsyncScheduler

@pytest.mark.asyncio
async def test_scheduler_queue_bound():
    """
    Test that scheduler drops tasks when queue is full.
    """
    with patch('crex_scraper_python.src.scheduler.get_settings') as mock_settings:
        mock_settings.return_value.max_queue_size = 2
        mock_settings.return_value.rate_limit_burst = 100
        mock_settings.return_value.rate_limit_tokens_per_sec = 100.0
        
        scheduler = AsyncScheduler()
        
        # Fill queue
        assert await scheduler.enqueue("1", "url1", "LIVE") is True
        assert await scheduler.enqueue("2", "url2", "LIVE") is True
        
        # Try to add 3rd task
        assert await scheduler.enqueue("3", "url3", "LIVE") is False
        
        # Verify queue size
        assert scheduler.qsize == 2
