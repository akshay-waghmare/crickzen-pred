"""
Telegram configuration management.

Loads and validates Telegram bot configuration from environment variables.
Uses python-decouple for secure environment-based configuration.
"""

from dataclasses import dataclass
from typing import Optional
import re

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
    
    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        self._validate_token()
        self._validate_channel_id()
    
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


def load_config() -> TelegramConfig:
    """
    Load Telegram configuration from environment variables.
    
    Environment Variables:
        TELEGRAM_BOT_TOKEN: Bot token from @BotFather (required)
        TELEGRAM_CHANNEL_ID: Channel username or numeric ID (required)
        TELEGRAM_STORAGE_PATH: Path to storage file (optional)
    
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
    except UndefinedValueError as e:
        raise ConfigError(f"Missing required configuration: {e}")
    
    return TelegramConfig(
        bot_token=bot_token,
        channel_id=channel_id,
        storage_path=storage_path,
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
