# BBL Live Match Prediction System

Real-time cricket match win probability prediction using the BBL pipeline model integrated with live match scraping.

## Features

- ✅ **Real-time Predictions**: Get live win probability updates for every ball
- 📊 **Rich Visual Display**: Console UI with probability trends, pressure metrics, and match situation
- 🎯 **DLS Integration**: Resource-based features for accurate predictions
- 📈 **Historical Context**: Player and venue statistics from feature store
- 💾 **Export Results**: Save prediction history to CSV for analysis
- 🔄 **Continuous Updates**: Automatic polling for new balls

## System Architecture

```
┌─────────────────┐
│  ESPN Cricinfo  │
│   Live Match    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐      ┌──────────────────┐
│  Real-time      │─────▶│  Scraper Bridge  │
│  Scraper        │      │  (Adapter Layer) │
│  (ml_predictions)│      └────────┬─────────┘
└─────────────────┘               │
                                  ▼
                     ┌────────────────────────┐
                     │ RealTimeFeatureMapper  │
                     │  - Field name mapping   │
                     │  - Feature calculation  │
                     │  - FeatureStore lookup  │
                     └────────┬───────────────┘
                              │
                              ▼
                   ┌──────────────────────┐
                   │  BBL Model Pipeline  │
                   │  - Resource features │
                   │  - Rolling stats     │
                   │  - Prediction        │
                   └──────────┬───────────┘
                              │
                              ▼
                   ┌──────────────────────┐
                   │  Live Match Display  │
                   │  - Probability chart │
                   │  - Match situation   │
                   │  - Pressure metrics  │
                   └──────────────────────┘
```

## Installation

### Prerequisites

```bash
# Install required packages
pip install playwright pandas numpy scikit-learn structlog joblib

# Install Playwright browsers
playwright install chromium
```

### Model Requirements

You need a trained BBL model with the following artifacts:
- `champion_model.joblib` - Trained model
- `champion_metadata.json` - Model metadata with global stats
- `player_stats.parquet` - Player historical statistics (FeatureStore)
- `venue_stats.parquet` - Venue historical statistics (FeatureStore)

## Usage

### Method 1: Integrated Runner (Recommended)

Uses the existing `ml_predictions/real_time_scraper.py` with prediction injection:

```bash
python src/run_integrated_prediction.py \
    --match-url "https://www.espncricinfo.com/series/big-bash-league-2024-25/..." \
    --model-dir "./models/champion"
```

### Method 2: Standalone Runner

Independent implementation with scraper bridge:

```bash
python src/run_live_prediction.py \
    --match-url "https://www.espncricinfo.com/series/big-bash-league-2024-25/..." \
    --model-dir "./models/champion" \
    --poll-interval 2.0
```

### Options

- `--match-url`: ESPN Cricinfo live match URL (required)
- `--model-dir`: Path to model directory (required)
- `--poll-interval`: Seconds between checks for new balls (default: 2.0)
- `--no-clear`: Don't clear screen between updates
- `--export`: Custom CSV export path

## Display Features

### Main Display

```
═══════════════════════════════════════════════════════════════════════════
                   🏏 LIVE CRICKET MATCH PREDICTION                        
═══════════════════════════════════════════════════════════════════════════

Innings        : 2
Batting        : Sydney Sixers
Bowling        : Perth Scorchers
Current Ball   : Over 15.3

────────────────────────────────────────────────────────────────────────────

                          WIN PROBABILITY                                   

Sydney Sixers: 67.5% 🔥🔥
[████████████████████████████████████████░░░░░░░░░░░░░░░░░░░░░░]
                           FAVORITE                                        

────────────────────────────────────────────────────────────────────────────

                         MATCH SITUATION                                    

Score                 : 145/4
Target                : 32 runs from 27 balls (4.5 overs)
Required Run Rate     : 7.11
Current Run Rate      : 9.35
Status                : ✅ On track!

Pressure Index        : [▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░] 0.35
Pressure Level        : 🟡 MODERATE PRESSURE

────────────────────────────────────────────────────────────────────────────

                   PROBABILITY TREND (Last 10 balls)                       

 70.0% │ █ █   █ █ █   █ █ █ █ 
 65.0% │ █ █ █ █ █ █ █ █ █ █ █ 
 60.0% │ █ █ █ █ █ █ █ █ █ █ █ 
       └──────────────────────
        1 2 3 4 5 6 1 2 3 4 5

────────────────────────────────────────────────────────────────────────────
                                                                             
Last Updated          : 2025-12-10 18:45:32                                 
                       Press Ctrl+C to stop                                  
═══════════════════════════════════════════════════════════════════════════
```

