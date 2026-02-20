"""Tests for Telegram bot client."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from bbl_pipeline.telegram.bot_client import (
    TelegramBotClient,
    PostResult,
    TelegramAPIError,
)
from bbl_pipeline.telegram.config import TelegramConfig


@pytest.fixture
def config():
    """Create a test configuration."""
    return TelegramConfig(
        bot_token="123456789:ABCdefGHIjklMNOpqrsTUVwxyz",
        channel_id="@test_channel",
    )


@pytest.fixture
def client(config):
    """Create a test bot client."""
    return TelegramBotClient(config)


class TestPostResult:
    """Tests for PostResult dataclass."""
    
    def test_success_result(self):
        """Test creating a successful result."""
        result = PostResult(
            success=True,
            message_id=12345,
            timestamp=datetime.now(),
        )
        assert result.success is True
        assert result.message_id == 12345
        assert result.error_message is None
    
    def test_error_result(self):
        """Test creating an error result."""
        result = PostResult(
            success=False,
            error_message="Network error",
            error_type="network_error",
        )
        assert result.success is False
        assert result.message_id is None
        assert result.error_message == "Network error"
        assert result.error_type == "network_error"


class TestTelegramBotClient:
    """Tests for TelegramBotClient class."""
    
    def test_client_initialization(self, config):
        """Test client initialization."""
        client = TelegramBotClient(config)
        assert client.config == config
        assert client._bot is None  # Lazy initialization
    
    @pytest.mark.asyncio
    async def test_send_message_async_success(self, client):
        """Test successful async message sending."""
        mock_message = MagicMock()
        mock_message.message_id = 12345
        mock_message.date = datetime(2026, 1, 27, 10, 30, 0)
        
        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock(return_value=mock_message)
        client._bot = mock_bot
        
        result = await client.send_message_async("Test message")
        
        assert result.success is True
        assert result.message_id == 12345
        mock_bot.send_message.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_send_message_async_unauthorized(self, client):
        """Test handling of unauthorized error."""
        from telegram.error import Forbidden
        
        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock(side_effect=Forbidden("Invalid token"))
        client._bot = mock_bot
        
        result = await client.send_message_async("Test message")
        
        assert result.success is False
        assert result.error_type == "unauthorized"
        assert "not authorized" in result.error_message.lower()
    
    @pytest.mark.asyncio
    async def test_send_message_async_network_error(self, client):
        """Test handling of network error."""
        from telegram.error import NetworkError
        
        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock(side_effect=NetworkError("Connection failed"))
        client._bot = mock_bot
        
        result = await client.send_message_async("Test message")
        
        assert result.success is False
        assert result.error_type == "network_error"
        assert "network" in result.error_message.lower()
    
    @pytest.mark.asyncio
    async def test_send_message_async_bad_request(self, client):
        """Test handling of bad request error."""
        from telegram.error import BadRequest
        
        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock(side_effect=BadRequest("Invalid chat_id"))
        client._bot = mock_bot
        
        result = await client.send_message_async("Test message")
        
        assert result.success is False
        assert result.error_type == "bad_request"
    
    @pytest.mark.asyncio
    async def test_test_connection_async_success(self, client):
        """Test successful connection test."""
        mock_user = MagicMock()
        mock_user.username = "test_bot"
        
        mock_bot = MagicMock()
        mock_bot.get_me = AsyncMock(return_value=mock_user)
        client._bot = mock_bot
        
        result = await client.test_connection_async()
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_test_connection_async_failure(self, client):
        """Test failed connection test."""
        from telegram.error import TelegramError
        
        mock_bot = MagicMock()
        mock_bot.get_me = AsyncMock(side_effect=TelegramError("Connection failed"))
        client._bot = mock_bot
        
        result = await client.test_connection_async()
        
        assert result is False
