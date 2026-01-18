# BBL Data Pipeline & Live Match Predictor

A comprehensive system for Big Bash League (BBL) cricket data processing and real-time match win probability prediction.

## 🏆 Latest Model: BBL v12 (Jan 2026)

Our latest champion model achieves state-of-the-art performance:
- **Brier Score:** 0.1760 (per-over calibrated), 0.1833 (raw model)
- **ECE (Calibration Error):** 0.0000 (perfect calibration)
- **Method:** XGBLogRegEnsemble + Per-Over Brier-Optimized Isotonic Calibration
- **Training Data:** 141,435 ball-by-ball samples
- **Calibrators:** 38 per-over + 6 phase-specific isotonic calibrators
- [Read the full documentation](docs/BBL_V12_MODEL.md) - Includes detailed OOF calibration analysis.

## Features

### Data Pipeline
- **Ingestion**: Parse Cricsheet JSON files and convert to Parquet.
- **Processing**: Flatten ball-by-ball data, separate Super Overs.
- **Entity Resolution**: Normalize player, team, and venue names using fuzzy matching and a canonical registry.
- **Validation**: Enforce strict schemas using Pandera.
- **CLI**: Unified command-line interface for all operations.

### Live Match Prediction 🎯
- **Real-time Win Probability**: Get live predictions for every ball
- **Visual Display**: Rich console UI with probability charts and trends
- **DLS Integration**: Resource-based features for accurate predictions
- **Match Analysis**: Pressure metrics, run rate tracking, and situation assessment
- **Auto Export**: Save all predictions to CSV for post-match analysis

### Monte Carlo Simulation 🎲 **NEW**
- **Uncertainty Quantification**: 1-ball and 6-ball forward simulations
- **Confidence Intervals**: 90% CI (p5-p95) for win probability
- **Betting Decision Support**: Phase-aware Kelly criterion with risk guardrails
- **Temperature Calibration**: League-specific probability adjustments (BBL, SA20, ILT20, WPL)
- **Performance**: <200ms for 1-ball, <500ms for 6-ball simulations
- [Full Documentation](docs/MONTE_CARLO_SIMULATION.md)

## Installation

### Basic Installation

```bash
pip install -e .
```

### For Live Match Predictions

```bash
# Install additional dependencies
pip install playwright pandas numpy scikit-learn structlog joblib

# Install browser for web scraping
playwright install chromium
```

## Usage

### Data Pipeline Operations

#### Ingest Data

```bash
bbl-pipeline ingest --input-dir /path/to/json --output-dir /path/to/output
```

#### Resolve Entities

```bash
bbl-pipeline resolve --input-dir /path/to/json
```

#### Validate Data

```bash
bbl-pipeline validate --data-dir /path/to/output
```

### Live Match Prediction 🏏

#### Quick Start - Run Live Prediction

**Step 1:** Get a live match URL from ESPN Cricinfo
```
Example: https://www.espncricinfo.com/series/big-bash-league-2024-25/perth-scorchers-vs-sydney-sixers-1st-match-123456/live-cricket-score
```

**Step 2:** Run the predictor
```bash
python src/run_integrated_prediction.py \
    --match-url "YOUR_LIVE_MATCH_URL" \
    --model-dir "./models/champion"
```

**Step 3:** Watch real-time predictions!
```
═══════════════════════════════════════════════════════════════
           🏏 LIVE CRICKET MATCH PREDICTION                
═══════════════════════════════════════════════════════════════

WIN PROBABILITY
Sydney Sixers: 67.5% 🔥🔥
[████████████████████████████████████░░░░░░░░░░░░░░░░]

MATCH SITUATION
Score          : 145/4
Target         : 32 runs from 27 balls
Required RR    : 7.11  |  Current RR: 9.35
Status         : ✅ On track!

Pressure Index : [▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░] 0.35
```

**Step 4:** Stop with `Ctrl+C` - predictions auto-saved to CSV!

#### Prerequisites for Live Prediction

1. **Trained Model**: You need a trained model directory containing:
   - `champion_model.joblib` (trained model)
   - `champion_metadata.json` (model metadata)
   - `player_stats.parquet` (player statistics)
   - `venue_stats.parquet` (venue statistics)

2. **Live Match**: An active match on ESPN Cricinfo

