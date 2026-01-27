"""
Telegram Bot API client.

Provides a wrapper for posting messages to Telegram channels
with proper error handling and retry logic.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import logging

from telegram import Bot
from telegram.error import TelegramError, NetworkError, Forbidden, BadRequest

from bbl_pipeline.telegram.config import TelegramConfig


logger = logging.getLogger(__name__)


class TelegramAPIError(Exception):
    """Raised when Telegram API call fails."""
    
    def __init__(self, message: str, error_type: str = "unknown"):
        super().__init__(message)
        self.error_type = error_type


@dataclass
class PostResult:
    """Result of posting a message to Telegram."""
    
    success: bool
    message_id: Optional[int] = None
    timestamp: Optional[datetime] = None
    error_message: Optional[str] = None
    error_type: Optional[str] = None


class TelegramBotClient:
    """Client for posting messages to Telegram channels."""
    
    def __init__(self, config: TelegramConfig):
        """
        Initialize the Telegram bot client.
        
        Args:
            config: Telegram configuration with bot token and channel ID
        """
        self.config = config
        self._bot: Optional[Bot] = None
    
    @property
    def bot(self) -> Bot:
        """Lazy initialization of Bot instance."""
        if self._bot is None:
            self._bot = Bot(token=self.config.bot_token)
        return self._bot
    
    async def send_message_async(
        self,
        text: str,
        parse_mode: str = "HTML",
        disable_web_page_preview: bool = True,
    ) -> PostResult:
        """
        Send a message to the configured Telegram channel (async).
        
        Args:
            text: Message text to send
            parse_mode: Telegram parse mode ("HTML" or "MarkdownV2")
            disable_web_page_preview: Whether to disable link previews
            
        Returns:
            PostResult: Result containing message_id and timestamp on success
        """
        try:
            message = await self.bot.send_message(
                chat_id=self.config.channel_id,
                text=text,
                parse_mode=parse_mode,
                disable_web_page_preview=disable_web_page_preview,
            )
            
            logger.info(
                "Message posted to Telegram",
                extra={
                    "message_id": message.message_id,
                    "channel_id": self.config.channel_id,
                }
            )
            
            return PostResult(
                success=True,
                message_id=message.message_id,
                timestamp=message.date,
            )
            
        except Forbidden as e:
            logger.error(f"Telegram authorization failed: {e}")
            return PostResult(
                success=False,
                error_message="Bot is not authorized. Check bot token and channel permissions.",
                error_type="unauthorized",
            )
            
        except BadRequest as e:
            logger.error(f"Telegram bad request: {e}")
            return PostResult(
                success=False,
                error_message=f"Invalid request: {str(e)}",
                error_type="bad_request",
            )
            
        except NetworkError as e:
            logger.error(f"Telegram network error: {e}")
            return PostResult(
                success=False,
                error_message="Network error. Check your internet connection and try again.",
                error_type="network_error",
            )
            
        except TelegramError as e:
            logger.error(f"Telegram API error: {e}")
            return PostResult(
                success=False,
                error_message=f"Telegram API error: {str(e)}",
                error_type="telegram_error",
            )
    
    def send_message(
        self,
        text: str,
        parse_mode: str = "HTML",
        disable_web_page_preview: bool = True,
    ) -> PostResult:
        """
        Send a message to the configured Telegram channel (sync wrapper).
        
        This is a synchronous wrapper around send_message_async for
        easier integration with Streamlit.
        
        Args:
            text: Message text to send
            parse_mode: Telegram parse mode ("HTML" or "MarkdownV2")
            disable_web_page_preview: Whether to disable link previews
            
        Returns:
            PostResult: Result containing message_id and timestamp on success
        """
        import asyncio
        
        try:
            # Get or create event loop
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            # Run async method
            if loop.is_running():
                # If loop is already running (e.g., in Streamlit), 
                # create a new loop in a thread
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        self.send_message_async(text, parse_mode, disable_web_page_preview)
                    )
                    return future.result()
            else:
                return loop.run_until_complete(
                    self.send_message_async(text, parse_mode, disable_web_page_preview)
                )
                
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return PostResult(
                success=False,
                error_message=str(e),
                error_type="unknown",
            )
    
    async def test_connection_async(self) -> bool:
        """
        Test the Telegram bot connection (async).
        
        Returns:
            bool: True if bot can connect and access the channel
        """
        try:
            me = await self.bot.get_me()
            logger.info(f"Connected as @{me.username}")
            return True
        except TelegramError as e:
            logger.error(f"Connection test failed: {e}")
            return False
    
    def test_connection(self) -> bool:
        """
        Test the Telegram bot connection (sync wrapper).
        
        Returns:
            bool: True if bot can connect and access the channel
        """
        import asyncio
        
        try:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, self.test_connection_async())
                    return future.result()
            else:
                return loop.run_until_complete(self.test_connection_async())
                
        except Exception as e:
            logger.error(f"Connection test error: {e}")
            return False
