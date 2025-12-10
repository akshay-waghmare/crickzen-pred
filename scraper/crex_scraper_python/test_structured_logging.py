#!/usr/bin/env python
"""
Test script to verify structured logging with correlation IDs.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from crex_scraper_python.logging_config import setup_logging
from src.logging.adapters import get_logger, bind_correlation_id
from src.crex_scraper import scrape

if __name__ == "__main__":
    setup_logging()
    
    # Bind a correlation ID
    correlation_id = bind_correlation_id("test-manual-001")
    print(f"\n🔗 Testing with Correlation ID: {correlation_id}\n")
    
    # Try to scrape a test URL
    test_url = "https://crex.live"
    
    logger = get_logger("test_script")
    logger.info("test.start", metadata={"test_url": test_url})
    
    try:
        result = scrape(test_url)
        logger.info("test.success", metadata={"result_count": len(result) if result else 0})
        print(f"\n✅ Scrape completed! Found {len(result) if result else 0} URLs")
    except Exception as e:
        logger.error("test.failed", metadata={"error": str(e), "error_type": type(e).__name__})
        print(f"\n❌ Scrape failed: {e}")
    
    print(f"\n📝 Check the logs above - all events should have correlation_id: {correlation_id}")
    print(f"📁 Check artifacts/ directory for any captured HTML snapshots\n")
