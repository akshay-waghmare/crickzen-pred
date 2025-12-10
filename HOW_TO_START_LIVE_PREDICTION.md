# 🚀 How to Start Live Match Visualization

## ⚡ Super Quick Start (3 Steps)

### Step 1: Find a Live Match URL 🔍

Go to **ESPN Cricinfo** → Find a **LIVE** match → Copy the URL

Example URL:
```
https://www.espncricinfo.com/series/big-bash-league-2024-25/perth-scorchers-vs-sydney-sixers-1st-match-1419756/live-cricket-score
```

**Important:** Must be a **LIVE** match, not a scheduled or completed match!

---

### Step 2: Open Terminal/Command Prompt 💻

Navigate to your project directory:
```bash
cd C:\Users\ADMINS\Documents\projects\machine_learning
```

---

### Step 3: Run the Command 🎯

**Copy this command and replace `YOUR_URL_HERE` with your match URL:**

```bash
python src/run_integrated_prediction.py --match-url "YOUR_URL_HERE" --model-dir "./models/champion"
```

**Full Example:**
```bash
python src/run_integrated_prediction.py --match-url "https://www.espncricinfo.com/series/big-bash-league-2024-25/perth-scorchers-vs-sydney-sixers-1st-match-1419756/live-cricket-score" --model-dir "./models/champion"
```

---

## 📺 What You'll See

### Initial Loading
```
═══════════════════════════════════════════════════════════
           🏏 BBL LIVE MATCH PREDICTOR                
═══════════════════════════════════════════════════════════

📦 Loading model and feature store...
✅ Model loaded successfully!

🌐 Initializing scraper...
✅ Scraper initialized!

🎯 Starting live monitoring for: [Your Match URL]
⏱️  Polling every 2.0 seconds
⌨️  Press Ctrl+C to stop
```

### Live Updates (Every Ball!)
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

📊 Model is more optimistic than DLS baseline by 5.2%

────────────────────────────────────────────────────────────────────────────

                         MATCH SITUATION                                    

Score                 : 145/4
Target                : 32 runs from 27 balls (4.5 overs)
Required Run Rate     : 7.11
Current Run Rate      : 9.35
Status                : ✅ On track!

Pressure Index        : [▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░] 0.35
Pressure Level        : 🟡 MODERATE PRESSURE

────────────────────────────────────────────────────────────────────────────

                   PROBABILITY TREND (Last 10 balls)                       

 70.0% │ █ █   █ █ █   █ █ █ █ 
 65.0% │ █ █ █ █ █ █ █ █ █ █ █ 
 60.0% │ █ █ █ █ █ █ █ █ █ █ █ 
       └──────────────────────
        1 2 3 4 5 6 1 2 3 4 5

────────────────────────────────────────────────────────────────────────────

                             KEY METRICS                                    

Wickets Remaining : 6        Balls Remaining : 27       Resource %   : 45.3%

────────────────────────────────────────────────────────────────────────────

                            RECENT BALLS                                    

Ball         Score           Win Prob    Pressure    Change      
────────────────────────────────────────────────────────────────────────────
15.1         143/4           65.2%       0.33        📈 +2.1%    
15.2         145/4           67.5%       0.35        📈 +2.3%    
15.3         145/4           67.5%       0.35        ─           

═══════════════════════════════════════════════════════════════════════════
Last Updated          : 2025-12-10 18:45:32                                 
                       Press Ctrl+C to stop                                  
═══════════════════════════════════════════════════════════════════════════
```

---

## 🎮 Controls

- **Watch**: Just sit back and watch! Updates automatically every 2 seconds
- **Stop**: Press `Ctrl+C` (or `Cmd+C` on Mac)
- **Results**: Automatically saved to CSV when you stop

---

## 💾 After Stopping

When you press `Ctrl+C`, you'll see:

```
✋ Stopped by user

📊 PREDICTION SUMMARY

Total Balls Predicted    : 48
Current Win Probability  : 67.5%
Average Win Probability  : 55.3%
Win Probability Range    : 45.2% - 78.9%
Average Pressure Index   : 0.42

💾 Predictions exported to: live_predictions_20241210_184532.csv

👋 Goodbye!
```

Your predictions are saved in a CSV file with the timestamp!

---

## 📊 View Your Results

### Option 1: Open in Excel/Numbers
```
Double-click the CSV file
```

### Option 2: View in Python
```python
import pandas as pd

df = pd.read_csv('live_predictions_20241210_184532.csv')
print(df.head())
```

### Option 3: Plot Results
```python
import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_csv('live_predictions_20241210_184532.csv')

plt.figure(figsize=(12, 6))
plt.plot(df.index, df['win_probability'] * 100)
plt.xlabel('Ball Number')
plt.ylabel('Win Probability (%)')
plt.title('Win Probability Throughout Match')
plt.grid(True)
plt.show()
```

---

## 🔧 Customization Options

### Check More Frequently
```bash
# Check every 1 second instead of 2
python src/run_integrated_prediction.py \
    --match-url "YOUR_URL" \
    --model-dir "./models/champion" \
    --poll-interval 1.0
```

### Custom Save Location
```bash
# Save to specific file
python src/run_integrated_prediction.py \
    --match-url "YOUR_URL" \
    --model-dir "./models/champion" \
    --export "./my_predictions/match_1.csv"
```

### Different Model
```bash
# Use different model
python src/run_integrated_prediction.py \
    --match-url "YOUR_URL" \
    --model-dir "./models/another_model"
```

---

## ❓ FAQ

### Where do I find live match URLs?
1. Go to https://www.espncricinfo.com
2. Click on "Live Matches" or "Scores"
3. Click on any live match
4. Copy the URL from your browser

### What if no match is live?
- Wait for a match to start
- You can test with historical matches, but predictions won't update (match is over)

### Can I monitor multiple matches?
Yes! Open multiple terminal windows:
```bash
# Terminal 1
python src/run_integrated_prediction.py --match-url "MATCH_1_URL" --model-dir "./models/champion"

# Terminal 2
python src/run_integrated_prediction.py --match-url "MATCH_2_URL" --model-dir "./models/champion"
```

### What if it hangs or freezes?
1. Press `Ctrl+C` to stop
2. Check your internet connection
3. Verify the match URL is correct
4. Make sure the match is actually live

### Can I run this without the visualization?
Yes! Set headless mode in the script (browser won't open):
- Edit `src/run_integrated_prediction.py`
- Change line: `browser = p.chromium.launch(headless=True)`

---

## 🎯 Pro Tips

1. **Best Experience**: Use a wide terminal window (at least 100 characters wide)
2. **Multiple Monitors**: Run predictions on one screen, watch match on another
3. **Save Everything**: Each run creates a new CSV - you can compare different matches
4. **Analyze Later**: Use the CSV files to study prediction accuracy vs actual results

---

## 🚨 Troubleshooting

### "Playwright not installed"
```bash
pip install playwright
playwright install chromium
```

### "Model not found"
Check that this path exists: `./models/champion/champion_model.joblib`

### "No such file or directory"
Make sure you're in the project directory:
```bash
cd C:\Users\ADMINS\Documents\projects\machine_learning
```

### Browser opens but nothing happens
- The match might not be live yet
- Check if the match URL is correct
- Wait a few seconds for the page to load

---

## 🎉 You're Ready!

Just run:
```bash
python src/run_integrated_prediction.py \
    --match-url "YOUR_LIVE_MATCH_URL" \
    --model-dir "./models/champion"
```

And watch the magic happen! 🏏✨
