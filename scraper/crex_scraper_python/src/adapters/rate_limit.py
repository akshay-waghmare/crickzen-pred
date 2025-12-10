"""
Token Bucket Rate Limiter.
"""

import time
import asyncio
from dataclasses import dataclass

@dataclass
class TokenBucket:
    capacity: int
    refill_rate: float  # tokens per second
    tokens: float = 0.0
    last_refill: float = 0.0

    def __post_init__(self):
        self.tokens = float(self.capacity)
        self.last_refill = time.time()

    def consume(self, tokens: int = 1) -> bool:
        """
        Attempt to consume tokens. Returns True if successful.
        """
        self._refill()
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    def _refill(self):
        now = time.time()
        delta = now - self.last_refill
        added = delta * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + added)
        self.last_refill = now

    async def wait_for_token(self, tokens: int = 1):
        """
        Wait until enough tokens are available.
        """
        while not self.consume(tokens):
            required = tokens - self.tokens
            wait_time = required / self.refill_rate
            await asyncio.sleep(wait_time)
