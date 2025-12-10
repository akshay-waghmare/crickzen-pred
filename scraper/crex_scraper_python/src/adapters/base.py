"""
Base Source Adapter Interface.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from playwright.async_api import BrowserContext
from .reliability import ReliabilityTracker

class SourceAdapter(ABC):
    """
    Abstract base class for scraper source adapters.
    """

    def __init__(self):
        self.reliability = ReliabilityTracker()

    @property
    @abstractmethod
    def domain(self) -> str:
        """Return the domain name (e.g., 'crex', 'espn')."""
        pass

    @abstractmethod
    def get_canonical_id(self, raw_id: str) -> str:
        """Convert source-specific ID to canonical ID."""
        pass

    @abstractmethod
    async def fetch_match(self, context: BrowserContext, url: str) -> Dict[str, Any]:
        """
        Fetch match data from the given URL using the browser context.
        Returns a dictionary of match data.
        """
        pass

    @abstractmethod
    async def discover_matches(self, context: BrowserContext) -> Dict[str, str]:
        """
        Discover live/upcoming matches.
        Returns a dict of {match_id: url}.
        """
        pass
