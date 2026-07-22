# Plan

1. Finish and verify gender-aware combined T20/ODI v2 baseline models.
2. Build chronological innings-2 phase datasets using format-specific phase boundaries.
3. Train T20 PP/MID/DEATH candidates and ODI PP/MID/SETUP/DEATH candidates.
4. Evaluate every candidate against the complete innings model by phase, gender, and match.
5. Add market comparison datasets where available and keep market data strictly OOS.
6. Promote only winning phase candidates into `routing_config.json`.
7. Add conditional fallback and guarded post-model calibration only after sufficient OOS evidence.
8. Integrate the router through the existing `Inn2PhaseRouter` and verify CrickZen fallback resolution.