## Feature Mapping

The system automatically maps scraped data to model features:

| Scraped Field | Model Feature | Source |
|--------------|---------------|--------|
| `innings_num` | `innings` | Direct |
| `over_number` | `over` | Direct |
| `ball_number` | `ball` | Direct |
| `total_score` | `current_score` | Direct |
| `total_wickets` | `wickets_lost` | Direct |
| `batsman1_name` | Player lookup | FeatureStore |
| `venue` | Venue lookup | FeatureStore |
| - | `resource_pct` | ResourceCalculator |
| - | `resource_win_prob` | ResourceCalculator |
| - | `pressure_index` | ResourceCalculator |

## Output Files

### Prediction History CSV

Automatically exported on exit:

```
timestamp,ball,innings,batting_team,score,win_probability,pressure_index,...
2025-12-10T18:45:32,15.3,2,Sydney Sixers,145/4,0.675,0.35,7.11,9.35,...
```

### Fields

- `timestamp`: ISO format timestamp
- `ball`: Over.ball (e.g., "15.3")
- `innings`: 1 or 2
- `batting_team`: Team name
- `score`: Current score (runs/wickets)
- `win_probability`: Model's win probability (0-1)
- `resource_win_prob`: DLS-based baseline probability
- `pressure_index`: Pressure metric (0-1)
- `current_run_rate`: Current run rate
- `required_run_rate`: Required run rate (innings 2 only)
- `runs_required`: Runs needed to win (innings 2 only)
- `balls_remaining`: Balls left in innings
- `wickets_remaining`: Wickets in hand
- `expected_final_score`: Projected final score

## Troubleshooting

### Playwright not found
```bash
pip install playwright
playwright install chromium
```

### Model not found
Ensure your model directory contains:
- `champion_model.joblib`
- `champion_metadata.json`
- `player_stats.parquet`
- `venue_stats.parquet`

### Feature mismatch errors
The mapper will automatically add missing features with defaults. Check logs for warnings.

### Scraper connection issues
- Verify the match URL is correct
- Check network connection
- ESPN Cricinfo may rate-limit requests

## Programmatic Usage

### Custom Integration

```python
from bbl_pipeline.inference import LiveMatchPredictor, RealTimeFeatureMapper

# Initialize predictor
predictor = LiveMatchPredictor(model_dir="./models/champion")

# Process a ball
scraped_data = {
    'innings_num': 2,
    'over_number': 15,
    'ball_number': 3,
    'total_score': 145,
    'total_wickets': 4,
    'batting_team': 'Sydney Sixers',
    'batsman1_name': 'Player Name',
    # ... other fields
}

result = predictor.predict_ball(scraped_data)
print(f"Win Probability: {result['win_probability']:.1%}")
```

### Custom Display Callback

```python
def my_display(result):
    """Custom display function."""
    print(f"Ball {result['ball']}: {result['win_probability']:.1%}")

predictor = LiveMatchPredictor(
    model_dir="./models/champion",
    callback=my_display  # Your custom function
)
```

## Performance

- **Prediction Latency**: < 100ms per ball
- **Memory Usage**: ~500MB (model + feature store)
- **Scraping Interval**: 2 seconds default (configurable)

## Architecture Decisions

### Why Feature Mapper?
- Decouples scraper format from model format
- Allows scraper updates without model retraining
- Centralizes feature calculation logic

### Why Resource Calculator?
- Provides cricket domain knowledge (DLS-inspired)
- Helps with rare/extreme game states
- Improves calibration

### Why Separate Display?
- Modular design for different UIs (console, web, mobile)
- Easy to customize or replace
- Can run headless for logging only

## Future Enhancements

- [ ] Web-based dashboard
- [ ] Mobile app integration
- [ ] Multiple match monitoring
- [ ] Prediction explanations (SHAP values)
- [ ] Player contribution metrics
- [ ] Betting odds comparison

## License

[Your License Here]

## Credits

Built on top of:
- BBL Pipeline (src/bbl_pipeline)
- Real-time Scraper (ml_predictions/real_time_scraper.py)
- Resource Feature Calculator (DLS-inspired)
