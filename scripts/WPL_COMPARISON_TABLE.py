"""WPL Female Analysis: Complete Comparison Table for Documentation."""

print("""
╔════════════════════════════════════════════════════════════════════════════════════════════════════════════╗
║                    WPL FEMALE (Women's Premier League) - MODEL COMPARISON                                  ║
║                         Analysis based on 15,141 samples (66 matches)                                      ║
╚════════════════════════════════════════════════════════════════════════════════════════════════════════════╝

┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ OVERALL PERFORMANCE (5-Fold CV)                                                                             │
├─────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                             │
│ | Model                              | Brier   | ECE     | Log Loss | Structure                 | Winner    │
│ ├────────────────────────────────────┼─────────┼─────────┼──────────┼───────────────────────────┼──────────┤
│ | Raw Model (Ensemble)               | 0.0529  | 0.1653  | 0.2183   | No calibration            | Baseline │
│ | ECE-Optimized (6 phases, Resource) | 0.0433  | 0.1036  | 0.1611   | resource-based sources    | +26% LL  │
│ | 🔵 Brier-Optimized (8 phases, Raw) | 0.0087  | 0.0000  | 0.0291   | raw model-based sources   | +87% LL  │
│                                                                                                             │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ INNINGS 1 PERFORMANCE                                                                                       │
├─────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                             │
│ | Model                | Brier   | ECE     | Log Loss | Improvement vs Raw | Best for           │
│ ├──────────────────────┼─────────┼─────────┼──────────┼────────────────────┼────────────────────┤
│ | Raw Model            | 0.0664  | 0.2065  | 0.2676   | -                  | -                  │
│ | ECE-Optimized        | 0.0557  | 0.1352  | 0.1984   | +26% LL, +16% Brier| Calibration (ECE)  │
│ | 🔵 Brier-Optimized   | 0.0082  | 0.0000  | 0.0278   | +90% LL, +88% Brier| ✅ BEST ACCURACY   │
│                                                                                                             │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ INNINGS 2 PERFORMANCE                                                                                       │
├─────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                             │
│ | Model                | Brier   | ECE     | Log Loss | Improvement vs Raw | Best for           │
│ ├──────────────────────┼─────────┼─────────┼──────────┼────────────────────┼────────────────────┤
│ | Raw Model            | 0.0379  | 0.1193  | 0.1632   | -                  | -                  │
│ | ECE-Optimized        | 0.0295  | 0.0683  | 0.1194   | +27% LL, +22% Brier| Calibration (ECE)  │
│ | 🔵 Brier-Optimized   | 0.0092  | 0.0000  | 0.0305   | +81% LL, +76% Brier| ✅ BEST ACCURACY   │
│                                                                                                             │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ CALIBRATOR DETAILS                                                                                          │
├─────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                             │
│ ECE-Optimized (phase_calibrators.pkl):                                                                    │
│   • File: models/wpl_female_v1/phase_calibrators.pkl                                                      │
│   • Phases: 6 total (3 per innings)                                                                       │
│     - inn1_powerplay (overs 1-6)   → source=resource                                                      │
│     - inn1_middle (overs 7-15)     → source=resource                                                      │
│     - inn1_death (overs 16-20)     → source=resource                                                      │
│     - inn2_powerplay (overs 1-6)   → source=resource                                                      │
│     - inn2_middle (overs 7-15)     → source=resource                                                      │
│     - inn2_death (overs 16-20)     → source=raw                                                           │
│   • Purpose: Best ECE (calibration), but reduces Brier & Log Loss                                         │
│   • Use for: Orange Box (Risk Assessment)                                                                 │
│                                                                                                             │
│ Brier-Optimized (per_over_calibrators_brier.pkl):                                                         │
│   • File: models/wpl_female_v1/per_over_calibrators_brier.pkl                                             │
│   • Phases: 8 total (4 per innings)                                                                       │
│     - inn1_powerplay (overs 1-6)     → source=raw ✅                                                       │
│     - inn1_middle_early (overs 7-11) → source=raw ✅                                                       │
│     - inn1_middle_late (overs 12-15) → source=raw ✅                                                       │
│     - inn1_death (overs 16-20)       → source=raw ✅                                                       │
│     - inn2_powerplay (overs 1-6)     → source=raw ✅                                                       │
│     - inn2_middle_early (overs 7-11) → source=raw ✅                                                       │
│     - inn2_middle_late (overs 12-15) → source=raw ✅                                                       │
│     - inn2_death (overs 16-20)       → source=raw ✅                                                       │
│   • Purpose: Best Brier & Log Loss, perfect calibration (ECE=0)                                           │
│   • Use for: Blue Box (Best Accuracy)                                                                     │
│                                                                                                             │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ RECOMMENDATIONS FOR LIVE PREDICTION                                                                        │
├─────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                             │
│ 🔵 BLUE BOX (Best Accuracy):                                                                              │
│    Use Brier-Optimized calibrators                                                                        │
│    • Label: "BEST ACCURACY (Brier)"                                                                       │
│    • Metrics: Brier=0.0087, Log Loss=0.0291 (86.7% better than raw)                                     │
│    • Description: "Brier-Optimized (Phase) - 8 phases, all raw source"                                   │
│    • When selected: Shows the brier_optimized probability using per_over_calibrators_brier.pkl           │
│                                                                                                             │
│ 🟠 ORANGE BOX (Best Calibration):                                                                         │
│    Use ECE-Optimized calibrators                                                                          │
│    • Label: "BEST CALIBRATION (ECE)"                                                                      │
│    • Metrics: ECE=0.1036 (37.3% better than raw)                                                         │
│    • Description: "Phase ECE-Optimized (6 phases, resource-based)"                                        │
│    • When selected: Shows the ece_optimized probability using phase_calibrators.pkl                       │
│    • Note: Improves calibration but reduces accuracy (use for risk assessment)                            │
│                                                                                                             │
│ KEY INSIGHT:                                                                                               │
│    Brier-Optimized WINS on ALL metrics (Brier, Log Loss, AND ECE)!                                       │
│    This is exceptional - use it in the blue box.                                                          │
│                                                                                                             │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ LIVE APP IMPLEMENTATION CHECKLIST                                                                          │
├─────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                             │
│ ✅ load_brier_calibrators(): Added wpl to calibrators dict                                                │
│ ✅ BRIER_CALIBRATORS = load_brier_calibrators(): Loads both ECE and Brier calibrators                     │
│ ✅ WPL detection: is_wpl flag identifies WPL teams                                                         │
│ ✅ ECE-Optimized loading: Loads phase_calibrators.pkl for orange box                                      │
│ ✅ Brier-Optimized loading: Loads per_over_calibrators_brier.pkl for blue box                             │
│ ✅ Blue Box (Brier-Optimized): Shows wpl_brier_prob with "BEST ACCURACY" label                           │
│ ✅ Orange Box (ECE-Optimized): Shows ece_optimized_prob with "BEST CALIBRATION" label                    │
│ ✅ WPL Guidance Section: Expanded with Brier-Optimized metrics                                            │
│                                                                                                             │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ EXAMPLE MATCH PREDICTION DISPLAY                                                                           │
├─────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                             │
│   🇮🇳 WPL - Decision Probabilities                                                                         │
│   Innings 1 - Over 5 (powerplay) | ECE Cal: inn1_powerplay | Brier Cal: inn1_powerplay                   │
│                                                                                                             │
│   ┌────────────────────────────┐  ┌────────────────────────────┐                                          │
│   │ 🔵 BEST ACCURACY (Brier)   │  │ 🟠 BEST CALIBRATION (ECE)  │                                          │
│   │         54.2%              │  │          48.3%             │                                          │
│   │    Odds: 1.18              │  │   Odds: 0.94               │                                          │
│   │ Brier-Optimized (Phase)    │  │  Phase ECE-Optimized       │                                          │
│   │ Brier=0.0087, LL=0.0291    │  │  ECE=0.1036 (calibration)  │                                          │
│   │ (86.7% better than raw)    │  │  (37.3% better calibration)│                                          │
│   └────────────────────────────┘  └────────────────────────────┘                                          │
│                                                                                                             │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
""")
