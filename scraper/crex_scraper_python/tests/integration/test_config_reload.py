import pytest
import os
from unittest.mock import patch
from crex_scraper_python.src.config import ScraperSettings

def test_config_reload_from_env():
    # Initial config
    settings = ScraperSettings.from_env({})
    assert settings.concurrency_cap == 10 # Default
    
    # Simulate env change
    new_env = {"CONCURRENCY_CAP": "20"}
    
    # Reload
    new_settings = ScraperSettings.from_env(new_env)
    assert new_settings.concurrency_cap == 20
    
    # Verify other defaults preserved
    assert new_settings.cache_live_ttl == 15
