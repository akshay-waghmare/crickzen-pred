import asyncio
import time
import logging
from crex_scraper_python.src.browser_pool import AsyncBrowserPool
from crex_scraper_python.src.adapters.crex_adapter import CrexAdapter

# Configure logging to suppress noise
logging.basicConfig(level=logging.WARNING)

async def profile_latency():
    pool = AsyncBrowserPool()
    adapter = CrexAdapter()
    
    print("Initializing browser pool...")
    await pool.setup()
    
    urls = [
        "https://crex.live/scoreboard/TEST/1G/1st-test/1st-test-match", # Example URL
        "https://crex.live/scoreboard/TEST/1G/1st-test/1st-test-match",
        "https://crex.live/scoreboard/TEST/1G/1st-test/1st-test-match",
        "https://crex.live/scoreboard/TEST/1G/1st-test/1st-test-match",
        "https://crex.live/scoreboard/TEST/1G/1st-test/1st-test-match"
    ]
    
    latencies = []
    
    print(f"Profiling {len(urls)} requests...")
    
    for i, url in enumerate(urls):
        start = time.time()
        async with pool.get_context() as context:
            try:
                # We expect this to fail or return partial data if URL is invalid/unreachable in test env
                # But we measure the overhead of browser interaction
                await adapter.fetch_match(context, url)
            except Exception:
                pass # Ignore scrape errors, we want to measure cycle time
        
        duration = time.time() - start
        latencies.append(duration)
        print(f"Request {i+1}: {duration:.4f}s")
        
    avg_latency = sum(latencies) / len(latencies)
    print(f"\nAverage Latency: {avg_latency:.4f}s")
    print(f"Min Latency: {min(latencies):.4f}s")
    print(f"Max Latency: {max(latencies):.4f}s")
    
    await pool.shutdown()

if __name__ == "__main__":
    asyncio.run(profile_latency())
