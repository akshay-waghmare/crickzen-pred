# Quickstart Guide: Telegram Prediction Ledger

**Feature**: [plan.md](plan.md) | **Date**: 2026-01-27

## Overview

This guide walks you through setting up and using the Telegram Prediction Ledger to post verifiable, immutable prediction records to a Telegram channel.

---

## Prerequisites

- Python 3.10+ installed
- `bbl_pipeline` package installed (this project)
- Telegram account (to create bot and channel)
- Internet connection

---

## Setup (One-Time)

### 1. Create Telegram Bot

1. Open Telegram and search for [@BotFather](https://t.me/botfather)
2. Send `/newbot` command
3. Follow prompts to choose bot name and username
4. Copy the bot token (format: `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`)
5. **Important**: Keep this token secret!

### 2. Create Telegram Channel

1. In Telegram, create a new channel (not group):
   - Tap menu → "New Channel"
   - Choose channel name (e.g., "My Cricket Predictions")
   - Make it public or private (your choice)
2. Add your bot as an administrator:
   - Go to channel settings → Administrators
   - Click "Add Administrator"
   - Search for your bot username
   - Grant "Post Messages" permission
3. Get your channel ID:
   - **Public channel**: Use `@channel_username` (e.g., `@my_predictions`)
   - **Private channel**: Forward a message from the channel to [@userinfobot](https://t.me/userinfobot) to get numeric ID (e.g., `-1001234567890`)

### 3. Configure Environment

1. Navigate to project root:
   ```bash
   cd machine_learning_bbl
   ```

2. Create `.env` file (copy from example):
   ```bash
   cp config/.env.example .env
   ```

3. Edit `.env` file with your credentials:
   ```bash
   # .env
   TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
   TELEGRAM_CHANNEL_ID=@my_predictions
   # or for private channel:
   # TELEGRAM_CHANNEL_ID=-1001234567890
   
   # Optional: Custom storage path
   TELEGRAM_STORAGE_PATH=data/telegram_predictions.jsonl
   ```

4. **Important**: Verify `.env` is in `.gitignore` (it should be by default)

### 4. Install Dependencies

```bash
# If using pip
pip install python-telegram-bot python-decouple

# If using poetry
poetry add python-telegram-bot python-decouple

# Or update from pyproject.toml
pip install -e .
```

### 5. Verify Setup

Run the verification script:
```bash
python -c "from bbl_pipeline.telegram.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID; print('✓ Config loaded successfully')"
```

If no errors, you're ready!

---

## Usage

### Starting the App

```bash
streamlit run src/bbl_pipeline/app/telegram_ledger_app.py
```

The Streamlit interface will open in your browser.

---

### Posting a Pre-Match Prediction

**When to use**: Before the match starts, after running your model analysis.

1. Click **"Post Pre-Match Prediction"** button
2. Fill in the modal form:
   - **Match ID**: Enter match identifier (e.g., from Cricsheet or your tracking system)
   - **League**: Select league from dropdown (BBL, SA20, ILT20, etc.)
   - **Team A**: First team name
   - **Team B**: Second team name
   - **Selection**: Choose "BACK" (betting on) or "LAY" (betting against)
   - **Model Probability (%)**: Your model's win probability (0-100)
   - **Market Odds**: Current decimal odds from bookmaker (e.g., 1.52)
   - **Model Edge (%)**: Calculated edge (positive = advantage, negative = disadvantage)
3. Review your entries
4. Click **"Post to Telegram"**
5. Wait for confirmation message
6. Check your Telegram channel to verify the post

**Example**:
```
Match ID: 1234567
League: BBL
Team A: Sydney Sixers
Team B: Melbourne Stars
Selection: BACK
Model Probability: 67.5%
Market Odds: 1.52
Model Edge: 5.2%
```

**Result in Telegram**:
```
MATCH ID: 1234567
LEAGUE: BBL

MATCH:
Sydney Sixers vs Melbourne Stars

MODEL PROBABILITY:
Sydney Sixers win: 67.5%

MARKET ODDS (at post time):
Sydney Sixers: 1.52

POSITION:
BACK – Sydney Sixers

MODEL EDGE:
5.2%

STATUS:
Pre-Match Prediction
```

---

### Posting Match Start Info

**When to use**: When the match begins and toss is completed.

1. Click **"Post Match Start Info"** button
2. Fill in the modal:
   - **Match ID**: Same ID as pre-match prediction
   - **Team A**: First team name
   - **Team B**: Second team name
   - **Toss Winner**: Team that won the toss
   - **Toss Decision**: Select "Bat" or "Bowl"
   - **Model Pre-Match Probability**: (Optional) Reference to original prediction
3. Click **"Post to Telegram"**

**Note**: This posts a **new, separate message**. It does NOT edit the pre-match prediction.

---

### Posting Match Result

**When to use**: After the match concludes.

1. Click **"Post Match Result"** button
2. Fill in the modal:
   - **Match ID**: Same ID as pre-match prediction
   - **Winning Team**: Team that won the match
3. System automatically calculates if prediction was correct
4. Click **"Post to Telegram"**

The system will:
- Look up your original prediction (if exists)
- Determine if your BACK/LAY call was correct
- Post the result with correctness indicator

---

## Data Storage

All successfully posted predictions are stored in:
```
data/telegram_predictions.jsonl
```

This is an append-only log file. Each line is a JSON record.

**To view your prediction history**:
```bash
cat data/telegram_predictions.jsonl | jq .
```

**To filter by match ID**:
```bash
cat data/telegram_predictions.jsonl | jq 'select(.match_id == "1234567")'
```

---

## Error Handling

### "Network error. Check internet connection."
- **Cause**: No internet or Telegram API unreachable
- **Fix**: Check internet connection and retry

### "Invalid bot token. Check .env configuration."
- **Cause**: Bot token is incorrect or missing
- **Fix**: Verify `TELEGRAM_BOT_TOKEN` in `.env` file (should start with numeric ID followed by colon and alphanumeric string)

### "Bot lacks permission. Make bot admin of channel."
- **Cause**: Bot is not an administrator of the channel
- **Fix**: Add bot as admin in Telegram channel settings with "Post Messages" permission

### "Rate limited. Wait 60 seconds and retry."
- **Cause**: Too many Telegram API requests
- **Fix**: Wait and retry (Telegram has rate limits to prevent spam)

### "Invalid channel ID. Check configuration."
- **Cause**: `TELEGRAM_CHANNEL_ID` is incorrect
- **Fix**: 
  - Public channel: Use `@channel_username` format
  - Private channel: Use numeric ID format `-1001234567890`

---

## Best Practices

### Before Posting
- ✅ Double-check all fields (predictions are immutable!)
- ✅ Verify odds are current (from your bookmaker at that moment)
- ✅ Calculate edge correctly: `(1 / odds - 1 / (prob / 100)) * 100`
- ✅ Use consistent team names (spelling matters for linking records)

### During Operation
- ✅ Post pre-match predictions BEFORE match starts
- ✅ Post match start info when toss happens (not before)
- ✅ Post results after match fully concludes
- ✅ Keep your `.env` file secure (never share bot token)

### After Posting
- ✅ Check Telegram channel to confirm message posted correctly
- ✅ Note the Telegram timestamp (authoritative time record)
- ❌ Do NOT attempt to edit or delete messages (defeats immutability)
- ❌ Do NOT post corrections (if you made an error, it's permanent - that's the point!)

---

## Troubleshooting

### Modal doesn't appear when I click button
- **Issue**: Old Streamlit version
- **Fix**: Update Streamlit: `pip install streamlit>=1.31`

### Storage file not created
- **Issue**: Permission error or invalid path
- **Fix**: Check `TELEGRAM_STORAGE_PATH` in `.env` and ensure directory exists:
  ```bash
  mkdir -p data
  ```

### Predictions posted to wrong channel
- **Issue**: Incorrect `TELEGRAM_CHANNEL_ID`
- **Fix**: Verify channel ID in `.env` (forward a channel message to @userinfobot to confirm)

### Bot not found when adding to channel
- **Issue**: Bot username typo
- **Fix**: Go back to @BotFather and send `/mybots` to see exact bot username

---

## Security Notes

⚠️ **Critical**: Your `.env` file contains sensitive credentials.

- ✅ **DO**: Store `.env` locally only (never commit to git)
- ✅ **DO**: Add `.env` to `.gitignore`
- ✅ **DO**: Use environment variables in production (not `.env` files)
- ❌ **DON'T**: Share bot token with others
- ❌ **DON'T**: Post bot token in public channels or forums
- ❌ **DON'T**: Commit `.env` to version control

If you accidentally expose your bot token:
1. Go to @BotFather
2. Send `/mybots`
3. Select your bot
4. Click "API Token" → "Revoke"
5. Generate new token
6. Update `.env` with new token

---

## FAQ

**Q: Can I edit a prediction after posting?**  
A: No. This is intentional - immutability is the core feature. If you made a mistake, the record stands as-is.

**Q: Can I delete a prediction?**  
A: No. Append-only means records are permanent. You cannot delete from Telegram or local storage.

**Q: What if I posted to the wrong channel?**  
A: The prediction is now in the wrong channel permanently. Create a new channel and update `.env` for future posts.

**Q: Can I post the same prediction twice?**  
A: Yes, the system allows duplicates. This is your responsibility to manage (use unique Match IDs).

**Q: Do I need to post all three types (pre-match, start, result)?**  
A: No. They're independent. You can post only pre-match predictions if you want.

**Q: Can I use this for multiple leagues?**  
A: Yes, all predictions go to the same channel. Use the "League" field to distinguish them.

**Q: How do I link predictions, starts, and results?**  
A: Use the same `Match ID` for all three. The system links them via this ID.

**Q: Can I export predictions to CSV?**  
A: Not built-in, but you can convert the `.jsonl` file:
  ```bash
  cat data/telegram_predictions.jsonl | jq -r '. | @csv' > predictions.csv
  ```

---

## Next Steps

- Post your first test prediction to verify setup
- Check prediction appears in Telegram channel
- Review stored data in `data/telegram_predictions.jsonl`
- Integrate with your match analysis workflow

**Happy predicting! 🏏**
