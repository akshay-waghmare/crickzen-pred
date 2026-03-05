"""
Summary: Why Innings 2 recording is missing

DIAGNOSIS:
1. Recording stopped after 18.3 overs of Innings 1 (SA: 159/6)
2. Match was still in progress (incomplete Innings 1)
3. No Innings 2 data was ever recorded
4. Recording was "finalized" (match_state_logger.finalize() called)

ROOT CAUSE:
The predictor's `poll_and_predict()` loop likely hit one of these conditions:
  a) User stopped predictor (Ctrl+C) before Innings 2 appeared on CREX
  b) Network error / page timeout during transition between innings
  c) CREX page hadn't updated to show Innings 2 yet when finally() was called
  d) Predictor crashed silently during poll

CURRENT BEHAVIOR:
- MatchStateLogger uses deduplication (record_key = (innings, over, ball, runs, wickets))
- Once finalize() is called, no new records can be added (buffer cleared)
- Even if Innings 2 data arrived later, it wouldn't be recorded

FIX RECOMMENDATIONS:

1. IMMEDIATE: Don't call finalize() until match is truly complete
   - Only finalize when: batting team wins OR all out OR 20 overs bowled
   - Current code calls finalize(result_type="in_progress") on Ctrl+C

2. RESUME SUPPORT: Enable recording to continue if match_state_logger is reused
   - Keep _seen_record_keys across resume() calls
   - Allow appending new innings to existing parquet file

3. MONITORING: Detect when polling stops unexpectedly
   - Check for consecutive identical states (stale page)
   - Log warnings if same state polled 5+ times in a row

4. VALIDATION: Verify complete innings before declaring Innings 1 done
   - For Innings 1: wait for 20.0 overs OR all out before calling finalize()
   - For Innings 2: wait for match result before finalizing

CURRENT RECORDINGS STATUS:
  T20I Male (10 matches):
    - 1 match (IND vs SA): Incomplete - Innings 1 only (18.3 overs, 120 balls), no Innings 2
    - 9 matches: Partial or complete (afgvscan: 235 balls, ind-vs-ned: 224 balls, etc.)
  
  Total: 1,366 ball states from live T20I matches
  Complete Innings 2: ~370 balls (from ind-vs-ned, ita-vs-wi, nam-vs-pak, afg-vs-can, sl-vs-zim)

ACTION ITEMS:
1. Modify crex_live_predictor.py to NOT call finalize() until match is actually complete
2. Add logging to track when finalize() is called and why
3. Consider checkpointing mechanism to resume recording if predictor restarts
4. Test with long-running live matches (5+ hours)
"""

# Print this summary
print(__doc__)

# Save to file for reference
with open('data/RECORDING_INCOMPLETENESS_ANALYSIS.md', 'w') as f:
    f.write(__doc__)

print("\nAnalysis saved to: data/RECORDING_INCOMPLETENESS_ANALYSIS.md")
