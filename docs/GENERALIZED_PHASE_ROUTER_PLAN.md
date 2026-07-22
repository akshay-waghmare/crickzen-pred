# Generalized Phase Router Plan

The combined models will follow the proven IPL structure: a complete innings-1 model, followed by independently evaluated innings-2 phase models. A phase model is promoted only if it improves held-out Brier/log loss/calibration and does not regress gender or match-level slices. The final artifact is a router that can mix model versions by phase, just as IPL v17 uses v17 for powerplay and v14 for middle/death.

See `specs/022-generalized-phase-router-models/` for the execution contract.

## First promotion-gate result — 2026-07-12

The first candidates were evaluated chronologically: train seasons before 2025, test seasons 2025 and later, with all/male/female slices.

- T20 PP: rejected; candidate regressed overall by 9.08% Brier.
- T20 MID: rejected; candidate regressed overall by 4.06%.
- T20 DEATH: rejected; improved overall by 0.46% but regressed the female slice by 1.14%.
- ODI PP: rejected; regressed overall by 4.61%.
- ODI MID: rejected; regressed overall by 6.98%.
- ODI SETUP: rejected; regressed overall by 0.98%.
- ODI DEATH: rejected; improved overall by 2.65% but regressed the male slice by 6.94%.

Decision: no phase candidate is promoted. CrickZen continues using the complete gender-aware v2 models. The phase artifacts remain research candidates for feature refinement and future OOS windows.
