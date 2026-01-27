"""Tests for Telegram configuration."""

import pytest
from unittest.mock import patch, MagicMock

from bbl_pipeline.telegram.config import (
    TelegramConfig,
    ConfigError,
    load_config,
    is_configured,
)


class TestTelegramConfig:
    """Tests for TelegramConfig dataclass."""
    
    def test_valid_config(self):
        """Test creating config with valid values."""
        config = TelegramConfig(
            bot_token="123456789:ABCdefGHIjklMNOpqrsTUVwxyz",
            channel_id="@test_channel",
        )
        assert config.bot_token == "123456789:ABCdefGHIjklMNOpqrsTUVwxyz"
        assert config.channel_id == "@test_channel"
        assert config.storage_path == "data/telegram_predictions.jsonl"
    
    def test_valid_numeric_channel_id(self):
        """Test config with numeric channel ID."""
        config = TelegramConfig(
            bot_token="123456789:ABCdefGHIjklMNOpqrsTUVwxyz",
            channel_id="-1001234567890",
        )
        assert config.channel_id == "-1001234567890"
    
    def test_custom_storage_path(self):
        """Test config with custom storage path."""
        config = TelegramConfig(
            bot_token="123456789:ABCdefGHIjklMNOpqrsTUVwxyz",
            channel_id="@test_channel",
            storage_path="custom/path.jsonl",
        )
        assert config.storage_path == "custom/path.jsonl"
    
    def test_empty_token_raises_error(self):
        """Test that empty token raises ConfigError."""
        with pytest.raises(ConfigError, match="cannot be empty"):
            TelegramConfig(
                bot_token="",
                channel_id="@test_channel",
            )
    
    def test_invalid_token_format_raises_error(self):
        """Test that invalid token format raises ConfigError."""
        with pytest.raises(ConfigError, match="invalid format"):
            TelegramConfig(
                bot_token="invalid_token",
                channel_id="@test_channel",
            )
    
    def test_empty_channel_id_raises_error(self):
        """Test that empty channel ID raises ConfigError."""
        with pytest.raises(ConfigError, match="cannot be empty"):
            TelegramConfig(
                bot_token="123456789:ABCdefGHIjklMNOpqrsTUVwxyz",
                channel_id="",
            )
    
    def test_invalid_channel_id_format_raises_error(self):
        """Test that invalid channel ID format raises ConfigError."""
        with pytest.raises(ConfigError, match="invalid format"):
            TelegramConfig(
                bot_token="123456789:ABCdefGHIjklMNOpqrsTUVwxyz",
                channel_id="invalid_channel",
            )


class TestLoadConfig:
    """Tests for load_config function."""
    
    @patch.dict("os.environ", {
        "TELEGRAM_BOT_TOKEN": "123456789:ABCdefGHIjklMNOpqrsTUVwxyz",
        "TELEGRAM_CHANNEL_ID": "@test_channel",
    })
    def test_load_config_from_env(self):
        """Test loading config from environment variables."""
        config = load_config()
        assert config.bot_token == "123456789:ABCdefGHIjklMNOpqrsTUVwxyz"
        assert config.channel_id == "@test_channel"
    
    @patch.dict("os.environ", {
        "TELEGRAM_BOT_TOKEN": "123456789:ABCdefGHIjklMNOpqrsTUVwxyz",
        "TELEGRAM_CHANNEL_ID": "@test_channel",
        "TELEGRAM_STORAGE_PATH": "custom/storage.jsonl",
    })
    def test_load_config_with_custom_storage(self):
        """Test loading config with custom storage path."""
        config = load_config()
        assert config.storage_path == "custom/storage.jsonl"
    
    @patch.dict("os.environ", {}, clear=True)
    def test_load_config_missing_token_raises_error(self):
        """Test that missing token raises ConfigError."""
        with pytest.raises(ConfigError, match="Missing required"):
            load_config()


class TestIsConfigured:
    """Tests for is_configured function."""
    
    @patch.dict("os.environ", {
        "TELEGRAM_BOT_TOKEN": "123456789:ABCdefGHIjklMNOpqrsTUVwxyz",
        "TELEGRAM_CHANNEL_ID": "@test_channel",
    })
    def test_is_configured_returns_true(self):
        """Test is_configured returns True when config is valid."""
        assert is_configured() is True
    
    @patch.dict("os.environ", {}, clear=True)
    def test_is_configured_returns_false_when_missing(self):
        """Test is_configured returns False when config is missing."""
        assert is_configured() is False
