import json
from io import StringIO

import pytest
import structlog

from src.config import ScraperSettings
from crex_scraper_python.logging_config import scraper_logging_context, setup_logging
from src.logging.adapters import get_logger


@pytest.fixture(autouse=True)
def reset_structlog_state():
    import src.logging.adapters as adapters

    adapters._IS_CONFIGURED = False
    structlog.reset_defaults()
    structlog.contextvars.clear_contextvars()
    yield
    structlog.contextvars.clear_contextvars()


def _parse_logs(stream: StringIO):
    return [json.loads(line) for line in stream.getvalue().strip().splitlines() if line.strip()]


def test_setup_logging_binds_scraper_id():
    stream = StringIO()
    settings = ScraperSettings(scraper_id="scraper-test", log_level="INFO", log_format="json")
    setup_logging(settings, stream=stream)

    logger = get_logger("test_component")
    logger.info("test.event")

    records = _parse_logs(stream)
    assert len(records) == 1
    record = records[0]
    assert record["scraper_id"] == "scraper-test"
    assert record["match_id"] == "unbound"


def test_scraper_logging_context_sets_match_id():
    stream = StringIO()
    settings = ScraperSettings(scraper_id="scraper-ctx", log_level="INFO", log_format="json")
    setup_logging(settings, stream=stream)

    logger = get_logger("test_component")
    with scraper_logging_context(match_id="match-555"):
        logger.info("context.event")
    logger.info("post.event")

    records = _parse_logs(stream)
    assert len(records) == 2
    assert records[0]["match_id"] == "match-555"
    assert records[0]["scraper_id"] == "scraper-ctx"
    assert records[1]["match_id"] == "unbound"
    assert records[1]["scraper_id"] == "scraper-ctx"
