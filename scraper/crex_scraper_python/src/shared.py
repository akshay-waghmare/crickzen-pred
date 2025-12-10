# shared.py

# Global dictionary to track scraping tasks
scraping_tasks = {}


def get_config_value(key, default=None):
    """Retrieve a configuration value by key, returning a default if not found."""
    import os
    return os.getenv(key, default)

def log_error(message):
    """Log an error message to the console."""
    import logging
    logging.error(message)

def log_info(message):
    """Log an informational message to the console."""
    import logging
    logging.info(message)

def validate_url(url):
    """Validate a URL format."""
    import re
    regex = re.compile(
        r'^(?:http|ftp)s?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}|'  # ...or ipv4
        r'\[?[A-F0-9]*:[A-F0-9:]+\]?)'  # ...or ipv6
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    return re.match(regex, url) is not None

def format_timestamp(timestamp):
    """Format a timestamp into a readable string."""
    from datetime import datetime
    return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')