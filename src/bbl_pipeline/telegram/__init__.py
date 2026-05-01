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
from bbl_pipeline.telegram.live_state_adapter import LiveStateError, LiveSignalState, build_signal_snapshot_from_json, load_live_signal_state
from bbl_pipeline.telegram.storage import PredictionStorage
from bbl_pipeline.telegram.signal_publisher import PublicSignalPublisher, SignalPublishResult
from bbl_pipeline.telegram.signal_review_queue import QueuedSignalDraft, SignalQueueError, SignalReviewQueue
from bbl_pipeline.telegram.signal_runner import SignalAutomationRunner, detect_current_phase
from bbl_pipeline.telegram.message_formatter import (
    format_prematch_prediction,
    format_match_start,
    format_match_result,
)
from bbl_pipeline.telegram.signals import (
    READY_TO_PUBLISH,
    NOT_READY_TO_PUBLISH,
    PHASE_PRE_MATCH,
    PHASE_TOSS,
    PHASE_POWERPLAY,
    PHASE_MID_INNINGS,
    PHASE_DEATH_OVERS,
    PHASE_INNINGS_BREAK,
    PHASE_CHASE_MIDPOINT,
    PHASE_FINAL_REVIEW,
    AccuracyTrackerRow,
    SignalPostDraft,
    SignalSnapshot,
    SourceCheck,
    build_accuracy_tracker_row,
    confidence_label,
    draft_signal,
)

__all__ = [
    "TelegramConfig",
    "load_config",
    "TelegramBotClient",
    "LiveStateError",
    "LiveSignalState",
    "build_signal_snapshot_from_json",
    "load_live_signal_state",
    "PredictionStorage",
    "PublicSignalPublisher",
    "SignalPublishResult",
    "QueuedSignalDraft",
    "SignalQueueError",
    "SignalReviewQueue",
    "SignalAutomationRunner",
    "detect_current_phase",
    "format_prematch_prediction",
    "format_match_start",
    "format_match_result",
    "READY_TO_PUBLISH",
    "NOT_READY_TO_PUBLISH",
    "PHASE_PRE_MATCH",
    "PHASE_TOSS",
    "PHASE_POWERPLAY",
    "PHASE_MID_INNINGS",
    "PHASE_DEATH_OVERS",
    "PHASE_INNINGS_BREAK",
    "PHASE_CHASE_MIDPOINT",
    "PHASE_FINAL_REVIEW",
    "AccuracyTrackerRow",
    "SignalPostDraft",
    "SignalSnapshot",
    "SourceCheck",
    "build_accuracy_tracker_row",
    "confidence_label",
    "draft_signal",
]
