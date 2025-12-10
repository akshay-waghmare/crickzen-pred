"""Minimal unit tests for logging adapters."""

import json
from io import StringIO

import pytest
import structlog

from src.logging.adapters import (
    bind_correlation_id,
    clear_correlation_id,
    configure_logging,
    get_logger,
)


@pytest.fixture(autouse=True)
def reset_logging():
    """Reset structlog configuration before each test."""
    # Reset the global configuration flag
    import src.logging.adapters as adapters_module
    adapters_module._IS_CONFIGURED = False
    
    # Reset structlog's global state
    structlog.reset_defaults()
    
    yield
    
    # Cleanup after test
    clear_correlation_id()


def test_configure_logging_produces_json():
    """Verify logging outputs valid JSON."""
    stream = StringIO()
    configure_logging(stream=stream)
    
    logger = get_logger("test_component")
    logger.info("test.event", metadata={"key": "value"})
    
    output = stream.getvalue().strip()
    log_entry = json.loads(output)
    
    assert log_entry["event"] == "test.event"
    assert log_entry["component"] == "test_component"
    assert log_entry["level"] == "INFO"
    assert "timestamp" in log_entry
    assert "correlation_id" in log_entry
    assert log_entry["metadata"]["key"] == "value"
    assert log_entry["scraper_id"] == "unknown"
    assert log_entry["match_id"] == "unbound"


def test_correlation_id_binding():
    """Verify correlation ID can be bound and retrieved."""
    correlation_id = bind_correlation_id()
    
    stream = StringIO()
    configure_logging(stream=stream)
    logger = get_logger("test")
    logger.info("test.correlation")
    
    output = stream.getvalue().strip()
    log_entry = json.loads(output)
    
    assert log_entry["correlation_id"] == correlation_id


def test_metadata_captures_extra_fields():
    """Verify unexpected keys are moved to metadata."""
    stream = StringIO()
    configure_logging(stream=stream)
    
    logger = get_logger("test")
    logger.info("test.extras", unexpected_field="should_be_in_metadata")
    
    output = stream.getvalue().strip()
    log_entry = json.loads(output)
    
    assert "unexpected_field" not in log_entry
    assert log_entry["metadata"]["unexpected_field"] == "should_be_in_metadata"
