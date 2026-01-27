# Data Model: Telegram Prediction Ledger

**Feature**: [plan.md](plan.md) | **Date**: 2026-01-27

## Overview

This feature involves three primary entities representing different types of prediction records posted to Telegram. All entities share common metadata fields (Telegram message ID, timestamps) and are stored in a unified append-only JSON Lines file.

---

## Entity: Prediction Record

**Description**: Represents a pre-match prediction posted before a match begins. Contains model probabilities, market odds, and calculated edge.

### Fields

| Field Name | Type | Constraints | Description |
|------------|------|-------------|-------------|
| `match_id` | string | required, non-empty | Unique identifier for the match (e.g., Cricsheet match ID) |
| `league` | string | required, enum | League name: "BBL", "SA20", "ILT20", "WPL", "SSM", "T20I" |
| `team_a` | string | required, non-empty | First team name |
| `team_b` | string | required, non-empty | Second team name |
| `selection_type` | string | required, enum | "BACK" or "LAY" |
| `selected_team` | string | required, non-empty | Team being backed or laid (must be team_a or team_b) |
| `model_probability` | float | required, 0.0-100.0 | Model's win probability for selected team (percentage) |
| `market_odds` | float | required, >= 1.01 | Decimal odds from market at time of post |
| `model_edge` | float | required | Calculated edge percentage (can be negative) |
| `telegram_message_id` | integer | required | Telegram's message ID (returned from API) |
| `telegram_timestamp` | string | required, ISO8601 | Telegram's authoritative timestamp (UTC) |
| `post_type` | string | required, constant | Always "pre_match" for this entity |
| `posted_at_utc` | string | required, ISO8601 | System timestamp when record was created (UTC) |

### Relationships

- Links to **Match Start Record** via `match_id`
- Links to **Result Record** via `match_id`

### Validation Rules

1. `selected_team` must equal either `team_a` or `team_b`
2. `model_probability` must be in range [0.0, 100.0]
3. `market_odds` must be >= 1.01 (minimum bookmaker odds)
4. `model_edge` = (1 / market_odds - 1 / (model_probability / 100)) * 100
5. All timestamps must be valid ISO8601 format
6. `telegram_message_id` must be positive integer

### Example

```json
{
  "match_id": "1234567",
  "league": "BBL",
  "team_a": "Sydney Sixers",
  "team_b": "Melbourne Stars",
  "selection_type": "BACK",
  "selected_team": "Sydney Sixers",
  "model_probability": 67.5,
  "market_odds": 1.52,
  "model_edge": 5.2,
  "telegram_message_id": 12345,
  "telegram_timestamp": "2026-01-27T10:30:00Z",
  "post_type": "pre_match",
  "posted_at_utc": "2026-01-27T10:30:00.123456Z"
}
```

---

## Entity: Match Start Record

**Description**: Represents match start context (toss information) posted when the match begins. References the original pre-match prediction probability for context.

### Fields

| Field Name | Type | Constraints | Description |
|------------|------|-------------|-------------|
| `match_id` | string | required, non-empty | Links to corresponding Prediction Record |
| `team_a` | string | required, non-empty | First team name |
| `team_b` | string | required, non-empty | Second team name |
| `toss_winner` | string | required, non-empty | Team that won the toss |
| `toss_decision` | string | required, enum | "Bat" or "Bowl" |
| `model_prematch_probability` | float | optional, 0.0-100.0 | Pre-match probability for reference (not used in computation) |
| `telegram_message_id` | integer | required | Telegram's message ID |
| `telegram_timestamp` | string | required, ISO8601 | Telegram's timestamp (UTC) |
| `post_type` | string | required, constant | Always "match_start" for this entity |
| `posted_at_utc` | string | required, ISO8601 | System timestamp (UTC) |

### Relationships

- Links to **Prediction Record** via `match_id` (optional relationship - can be posted without prior prediction)

### Validation Rules

1. `toss_winner` must equal either `team_a` or `team_b`
2. `toss_decision` must be "Bat" or "Bowl"
3. If `model_prematch_probability` is provided, must be in range [0.0, 100.0]
4. All timestamps must be valid ISO8601 format

### State Transitions

- **None**: Match Start Records are immutable after creation (no state transitions)

### Example

```json
{
  "match_id": "1234567",
  "team_a": "Sydney Sixers",
  "team_b": "Melbourne Stars",
  "toss_winner": "Melbourne Stars",
  "toss_decision": "Bowl",
  "model_prematch_probability": 67.5,
  "telegram_message_id": 12346,
  "telegram_timestamp": "2026-01-27T11:00:00Z",
  "post_type": "match_start",
  "posted_at_utc": "2026-01-27T11:00:00.456789Z"
}
```

---

## Entity: Result Record

**Description**: Represents the final match outcome. Documents whether the model prediction was correct by comparing the winner to the original prediction selection.

### Fields

| Field Name | Type | Constraints | Description |
|------------|------|-------------|-------------|
| `match_id` | string | required, non-empty | Links to corresponding Prediction Record |
| `winning_team` | string | required, non-empty | Team that won the match |
| `model_call_correct` | boolean | required | True if prediction was correct, False otherwise |
| `original_selection_type` | string | optional, enum | "BACK" or "LAY" from original prediction (for reference) |
| `original_selected_team` | string | optional, non-empty | Team from original prediction (for reference) |
| `original_probability` | float | optional, 0.0-100.0 | Model probability from original prediction (for reference) |
| `telegram_message_id` | integer | required | Telegram's message ID |
| `telegram_timestamp` | string | required, ISO8601 | Telegram's timestamp (UTC) |
| `post_type` | string | required, constant | Always "result" for this entity |
| `posted_at_utc` | string | required, ISO8601 | System timestamp (UTC) |

