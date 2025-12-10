import pytest
import asyncio
import psutil
from crex_scraper_python.src.browser_pool import AsyncBrowserPool

@pytest.mark.asyncio
async def test_pid_stability():
    """
    Verify that PIDs do not leak over many context creations.
    """
    pool = AsyncBrowserPool()
    await pool.setup()
    
    process = psutil.Process()
    initial_pids = len(process.children(recursive=True))
    
    # Run 50 cycles (reduced from 200 for CI speed, but enough to show leaks)
    for _ in range(50):
        async with pool.get_context() as context:
            page = await context.new_page()
            await page.close()
            
    # Allow some time for cleanup
    await asyncio.sleep(1)
    
    final_pids = len(process.children(recursive=True))
    
    await pool.shutdown()
    
    # We allow a small variance, but it shouldn't grow linearly
    # 50 cycles * 1 process leak = +50 PIDs. 
    # If we are within +5 of initial, we are likely stable.
    assert final_pids <= initial_pids + 5, f"PID leak detected: {initial_pids} -> {final_pids}"
