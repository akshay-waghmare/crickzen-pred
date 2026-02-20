# Global vs League-Specific Model Comparison

## Results Summary

| League | League Model | Global + Calibrator | Improvement | Winner |
|--------|--------------|---------------------|-------------|--------|
| **BBL** | 0.1757 (BBL v12 best OOF) | **0.1713** | **-2.5%** | ✅ Global |
| **SA20** | 0.1597 (SA20 v2 best OOF) | **0.1582** | **-0.9%** | ✅ Global |
| **SSM** | N/A | 0.1682 | N/A | ✅ Global only |

## Why Does Global Win?

### 1. **Massive Training Data Advantage**
- **Global T20 Model**: 1,893,892 samples from 5,353 matches across 11 leagues
- **BBL v12**: 141,435 samples (13× less data)
- **SA20 v2**: 26,121 samples (72× less data)

### 2. **Transfer Learning Benefits**
The global model learns universal T20 patterns:
- Chase dynamics across different pitch types
- Powerplay/middle/death phase progressions  
- Wicket impact on win probability
- DLS resource calculations

Then league calibration adapts these patterns to specific leagues using Temperature/Platt scaling.

### 3. **Better Generalization**
League-specific models can overfit to:
- Small sample sizes (especially SA20 with only 121 matches)
- Specific teams/venues in that league
- Historical meta (may not apply to new seasons)

Global models with calibration:
- Learn from diverse conditions
- Adapt to league via parametric calibration (T or a,b)
- More robust to new teams/players

## Calibration Strategy

```
┌─────────────────────────────────────────┐
│   GLOBAL T20 MODEL (Frozen)             │
│   1.9M samples, 11 leagues              │
│   Learns universal T20 patterns         │
└─────────────────────────────────────────┘
              ↓
    predict_proba(X) → raw_probs
              ↓
┌─────────────────────────────────────────┐
│   LEAGUE CALIBRATOR                     │
│   Temperature/Platt Scaling             │
│   2 params per league (innings 1 & 2)   │
└─────────────────────────────────────────┘
              ↓
        calibrated_probs
```

### BBL Example
- **Global raw**: Brier 0.1721
- **BBL calibrator**: T₁=0.8470, T₂=0.8295 (sharper predictions)
- **Final**: Brier 0.1713 (-0.4% vs raw, **-2.5% vs BBL v12**)

### SA20 Example
- **Global raw**: Brier 0.1589
- **SA20 calibrator**: T₁=0.8988, T₂=0.7651 (very sharp for chases!)
- **Final**: Brier 0.1582 (-0.4% vs raw, **-0.9% vs SA20 v2**)

## Temperature Insights

| League | T (Inn 1) | T (Inn 2) | Interpretation |
|--------|-----------|-----------|----------------|
| BBL | 0.847 | 0.830 | Sharper predictions overall |
| SA20 | 0.899 | 0.765 | **Very sharp 2nd innings** (chases predictable) |
| SSM | 0.877 | 0.888 | Balanced sharpening |

**All T < 1**: Global model is calibrated for ALL leagues, so league-specific calibration makes it more confident (sharper) for each individual league.

## Practical Implications

### Use Global + Calibration When:
✅ League has 100-500+ matches  
✅ Need robust predictions across multiple leagues  
✅ Want to avoid league-specific overfitting  
✅ New teams/players join the league  

### Use League-Specific Model When:
❌ None - Global + calibration wins in all tested cases!  
(Maybe if league has radically different rules, but not in current T20 formats)

## Recommendation

**Retire league-specific models (BBL v12, SA20 v2) in favor of:**
```
Global T20 Male v1 + League Calibrators
```

**Benefits:**
1. Better accuracy (-0.9% to -2.5% Brier)
2. Single model to maintain
3. Easier to add new leagues (just calibrate)
4. More robust to meta shifts
5. Transfer learning from all T20 cricket

**Migration Path:**
1. Keep BBL v12, SA20 v2 as baselines for validation
2. Deploy Global + Calibrators in production
3. Monitor for 1-2 seasons
4. Archive league-specific models if performance holds
