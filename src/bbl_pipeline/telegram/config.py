"""
Telegram configuration management.

Loads and validates Telegram bot configuration from environment variables.
Uses python-decouple for secure environment-based configuration.
"""

from dataclasses import dataclass
from typing import Optional
import re
from urllib.parse import urlparse

from decouple import config, UndefinedValueError


# Token format: digits:alphanumeric (e.g., 123456789:ABCdefGHIjklMNOpqrsTUVwxyz)
TOKEN_PATTERN = re.compile(r"^\d+:[A-Za-z0-9_-]+$")


class ConfigError(Exception):
    """Raised when configuration is invalid or missing."""
    pass


@dataclass
class TelegramConfig:
    """Telegram bot configuration."""
    
    bot_token: str
    channel_id: str
    storage_path: str = "data/telegram_predictions.jsonl"
    signal_tracker_path: str = "data/telegram_signal_accuracy_tracker.csv"
    public_dashboard_base_url: Optional[str] = None
    signal_source_json: str = "data/ipl_live_ml.json"
    signal_queue_path: str = "data/telegram_signal_queue.json"
    
    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        self._validate_token()
        self._validate_channel_id()
        self._validate_public_dashboard_base_url()
    
    def _validate_token(self) -> None:
        """Validate bot token format."""
        if not self.bot_token:
            raise ConfigError("TELEGRAM_BOT_TOKEN cannot be empty")
        if not TOKEN_PATTERN.match(self.bot_token):
            raise ConfigError(
                "TELEGRAM_BOT_TOKEN has invalid format. "
                "Expected format: 123456789:ABCdefGHIjklMNOpqrsTUVwxyz"
            )
    
    def _validate_channel_id(self) -> None:
        """Validate channel ID format."""
        if not self.channel_id:
            raise ConfigError("TELEGRAM_CHANNEL_ID cannot be empty")
        # Valid formats: @channel_name OR numeric ID like -1001234567890
        if not (
            self.channel_id.startswith("@") or
            self.channel_id.lstrip("-").isdigit()
        ):
            raise ConfigError(
                "TELEGRAM_CHANNEL_ID has invalid format. "
                "Expected: @channel_name OR numeric ID (e.g., -1001234567890)"
            )

    def _validate_public_dashboard_base_url(self) -> None:
        """Validate dashboard CTA URL when configured."""
        if not self.public_dashboard_base_url:
            return
        parsed = urlparse(self.public_dashboard_base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ConfigError(
                "PUBLIC_DASHBOARD_BASE_URL has invalid format. "
                "Expected a full URL like https://app.crickzen.com/dashboard"
            )


def load_config() -> TelegramConfig:
    """
    Load Telegram configuration from environment variables.
    
    Environment Variables:
        TELEGRAM_BOT_TOKEN: Bot token from @BotFather (required)
        TELEGRAM_CHANNEL_ID: Channel username or numeric ID (required)
        TELEGRAM_STORAGE_PATH: Path to storage file (optional)
        TELEGRAM_SIGNAL_TRACKER_PATH: Path to accuracy tracker CSV (optional)
        PUBLIC_DASHBOARD_BASE_URL: CTA URL appended to public signals (optional)
        TELEGRAM_SIGNAL_SOURCE_JSON: Live predictor JSON used to prefill signals (optional)
        TELEGRAM_SIGNAL_QUEUE_PATH: Review queue file used by the watcher/approver (optional)
    
    Returns:
        TelegramConfig: Validated configuration object
        
    Raises:
        ConfigError: If required config is missing or invalid
    """
    try:
        bot_token = config("TELEGRAM_BOT_TOKEN")
        channel_id = config("TELEGRAM_CHANNEL_ID")
        storage_path = config(
            "TELEGRAM_STORAGE_PATH", 
            default="data/telegram_predictions.jsonl"
        )
        signal_tracker_path = config(
            "TELEGRAM_SIGNAL_TRACKER_PATH",
            default="data/telegram_signal_accuracy_tracker.csv",
        )
        public_dashboard_base_url = config(
            "PUBLIC_DASHBOARD_BASE_URL",
            default="",
        ).strip() or None
        signal_source_json = config(
            "TELEGRAM_SIGNAL_SOURCE_JSON",
            default="data/ipl_live_ml.json",
        )
        signal_queue_path = config(
            "TELEGRAM_SIGNAL_QUEUE_PATH",
            default="data/telegram_signal_queue.json",
        )
    except UndefinedValueError as e:
        raise ConfigError(f"Missing required configuration: {e}")
    
    return TelegramConfig(
        bot_token=bot_token,
        channel_id=channel_id,
        storage_path=storage_path,
        signal_tracker_path=signal_tracker_path,
        public_dashboard_base_url=public_dashboard_base_url,
        signal_source_json=signal_source_json,
        signal_queue_path=signal_queue_path,
    )


def is_configured() -> bool:
    """
    Check if Telegram configuration is available.
    
    Returns:
        bool: True if configuration can be loaded, False otherwise
    """
    try:
        load_config()
        return True
    except ConfigError:
        return False