3. **Internet Connection**: For scraping live data

#### Advanced Options

```bash
# Custom polling interval (check every 3 seconds)
python src/run_integrated_prediction.py \
    --match-url "URL" \
    --model-dir "./models/champion" \
    --poll-interval 3.0

# Custom export filename
python src/run_integrated_prediction.py \
    --match-url "URL" \
    --model-dir "./models/champion" \
    --export "./predictions/match_20241210.csv"
```

#### Understanding the Display

- **Win Probability Bar**: Visual representation of win chance (0-100%)
- **Probability Trend**: Chart showing how probability changed over recent balls
- **Pressure Index**: Indicates match tension (0=low, 1=extreme)
- **Match Situation**: Current score, target, run rates, and status
- **Recent Balls**: History of last 5 balls with probability changes

#### Output Files

Predictions are automatically exported to CSV with columns:
- `timestamp`, `ball`, `innings`, `batting_team`, `score`
- `win_probability`, `resource_win_prob`, `pressure_index`
- `current_run_rate`, `required_run_rate`, `runs_required`
- `balls_remaining`, `wickets_remaining`, `expected_final_score`

## Documentation

- **[Quick Start Guide](docs/QUICK_START_LIVE_PREDICTION.md)**: Get started in 5 minutes
- **[Full Documentation](docs/LIVE_PREDICTION_README.md)**: Complete system architecture and features
- **[Training Guide](docs/TRAINING_OPTIMIZATION.md)**: Model training and optimization

## Configuration

Configuration is loaded from `config/config.yaml` or passed via `--config`.

## Project Structure

```
.
├── src/
│   ├── bbl_pipeline/           # Data pipeline
│   │   ├── data/              # Data processing
│   │   ├── features/          # Feature engineering
│   │   ├── training/          # Model training
│   │   └── inference/         # Live prediction ⭐
│   ├── run_integrated_prediction.py  # Main live predictor ⭐
│   └── run_live_prediction.py       # Alternative runner
├── ml_predictions/            # Legacy scraper
├── models/                    # Trained models
├── docs/                      # Documentation
└── config/                    # Configuration files
```

## Common Workflows

### 1. Train a New Model
```bash
# Process data
bbl-pipeline ingest --input-dir ./data/raw --output-dir ./data/processed

# Train model
python src/bbl_pipeline/training/trainer.py

# Model saved to models/champion/
```

### 2. Run Live Predictions
```bash
# Start live prediction
python src/run_integrated_prediction.py \
    --match-url "LIVE_MATCH_URL" \
    --model-dir "./models/champion"

# Watch real-time updates
# Press Ctrl+C to stop and export results
```

### 3. Analyze Predictions
```python
import pandas as pd
import matplotlib.pyplot as plt

# Load saved predictions
df = pd.read_csv('live_predictions_20241210_184530.csv')

# Plot win probability over time
plt.plot(df.index, df['win_probability'] * 100)
plt.xlabel('Ball Number')
plt.ylabel('Win Probability (%)')
plt.title('Win Probability Throughout Match')
plt.show()
```

## Troubleshooting

### Live Prediction Issues

**"Playwright not installed"**
```bash
pip install playwright
playwright install chromium
```

**"Model not found"**
- Verify `--model-dir` path is correct
- Ensure directory contains `champion_model.joblib`

**"Feature mismatch warnings"**
- Usually safe to ignore - system adds missing features with defaults

**Scraper hangs**
- Verify match is actually live
- Check internet connection
- Confirm match URL is correct

### Data Pipeline Issues

See individual component documentation for troubleshooting.

## Development

Run tests:

```bash
pytest
```

## Examples

### Live Match Prediction

```bash
# BBL Match
python src/run_integrated_prediction.py \
    --match-url "https://www.espncricinfo.com/series/big-bash-league-2024-25/..." \
    --model-dir "./models/champion"

# With faster updates
python src/run_integrated_prediction.py \
    --match-url "https://..." \
    --model-dir "./models/champion" \
    --poll-interval 1.5
```

## License

[Your License]

## Credits

- BBL Data Pipeline: Built for comprehensive cricket analytics
- Live Prediction System: Integrates real-time scraping with ML predictions
- DLS Integration: Resource-based features inspired by Duckworth-Lewis-Stern method
