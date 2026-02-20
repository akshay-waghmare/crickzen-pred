# CREX Market Odds Integration

This document describes the market odds integration from CREX live match pages.

## Overview

The live predictor now extracts and displays market betting odds from the CREX API, allowing comparison between model predictions and market sentiment.

## How It Works

### 1. API Data Extraction

CREX's sV3 API returns odds data in two fields:

| Field | Description | Example |
|-------|-------------|---------|
| `F` | Favorite team code | `4O` (Sydney Sixers) |
| `R` | Odds format: `back+diff` | `39+1` (back 39, lay 40) |

### 2. Team Code Resolution

CREX uses internal team codes (e.g., `4O`, `4J`) that vary by match. These are resolved to team names using localStorage:

```python
# localStorage contains mappings like:
# t_4O_name = "Sydney Sixers"
# t_4J_name = "Brisbane Heat"

fav_team_name = local_storage.get(f"t_{team_code}_name", team_code)
```

The predictor extracts localStorage after page load:
```python
self.local_storage = await self.page.evaluate(
    "() => Object.fromEntries(Object.entries(localStorage).map(([k, v]) => [k, v]))"
)
```

### 3. Probability Calculation

Implied probability is calculated from back odds:

```
Implied Probability = 100 / (100 + back_odds)

Example: Back odds = 39
         Probability = 100 / (100 + 39) = 71.9%
```

## Output JSON

The predictor outputs market data in the live state JSON:

```json
{
  "market_fav_team": "Sydney Sixers",
  "market_back_odds": "39",
  "market_lay_odds": "40", 
  "market_fav_prob": 0.7194
}
```

## Streamlit Display

The Streamlit app shows:

1. **Favorite Team Box**: Team name, implied probability, back/lay odds
2. **Underdog Team Box**: Team name, calculated probability
3. **Model vs Market Edge**: Highlighted when difference > 3%

### Edge Detection

```python
diff = model_prob - market_bat_prob
if abs(diff) > 0.03:  # 3% threshold
    # Highlight potential value opportunity
```

## Code Locations

| Component | File | Function/Section |
|-----------|------|------------------|
| Odds extraction | `crex_live_predictor.py` | `_process_api_data()` |
| localStorage extraction | `crex_live_predictor.py` | `start()` |
| Streamlit display | `live_streamlit_app.py` | After gauges section |

## Notes

- Market odds are only available during live matches
- The `F` (favorite) field may change as the match progresses
- If localStorage is unavailable, the raw team code is displayed
- Odds format `back+diff` means lay = back + diff
