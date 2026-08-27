# Production Incident: Nepal A Team Identity Flip

**Date:** 2026-08-27  
**Status:** Resolved  
**Match:** 13KJ — Hyderabad Kingsmen Academy vs Nepal A  
**Component:** CREX live predictor team-role reconciliation

## Impact

During the Nepal A chase, the live source correctly reported Nepal A as the batting team, but the predictor reconciler treated the URL token `nep-a` as `Nepal`. Because `NEP-A` and `Nepal` did not compare as the same identity, it rewrote the live roles to the URL order. The public prediction therefore showed the wrong batting team and attached the win probability to the wrong side.

The score and target feed were fresh; this was a team-identity and batting-role error, not a scraper outage or model-score staleness issue.

## Root cause

`_known_team_codes()` did not recognize the provider token `nep-a`. URL parsing reduced `nep-a-20th-match...` to `Nepal`, while the live snapshot used `NEP-A`. The final unrelated-bowling-side repair then overwrote the valid live role assignment.

## Fix

Commit `4f4d74d` (`fix(predictor): preserve Nepal A batting identity`) made two narrow changes:

- recognize `nep-a` as the canonical URL identity;
- preserve a valid live batting identity when it matches either URL-derived side, including alias-equivalent names.

An exact regression test for the 13KJ URL was added. The predictor test file passes with `21 passed`.

## Production rollout

- Source installed at `/home/administrator/crickzen-releases/opening-r1-20260801/model/src/bbl_pipeline/inference/crex_live_predictor.py`.
- Deployed source SHA-256: `ec582e05a26b5028c6ff5a2598de503afdf4b7319c6f459721a566737e7f007a`.
- Rollback copy retained at `/home/administrator/crickzen-releases/opening-r1-20260801/model/rollback-20260827-nep-a-team-identity/crex_live_predictor.py` with SHA-256 `da11265c1562b465bee8e3c8ce4da18a05ee4e0a041545379ddec13d09a9371d`.
- Only `crickzen-dashboard` was restarted. It returned healthy with restart count `0`; the running image digest remained `sha256:ba27fd59d18f2aee2a3991eb565aeee2b324366924f3bc9401a851b252f965ac`.

## Post-deploy proof

The live source, public prediction API, and public detail page agreed on the corrected roles:

- public title: `NEP-A vs HYK`;
- `batting_team=NEP-A`;
- `bowling_team=HYK`;
- target: `198`;
- detail route: `/prediction-api/match/nep-a-vs-hyk-t20-win-probability`, HTTP `200`, rendering `Batting NEP-A` and `Bowling HYK`.

The displayed 7% probability was correctly Nepal A's batting-side probability; Hyderabad Kingsmen Academy was the complementary 93% favorite. The apparently hard-favorite result was therefore not caused by flipped team labels after the fix.

## Prevention and follow-up

- Keep the exact provider URL and alias case as a regression fixture.
- Treat team identity reconciliation as a guarded boundary: never replace a valid live role with URL order unless neither live side matches either URL-derived side.
- Verify future predictor incidents across source snapshot, public API, and rendered detail page; a fresh timestamp or HTTP 200 alone is insufficient.
- Keep the rollback copy until the next production release is independently verified.

The incident is closed. No model artifact or probability-calibration change was made.
