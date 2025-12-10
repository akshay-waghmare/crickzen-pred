#!/usr/bin/env python3
"""Cleanup script for expired diagnostic artifacts.

Run this script via cron or scheduled task to enforce retention policies.
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from crex_scraper_python.logging_config import setup_logging
from .loggers.adapters import get_logger
from .loggers.diagnostics import prune_expired_artifacts

setup_logging()
logger = get_logger(component="artifact_cleanup")

def main():
    """Execute artifact cleanup based on configured retention."""
    logger.info("cleanup.start")
    
    try:
        prune_expired_artifacts()
        logger.info("cleanup.complete")
        return 0
    except Exception as e:
        logger.error("cleanup.error", metadata={"error": str(e)})
        return 1

if __name__ == "__main__":
    sys.exit(main())
