import logging
import sys
import structlog
from typing import Any

def configure_logging(log_level: str = "INFO", json_format: bool = False) -> None:
    """
    Configure structured logging for the application.
    
    Args:
        log_level: The logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        json_format: Whether to output logs in JSON format (True) or pretty console format (False).
    """
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    if json_format:
        processors = shared_processors + [
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]
    else:
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(),
        ]

    structlog.configure(
        processors=processors,
        logger_factory=structlog.PrintLoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(log_level.upper())),
        cache_logger_on_first_use=True,
    )
    
    # Configure standard logging to redirect to structlog or stdout
    # This ensures libraries using standard logging are captured if needed, 
    # though PrintLoggerFactory handles the main app logs.
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level.upper(),
    )

def get_logger(name: str = None) -> structlog.stdlib.BoundLogger:
    """
    Get a structured logger instance.
    """
    return structlog.get_logger(name)
