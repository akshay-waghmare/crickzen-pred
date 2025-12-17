# Quick Start Guide: Live Match Prediction

Get up and running with live cricket match predictions in 5 minutes!

## 📋 Prerequisites Checklist

- [ ] Python 3.9+ installed
- [ ] Trained BBL model available
- [ ] Feature store files (player_stats.parquet, venue_stats.parquet)
- [ ] Live match URL from ESPN Cricinfo

## 🚀 Quick Setup

### 1. Install Dependencies

```bash
# From project root
pip install playwright pandas numpy scikit-learn structlog joblib

# Install browser for scraping
playwright install chromium
```

### 2. Verify Model Files

Check your model directory has these files:
```
models/champion/
├── champion_model.joblib          ← Trained model
├── champion_metadata.json         ← Contains global_stats
├── player_stats.parquet          ← Player historical data
└── venue_stats.parquet           ← Venue historical data
```

### 3. Run Your First Prediction

```bash
# Replace with actual match URL
python src/run_integrated_prediction.py \
    --match-url "https://www.espncricinfo.com/series/big-bash-league-2024-25/match-123456/live" \
    --model-dir "./models/champion"
```

### 4. Watch the Magic! 🎉

You'll see:
- Real-time win probability updates
- Pressure metrics
- Match situation analysis
- Probability trends

Press `Ctrl+C` to stop, and your predictions will be automatically exported to CSV.

## 📊 Sample Output

```
═══════════════════════════════════════════════════════════════════════════
                   🏏 LIVE CRICKET MATCH PREDICTION                        
═══════════════════════════════════════════════════════════════════════════

WIN PROBABILITY

Sydney Sixers: 67.5% 🔥🔥
[████████████████████████████████████████░░░░░░░░░░░░░░░░░░░░░░]
                           FAVORITE                                        

MATCH SITUATION

Target                : 32 runs from 27 balls
Required Run Rate     : 7.11
Current Run Rate      : 9.35
Status                : ✅ On track!
```

## 🎯 Common Use Cases

### During a Live Match
```bash
# Standard usage - updates every 2 seconds
python src/run_integrated_prediction.py \
    --match-url "https://..." \
    --model-dir "./models/champion"
```

### Faster Updates
```bash
# Check every 1 second
python src/run_integrated_prediction.py \
    --match-url "https://..." \
    --model-dir "./models/champion" \
    --poll-interval 1.0
```

### Save with Custom Name
```bash
# Export to specific file
python src/run_integrated_prediction.py \
    --match-url "https://..." \
    --model-dir "./models/champion" \
    --export "./results/match_predictions.csv"
```

## 🔍 Understanding the Display

### Win Probability Bar
```
[████████████████████░░░░░░░░]  60%
 ^                   ^
 Filled (win)       Empty (loss)
```

### Pressure Index
```
[▓▓▓▓▓▓▓▓░░░░░░░░░░]  0.40
 ^                ^
 High              Low
```

### Probability Trend Chart
```
 70% │ █ █ █ █ 
 60% │ █ █ █ █ █
 50% │ █ █ █ █ █ █
     └────────────
      Recent balls →
```

Shows how win probability has changed over recent balls.

## 💡 Tips & Tricks

### 1. Finding Match URLs

Go to ESPN Cricinfo → Click on a live match → Copy URL
- Must be a live match page
- URL should contain `/live-cricket-score`

Example:
```
https://www.espncricinfo.com/series/big-bash-league-2024-25/
  sydney-sixers-vs-perth-scorchers-1st-match-123456/live-cricket-score
```

### 2. Multiple Matches

Open multiple terminals to monitor multiple matches:

```bash
# Terminal 1
python src/run_integrated_prediction.py --match-url "match1" --model-dir "./models/champion"

# Terminal 2
python src/run_integrated_prediction.py --match-url "match2" --model-dir "./models/champion"
```

### 3. Headless Mode (No Browser Window)

Modify line in `run_integrated_prediction.py`:
```python
browser = p.chromium.launch(headless=True)  # Change False to True
```

### 4. Logging for Debugging

Set environment variable:
```bash
export STRUCTLOG_LEVEL=INFO
python src/run_integrated_prediction.py ...
```

## 🐛 Troubleshooting

### "Model not found" error
✅ **Solution**: Check `--model-dir` path is correct and contains required files

### "Playwright not installed"
✅ **Solution**: 
```bash
pip install playwright
playwright install chromium
```

### "Feature mismatch" warnings
✅ **Solution**: This is usually OK - the system adds missing features with defaults

### Scraper hangs on "Waiting for balls..."
✅ **Solution**: 
- Verify match is actually live
- Check internet connection
- Try refreshing the match URL

### Win probability seems off
✅ **Solution**: 
- Ensure feature store has recent data
- Check if player/team names match between scraper and feature store
- Verify model was trained on similar matches

## 📈 Analyzing Results

### View Saved Predictions

```bash
# Predictions are auto-saved to CSV
cat live_predictions_20251210_184532.csv
```

### Plot in Python

```python
import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_csv('live_predictions_20251210_184532.csv')

# Plot win probability over time
plt.figure(figsize=(12, 6))
plt.plot(df.index, df['win_probability'] * 100)
plt.xlabel('Ball Number')
plt.ylabel('Win Probability (%)')
plt.title('Win Probability Throughout Match')
plt.grid(True)
plt.show()
```

## 🎓 Next Steps

1. **Customize Display**: Edit `src/bbl_pipeline/inference/display.py`
2. **Add Features**: Extend `RealTimeFeatureMapper` with new features
3. **Build Dashboard**: Use prediction data to create web dashboard
4. **Mobile App**: Integrate with mobile notifications

## 📚 Full Documentation

See [LIVE_PREDICTION_README.md](./LIVE_PREDICTION_README.md) for complete documentation.

## 🆘 Getting Help

- Check the troubleshooting section above
- Review error messages carefully
- Check model and feature store files exist
- Verify match URL is correct and match is live

---

**Ready to predict?** 🏏

```bash
python src/run_integrated_prediction.py \
    --match-url "YOUR_MATCH_URL" \
    --model-dir "./models/champion"
```

Happy predicting! 🎉

## Running Predictor Locally (Minimal)

This project supports running the live predictor locally for development
and testing without deploying a full service.

### High-level flow
1. The CLI (`cli.py`) parses runtime arguments.
2. A live predictor runner is initialized with match and model configuration.
3. The predictor loads the trained model, calibrator, and metadata from `model_dir`.
4. Live match state is fetched from an API or read from JSON.
5. Features are constructed and passed to the inference pipeline.
6. Calibrated win probabilities are produced as output.

### Notes
- The required model artifacts must already exist under `model_dir`.
- If artifacts are missing or incompatible, defensive checks may log warnings
  or fall back safely.
