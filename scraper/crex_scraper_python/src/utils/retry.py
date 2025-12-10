"""
Retry Utilities.
"""

import logging
import backoff
import asyncio
from typing import Type, Tuple, Optional

logger = logging.getLogger(__name__)

def async_retry(
    exceptions: Tuple[Type[Exception], ...],
    tries: int = 3,
    delay: float = 1.0,
    backoff_factor: float = 2.0,
    logger: Optional[logging.Logger] = None
):
    """
    Decorator for async retries with exponential backoff.
    """
    def decorator(func):
        @backoff.on_exception(
            backoff.expo,
            exceptions,
            max_tries=tries,
            base=backoff_factor,
            factor=delay,
            logger=logger
        )
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)
        return wrapper
    return decorator
