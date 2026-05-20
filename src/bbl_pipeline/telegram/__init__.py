"""
Telegram Prediction Ledger Module.

Provides functionality for posting immutable, timestamped predictions
to a Telegram channel with append-only local storage.

Components:
- config: Environment-based configuration management
- bot_client: Telegram Bot API wrapper
- message_formatter: Message template formatting
- storage: Append-only JSON Lines storage
"""

from bbl_pipeline.telegram.config import TelegramConfig, load_config
from bbl_pipeline.telegram.bot_client import TelegramBotClient
from bbl_pipeline.telegram.storage import PredictionStorage
from bbl_pipeline.telegram.message_formatter import (
    format_prematch_prediction,
    format_match_start,
    format_match_result,
)
from bbl_pipeline.telegram.signals import (
    AccuracyTrackerRow,
    SignalPostDraft,
    SignalSnapshot,
    build_accuracy_tracker_row,
    confidence_label,
    draft_signal,
)

__all__ = [
    "TelegramConfig",
    "load_config",
    "TelegramBotClient",
    "PredictionStorage",
    "format_prematch_prediction",
    "format_match_start",
    "format_match_result",
    "SignalSnapshot",
    "SignalPostDraft",
    "AccuracyTrackerRow",
    "draft_signal",
    "build_accuracy_tracker_row",
    "confidence_label",
]