### Relationships

- Links to **Prediction Record** via `match_id` (optional relationship - can be posted without prior prediction)

### Validation Rules

1. `model_call_correct` calculation logic:
   - If `original_selection_type` == "BACK": correct if `winning_team` == `original_selected_team`
   - If `original_selection_type` == "LAY": correct if `winning_team` != `original_selected_team`
   - If no original prediction exists, set to `null` (not applicable)
2. All timestamps must be valid ISO8601 format

### Example

```json
{
  "match_id": "1234567",
  "winning_team": "Sydney Sixers",
  "model_call_correct": true,
  "original_selection_type": "BACK",
  "original_selected_team": "Sydney Sixers",
  "original_probability": 67.5,
  "telegram_message_id": 12347,
  "telegram_timestamp": "2026-01-27T14:00:00Z",
  "post_type": "result",
  "posted_at_utc": "2026-01-27T14:00:00.789012Z"
}
```

---

## Storage Schema

### File Format: JSON Lines (.jsonl)

All three entity types are stored in a single append-only file: `data/telegram_predictions.jsonl`

**Structure**: Each line is a complete JSON object (one of the three entity types). The `post_type` field distinguishes entity type.

**Example File Content**:
```jsonl
{"match_id": "1234567", "league": "BBL", "team_a": "Sydney Sixers", "team_b": "Melbourne Stars", "selection_type": "BACK", "selected_team": "Sydney Sixers", "model_probability": 67.5, "market_odds": 1.52, "model_edge": 5.2, "telegram_message_id": 12345, "telegram_timestamp": "2026-01-27T10:30:00Z", "post_type": "pre_match", "posted_at_utc": "2026-01-27T10:30:00.123456Z"}
{"match_id": "1234567", "team_a": "Sydney Sixers", "team_b": "Melbourne Stars", "toss_winner": "Melbourne Stars", "toss_decision": "Bowl", "model_prematch_probability": 67.5, "telegram_message_id": 12346, "telegram_timestamp": "2026-01-27T11:00:00Z", "post_type": "match_start", "posted_at_utc": "2026-01-27T11:00:00.456789Z"}
{"match_id": "1234567", "winning_team": "Sydney Sixers", "model_call_correct": true, "original_selection_type": "BACK", "original_selected_team": "Sydney Sixers", "original_probability": 67.5, "telegram_message_id": 12347, "telegram_timestamp": "2026-01-27T14:00:00Z", "post_type": "result", "posted_at_utc": "2026-01-27T14:00:00.789012Z"}
{"match_id": "7654321", "league": "SA20", "team_a": "Paarl Royals", "team_b": "Joburg Super Kings", "selection_type": "LAY", "selected_team": "Joburg Super Kings", "model_probability": 45.0, "market_odds": 2.10, "model_edge": -2.4, "telegram_message_id": 12348, "telegram_timestamp": "2026-01-28T10:00:00Z", "post_type": "pre_match", "posted_at_utc": "2026-01-28T10:00:00.111111Z"}
```

**Advantages**:
- Append-only: Safe concurrent writes (each line is atomic)
- Human-readable: Can inspect with text editor
- Incremental parsing: Can process one line at a time
- No schema migration: Add new fields without breaking old records

**Query Patterns**:
```python
# Read all records by type
def get_predictions():
    with open('data/telegram_predictions.jsonl', 'r') as f:
        return [json.loads(line) for line in f if json.loads(line)['post_type'] == 'pre_match']

# Get records for specific match
def get_match_records(match_id):
    with open('data/telegram_predictions.jsonl', 'r') as f:
        return [json.loads(line) for line in f if json.loads(line).get('match_id') == match_id]
```

---

## Data Consistency Rules

1. **Atomicity**: Telegram post and local storage write are NOT transactional. If Telegram succeeds but storage write fails, the record exists in Telegram but not locally. This is acceptable (Telegram is source of truth).

2. **Ordering**: Records are appended in chronological order by `posted_at_utc`. Order within the file reflects posting sequence.

3. **Immutability**: Once written, records are NEVER modified or deleted. Corrections are made by posting clarification messages (separate records).

4. **Uniqueness**: No uniqueness constraints. Duplicate `match_id` predictions are allowed (user responsibility to avoid).

5. **Referential Integrity**: `match_id` links are NOT enforced. A Result Record can be posted without a corresponding Prediction Record (soft reference).

---

## Migration Strategy

**Initial State**: No migration needed (new feature).

**Future Changes**:
- New fields can be added without breaking existing records (JSON is flexible)
- If breaking schema changes needed, create new file: `telegram_predictions_v2.jsonl`
- Old records remain readable in old format (append-only history preserved)

---

## Summary

This data model supports three independent record types (pre-match prediction, match start, result) stored in a unified append-only log. The design prioritizes simplicity, immutability, and human readability. Telegram serves as the authoritative timestamped ledger, with local storage providing a queryable backup.
