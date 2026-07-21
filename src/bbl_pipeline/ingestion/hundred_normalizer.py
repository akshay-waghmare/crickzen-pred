"""Canonical legal-ball normalization for The Hundred.

Cricsheet keeps The Hundred in a T20-compatible JSON shape.  Raw over labels
and delivery positions are therefore traceability fields only: wides and
no-balls can make a raw five-ball block contain more than five deliveries.
This module derives the format clock from legal deliveries instead.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

from ..features.format_config import FormatConfig


@dataclass(frozen=True)
class HundredNormalizationResult:
    """Normalized delivery rows and innings-level validation information."""

    rows: List[Dict[str, Any]]
    legal_balls: int
    anomaly_flags: Tuple[str, ...]


class HundredNormalizationError(ValueError):
    """Raised when a Hundred source record cannot satisfy the format contract."""


def is_legal_delivery(delivery: Dict[str, Any]) -> bool:
    """Return whether a Cricsheet delivery consumes a legal ball."""
    extras = delivery.get("extras") or {}
    return "wides" not in extras and "noballs" not in extras


def _phase_for_ball(legal_ball_index: int, config: FormatConfig) -> str:
    """Map a one-based legal-ball index to the configured five-unit phase."""
    five_index = (legal_ball_index - 1) // config.balls_per_over + 1
    for phase_name in config.phase_names:
        if five_index <= config.phase_thresholds[phase_name]:
            return phase_name
    return config.phase_names[-1]


def _raw_label_anomaly(delivery: Dict[str, Any], config: FormatConfig) -> Optional[str]:
    """Flag a raw ``over.ball`` label that contradicts five-ball notation."""
    label = delivery.get("actual_delivery")
    if label is None:
        return None
    try:
        ball_part = int(str(label).split(".", 1)[1])
    except (IndexError, TypeError, ValueError):
        return "invalid_raw_delivery_label"
    if ball_part > config.balls_per_over:
        return "raw_ball_label_exceeds_set_size"
    return None


class HundredNormalizer:
    """Normalize one Hundred innings without trusting raw over coordinates."""

    def __init__(self, config: Optional[FormatConfig] = None) -> None:
        self.config = config or FormatConfig.hundred()
        if self.config.format_name != "hundred":
            raise ValueError("HundredNormalizer requires FormatConfig.hundred()")

    def normalize_innings(
        self,
        innings: Dict[str, Any],
        *,
        match_id: Optional[str] = None,
        innings_number: int = 1,
        gender: Optional[str] = None,
        winner: Optional[str] = None,
        is_super_five: bool = False,
    ) -> HundredNormalizationResult:
        """Return rows with legal-ball and Hundred structural coordinates.

        Illegal deliveries receive ``legal_ball_index=None`` and retain the
        number of legal balls completed after the delivery in
        ``legal_balls_bowled``.  This keeps them available for audit while
        preventing them from becoming training states at a false clock value.
        """
        if innings_number not in {1, 2} and not is_super_five:
            raise HundredNormalizationError("normal innings_number must be 1 or 2")

        rows: List[Dict[str, Any]] = []
        anomalies: set[str] = set()
        legal_count = 0
        raw_index = 0
        for over_data in innings.get("overs", []) or []:
            raw_over = over_data.get("over")
            for delivery in over_data.get("deliveries", []) or []:
                raw_index += 1
                legal = is_legal_delivery(delivery)
                if legal:
                    legal_count += 1
                    if legal_count > self.config.total_balls:
                        anomalies.add("legal_ball_overflow")

                label_anomaly = _raw_label_anomaly(delivery, self.config)
                if label_anomaly:
                    anomalies.add(label_anomaly)

                legal_index = legal_count if legal else None
                if legal_index is not None and legal_index <= self.config.total_balls:
                    five_index = (legal_index - 1) // self.config.scoring_set_size + 1
                    ball_within_five = (legal_index - 1) % self.config.scoring_set_size + 1
                    end_block_index = (legal_index - 1) // self.config.end_change_interval + 1
                    phase = _phase_for_ball(legal_index, self.config)
                    powerplay_active = legal_index <= self.config.powerplay_balls
                else:
                    five_index = None
                    ball_within_five = None
                    end_block_index = None
                    phase = None
                    powerplay_active = False

                stored_legal_index = (
                    legal_index if legal and legal_index <= self.config.total_balls else None
                )
                rows.append({
                    "match_id": match_id,
                    "innings": innings_number,
                    "gender": gender,
                    "gender_female": int(gender == "female") if gender else None,
                    "winner": winner,
                    "is_super_five": is_super_five,
                    "raw_delivery_index": raw_index,
                    "raw_over": raw_over,
                    "raw_delivery_label": delivery.get("actual_delivery"),
                    "is_legal_delivery": legal,
                    "legal_ball_index": stored_legal_index,
                    "legal_balls_bowled": min(legal_count, self.config.total_balls),
                    "balls_remaining": max(0, self.config.total_balls - legal_count),
                    "five_index": five_index,
                    "ball_within_five": ball_within_five,
                    "end_block_index": end_block_index,
                    "phase": phase,
                    "powerplay_active": powerplay_active,
                    "anomaly_flags": tuple(sorted(anomalies)),
                    "batter": delivery.get("batter"),
                    "bowler": delivery.get("bowler"),
                    "non_striker": delivery.get("non_striker"),
                    "runs": delivery.get("runs") or {},
                    "extras": delivery.get("extras") or {},
                    "wickets": delivery.get("wickets") or [],
                })

        if is_super_five:
            anomalies.add("super_five")
        if legal_count > self.config.total_balls:
            anomalies.add("legal_ball_overflow")

        if anomalies:
            rows = [dict(row, anomaly_flags=tuple(sorted(anomalies))) for row in rows]
        return HundredNormalizationResult(
            rows=rows,
            legal_balls=legal_count,
            anomaly_flags=tuple(sorted(anomalies)),
        )
