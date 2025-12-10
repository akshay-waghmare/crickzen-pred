import pytest
import time
import asyncio
from crex_scraper_python.src.adapters.rate_limit import TokenBucket

@pytest.mark.asyncio
async def test_token_bucket_consume():
    """
    Test token consumption and refill.
    """
    bucket = TokenBucket(capacity=10, refill_rate=10.0)
    
    # Initial state: full
    assert bucket.tokens == 10.0
    
    # Consume 5
    assert bucket.consume(5) is True
    assert bucket.tokens == 5.0
    
    # Consume 6 (should fail)
    assert bucket.consume(6) is False
    # Tokens might have increased slightly due to refill
    assert bucket.tokens >= 5.0
    assert bucket.tokens < 6.0
    
    # Wait for refill (0.1s should give 1 token)
    await asyncio.sleep(0.11)
    bucket._refill() # Manually trigger refill check or call consume
    assert bucket.tokens >= 6.0
    
    # Consume 6 (should succeed now)
    assert bucket.consume(6) is True

@pytest.mark.asyncio
async def test_token_bucket_wait():
    """
    Test wait_for_token.
    """
    bucket = TokenBucket(capacity=1, refill_rate=10.0)
    bucket.consume(1) # Empty it
    
    start = time.time()
    await bucket.wait_for_token(1)
    duration = time.time() - start
    
    # Should wait approx 0.1s
    assert duration >= 0.09
    assert bucket.tokens <= 1.0 # It consumed it? No, wait_for_token consumes it.
