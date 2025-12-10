"""
Reliability Tracker for Scraper Sources.
Calculates reliability scores based on success/failure history.
"""

import time
from collections import deque
from typing import Deque

class ReliabilityTracker:
    """
    Tracks reliability of a source or domain.
    Score is 0-100 based on recent success rate.
    """

    def __init__(self, window_size: int = 50):
        self.window_size = window_size
        self._history: Deque[bool] = deque(maxlen=window_size)
        self._last_update = time.time()

    def record_success(self):
        """Record a successful operation."""
        self._history.append(True)
        self._last_update = time.time()

    def record_failure(self):
        """Record a failed operation."""
        self._history.append(False)
        self._last_update = time.time()

    def get_score(self) -> int:
        """
        Calculate reliability score (0-100).
        """
        if not self._history:
            return 100
        
        success_count = sum(1 for x in self._history if x)
        return int((success_count / len(self._history)) * 100)
