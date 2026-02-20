# Research: Telegram Prediction Ledger

**Feature**: [plan.md](plan.md) | **Date**: 2026-01-27

## Research Questions

Based on Technical Context unknowns and spec requirements, the following research was conducted:

### 1. Telegram Bot API Integration

**Question**: What is the best library and pattern for posting messages to Telegram channels from Python?

**Decision**: Use `python-telegram-bot` (version 20.x)

**Rationale**:
- Official recommendation from Telegram
- Active maintenance (last release: 2024)
- Async/sync API support (we'll use sync for simplicity)
- Built-in error handling and retry logic
- Type hints and excellent documentation
- Handles rate limiting automatically

**Alternatives Considered**:
- `pyTelegramBotAPI` (telepot): Less maintained, smaller community
- Direct HTTP requests to Telegram API: Reinventing the wheel, no built-in retry/rate-limit handling
- `aiogram`: Async-only, overkill for our manual-posting use case

**Integration Pattern**:
```python
from telegram import Bot
from telegram.error import TelegramError

bot = Bot(token=TELEGRAM_BOT_TOKEN)
try:
    message = bot.send_message(
        chat_id=TELEGRAM_CHANNEL_ID,
        text=formatted_message,
        parse_mode='HTML'  # or 'MarkdownV2' for formatting
    )
    return message.message_id, message.date
except TelegramError as e:
    # Handle API errors (network, rate limit, invalid token, etc.)
    raise
```

**Best Practices**:
- Store bot token in environment variables (never in code)
- Use channel ID format: `@channel_name` or numeric ID (e.g., `-1001234567890`)
- Bot must be admin of the channel with "Post Messages" permission
- Disable link previews: `disable_web_page_preview=True`
- Use HTML parse mode for structured formatting (cleaner than MarkdownV2)

---

### 2. Streamlit Modal Dialogs

**Question**: What's the best approach for modal forms in Streamlit for data entry?

**Decision**: Use Streamlit's `@st.dialog` decorator (Streamlit 1.31+)

**Rationale**:
- Native Streamlit feature (no custom components needed)
- Clean API for modal UI patterns
- Proper form state management
- Works with `st.form` for validation

**Alternatives Considered**:
- `streamlit-modal` custom component: Third-party dependency, less maintained
- Sidebar forms: Not modal, less focused UX
- `st.expander` with forms: Not truly modal, can be accidentally closed

**Implementation Pattern**:
```python
@st.dialog("Post Pre-Match Prediction")
def show_prediction_modal():
    with st.form("prediction_form"):
        match_id = st.text_input("Match ID", placeholder="e.g., 1234567")
        league = st.selectbox("League", ["BBL", "SA20", "ILT20", "WPL", "SSM"])
        team_a = st.text_input("Team A")
        team_b = st.text_input("Team B")
        selection = st.radio("Selection", ["BACK", "LAY"])
        model_prob = st.number_input("Model Probability (%)", 0.0, 100.0)
        odds = st.number_input("Market Odds", 1.01, 1000.0, step=0.01)
        edge = st.number_input("Model Edge (%)", -100.0, 100.0)
        
        submitted = st.form_submit_button("Post to Telegram")
        if submitted:
            # Validation and posting logic
            ...
```

**Best Practices**:
- Use `st.form` within dialog to batch input state
- Validate all fields before posting
- Show spinner during API call: `with st.spinner("Posting...")`
- Display success/error messages: `st.success()` / `st.error()`
- Close modal on success: `st.rerun()` after successful post

---

### 3. Append-Only Storage Format

**Question**: What's the best format for append-only local storage of prediction records?

**Decision**: JSON Lines (.jsonl format)

**Rationale**:
- Append-only by design (newline-delimited JSON records)
- Human-readable for debugging
- Easy to parse incrementally
- Standard format with library support
- No risk of corrupting entire file if write fails mid-operation

**Alternatives Considered**:
- SQLite: Overkill for append-only logs, requires schema migrations
- CSV: Harder to handle nested data (telegram metadata), no native dict support
- Plain JSON array: Requires rewriting entire file on append (not atomic)
- Pickle: Not human-readable, version-sensitive

**Schema Example**:
```json
{"match_id": "1234567", "league": "BBL", "team_a": "Sydney Sixers", "team_b": "Melbourne Stars", "selection_type": "BACK", "selected_team": "Sydney Sixers", "model_probability": 67.5, "market_odds": 1.52, "model_edge": 5.2, "telegram_message_id": 12345, "telegram_timestamp": "2026-01-27T10:30:00Z", "post_type": "pre_match", "posted_at_utc": "2026-01-27T10:30:00.123Z"}
{"match_id": "1234567", "team_a": "Sydney Sixers", "team_b": "Melbourne Stars", "toss_winner": "Melbourne Stars", "toss_decision": "Bowl", "model_prematch_probability": 67.5, "telegram_message_id": 12346, "telegram_timestamp": "2026-01-27T11:00:00Z", "post_type": "match_start", "posted_at_utc": "2026-01-27T11:00:00.456Z"}
```

**Best Practices**:
- Use `with open(..., 'a')` for atomic appends
- Include UTC timestamps (`posted_at_utc`) for audit trail
- Store Telegram's timestamp (`telegram_timestamp`) as authoritative
- Include Telegram message ID for linking back to posts
- No line breaks in JSON (each record is single line)

---

### 4. Message Format Templates

**Question**: Should we use plain text, Markdown, or HTML for Telegram message formatting?

**Decision**: Use HTML parse mode with structured plain text fallback

**Rationale**:
- HTML is more predictable than MarkdownV2 (fewer escaping edge cases)
- Supports bold (`<b>`), code blocks (`<pre>`), and line breaks (`\n`)
- Plain text structure still readable if HTML disabled
- Telegram's HTML is subset (safe from XSS)

**Template Structure**:
```python
PRE_MATCH_TEMPLATE = """
<b>MATCH ID:</b> {match_id}
<b>LEAGUE:</b> {league}

<b>MATCH:</b>
{team_a} vs {team_b}

<b>MODEL PROBABILITY:</b>
{selected_team} win: {model_probability}%

<b>MARKET ODDS (at post time):</b>
{selected_team}: {market_odds}

<b>POSITION:</b>
{selection_type} – {selected_team}

<b>MODEL EDGE:</b>
{model_edge}%

<b>STATUS:</b>
Pre-Match Prediction
"""
```

**Best Practices**:
- Use `str.format()` for safe templating (avoid f-strings with user input)
- Keep templates as module-level constants
- Validate field types before formatting (e.g., `model_probability` must be float)
- Include newlines for readability in Telegram
- Bold labels, plain text values

---

### 5. Configuration Management

**Question**: How to securely manage Telegram bot token and channel ID?

**Decision**: Use `python-decouple` with `.env` file

**Rationale**:
- Simple, widely-used pattern for 12-factor apps
- Separates config from code
- Type casting support (`config('PORT', cast=int)`)
- Default values for optional settings
- Works with environment variables (Docker/cloud deployments)

**Alternatives Considered**:
- `os.environ`: No type casting, no defaults, less ergonomic
- Config files (YAML/JSON): More complex, risk of committing secrets
- Secrets management service (Vault): Overkill for single-user local app

**Setup Pattern**:
```python
# src/bbl_pipeline/telegram/config.py
from decouple import config

TELEGRAM_BOT_TOKEN = config('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHANNEL_ID = config('TELEGRAM_CHANNEL_ID')
TELEGRAM_STORAGE_PATH = config(
    'TELEGRAM_STORAGE_PATH', 
    default='data/telegram_predictions.jsonl'
)
```

**Best Practices**:
- Create `.env.example` (committed) with dummy values
- Add `.env` to `.gitignore` (never commit real tokens)
- Validate token format on startup (starts with bot prefix)
- Document setup in `quickstart.md`

---

### 6. Error Handling Strategy

**Question**: What error handling is needed for Telegram API failures?

**Decision**: Fail-fast with user-friendly error messages; no automatic retries for manual posts

**Rationale**:
- Manual posting means user is present to handle errors
- Automatic retries could lead to duplicate posts
- Better to fail and let user retry manually
- Preserve audit trail: only record successful posts

**Error Categories**:
1. **Network Errors**: Timeout, connection refused → "Network error. Check internet connection."
2. **Auth Errors**: Invalid token → "Invalid bot token. Check .env configuration."
3. **Permission Errors**: Bot not admin → "Bot lacks permission. Make bot admin of channel."
4. **Rate Limiting**: Too many requests → "Rate limited. Wait 60 seconds and retry."
5. **Invalid Input**: Bad channel ID → "Invalid channel ID. Check configuration."

**Implementation Pattern**:
```python
try:
    message = bot.send_message(...)
    # Only write to storage after successful Telegram post
    storage.append(record)
except telegram.error.NetworkError:
    st.error("Network error. Check internet and retry.")
except telegram.error.Unauthorized:
    st.error("Invalid bot token. Check .env configuration.")
except telegram.error.BadRequest as e:
    st.error(f"Bad request: {e.message}")
except Exception as e:
    st.error(f"Unexpected error: {e}")
```

**Best Practices**:
- Catch specific Telegram exceptions before generic `Exception`
- Display error in Streamlit UI (not just console logs)
- Log full error for debugging: `structlog.get_logger().error(...)`
- Never write to storage if Telegram post fails (maintain consistency)

---

## Technology Decisions Summary

| Decision Area | Chosen Technology | Key Reason |
|---------------|-------------------|------------|
| Telegram API | python-telegram-bot 20.x | Official, well-maintained, built-in retries |
| Streamlit Modals | `@st.dialog` decorator | Native Streamlit 1.31+ feature |
| Storage Format | JSON Lines (.jsonl) | Append-only, atomic writes, human-readable |
| Message Format | HTML parse mode | Predictable formatting, fewer escaping issues |
| Configuration | python-decouple + .env | Simple, secure, 12-factor pattern |
| Error Handling | Fail-fast with UI feedback | Manual operation, user present to retry |

---

## Dependencies to Add

Update `pyproject.toml` dependencies:
```toml
dependencies = [
    # ... existing dependencies ...
    "python-telegram-bot>=20.0,<21.0",
    "python-decouple>=3.8",
]
```

---

## Security Considerations

1. **Token Storage**: Never commit `.env` to git (add to `.gitignore`)
2. **Token Validation**: Check token format on app startup (prevent typos)
3. **Input Sanitization**: HTML-escape user input before formatting (prevent injection)
4. **Channel Verification**: Verify channel ID is correct before first post (prevent posting to wrong channel)
5. **Audit Trail**: Log all API calls (success and failure) for security review

---

## Open Questions (Resolved)

All technical unknowns from the spec have been resolved. No remaining clarifications needed for Phase 1 (Design & Contracts).
