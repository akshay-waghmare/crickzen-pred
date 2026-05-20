# Implementation Plan: Telegram Public Signals Agent

**Branch**: `015-telegram-public-signals` | **Date**: 2026-05-01 | **Spec**: [spec.md](spec.md)

## Summary

Create an operator-facing CrickZen IPL Telegram signal agent that turns IPL v6 model and dashboard state into disciplined public posts. The goal is to own the IPL prediction attention layer first: free pre-match and live probability updates, public accuracy tracking, and honest final reviews. Dashboard conversion comes through restrained CTAs after value is visible.

This extends, rather than replaces, the older Telegram ledger and public dashboard growth work:

- `specs/006-telegram-prediction-ledger`: immutable Telegram posting and append-only storage.
- `specs/013-public-dashboard-growth`: public pages, lite API, Telegram dry-run hooks, dashboard CTA.
- This spec: channel operating system, signal agent prompt, lifecycle templates, accuracy tracker, and first-hour launch workflow.

## Technical Context

**Language/Version**: Python 3.10+ for implementation work; Markdown for agent/spec artifacts  
**Primary Dependencies**: Existing `python-telegram-bot`, existing `src/bbl_pipeline/telegram`, dashboard FastAPI/Jinja/Alpine stack  
**Prediction Source**: IPL v6 live model output and dashboard public serializer  
**Storage**: Existing Telegram ledger JSONL for posted messages; new tracker can start as JSONL/CSV and later render in dashboard  
**Testing**: pytest for formatter/tracker logic; dry-run mode without live Telegram credentials  
**Target Platform**: Local operator workflow first, production dashboard and Telegram channel after deployment  
**Constraints**: Manual approval before publish, no cherry-picking, no betting guarantees, no fixture invention  
**Scale/Scope**: One IPL public channel, one operator, roughly 5-8 posts per match

## Constitution Check

**Verdict**: PASS

- Does not retrain or alter IPL v6 model behavior.
- Uses current model/dashboard state as source of truth.
- Adds distribution and accountability artifacts without mutating feature pipelines.
- Requires tests for any code implementation that formats posts, detects lifecycle events, or writes tracker rows.
- Keeps public copy and tracker output separate from premium dashboard internals.

## Project Structure

### Documentation and Agent Artifacts

```text
specs/015-telegram-public-signals/
├── spec.md
├── plan.md
└── tasks.md

.github/agents/
└── crickzen.telegram.signals.agent.md
```

### Likely Source Code Follow-Up

```text
dashboard/app/
├── telegram_distribution.py        # From public dashboard growth spec
└── telegram_signals.py             # Signal lifecycle/tracker service if separated

src/bbl_pipeline/telegram/
├── message_formatter.py            # Extend with signal templates if reused
├── storage.py                      # Reuse append-only storage pattern
└── bot_client.py                   # Reuse live posting client

data/
└── telegram_signal_tracker.jsonl    # Append-only tracker candidate

tests/
└── telegram/
    ├── test_signal_formatter.py
    └── test_signal_tracker.py
```

## Operating Model

### First Hour Workflow

1. Create public Telegram channel: `CrickZen IPL Probability` or closest available name.
2. Set bio exactly:

   ```text
   Ball-by-ball IPL win probability powered by ML. Free pre-match and live prediction updates. Built by CrickZen.
   ```

3. Create bot via BotFather and add it as channel admin with post permission.
4. Configure secrets locally/prod:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHANNEL_ID`
   - `PUBLIC_DASHBOARD_BASE_URL`
5. Post and pin "How this channel works".
6. Publish same-day pre-match signal only after fixture and model state are verified.
7. Share one restrained invite in up to three relevant cricket/fantasy groups where sharing is allowed.
8. During match, post at toss, 6 overs, 10 overs or mid-innings, innings break, chase midpoint, and final review.
9. Update the accuracy tracker after the final review.

### Pinned Post Template

```text
How this channel works

CrickZen posts IPL win probability updates from our ML model.

What you will see:
- Pre-match favorite before toss when model state is ready
- Toss update if conditions change the view
- Powerplay and mid-match probability movement
- Innings break and chase pressure updates
- Final review after the match, including misses

We track every pre-match favorite publicly:
Date | Match | Pre-match favorite | Final result | Confidence | What changed

This is cricket analytics, not guaranteed betting advice. The free channel shows the public view. The dashboard gives deeper probability timeline, projections, and model context.
```

### Public Invite Copy

```text
I have started a free CrickZen IPL Probability channel.

It posts pre-match and live win probability updates from an ML model, then records the final review publicly after the match.

No paid tips, no stake sizing, no deleted misses. Just model probability updates and an accuracy tracker.

Channel: <telegram-channel-link>
```

## Signal Lifecycle

### Pre-Match Before Toss

Purpose: Public proof before match conditions are known.

Required fields:

- Match
- Phase: `Pre-match before toss`
- Model favorite
- Win probability or confidence band
- Model caveat
- Dashboard CTA if available

Example shape:

```text
IPL Pre-match Signal
Match: RR vs DC
Phase: Before toss
Model favorite: <team>
Confidence: <Low/Medium/High> (<rounded_probability>%)
Why: <one model-readable reason>
Caveat: Toss and confirmed XI can move this.

Full dashboard: <url>
```

### Toss Update

Purpose: Explain whether toss changed the pre-match view.

```text
Toss Update
Match: <match>
Toss: <team> chose <bat/bowl>
Pre-match favorite: <team>
Current favorite: <team>
Change: <+/- points or no major change>
Read: <one sentence>
```

### Powerplay Update

Purpose: Own early attention around the first major match checkpoint.

```text
Powerplay Update
Match: <match>
Score: <score> after 6 overs
Current favorite: <team> (<rounded_probability>%)
Move since pre-match: <+/- points>
What changed: <one reason>
```

### Mid-Match and Innings Break

Purpose: Convert score into par/chase interpretation.

```text
Mid-innings Update
Match: <match>
Score: <score> after <overs>
Model read: <ahead/behind par or chase pressure>
Current favorite: <team> (<rounded_probability>%)
What changed: <one reason>
```

### Chase Midpoint

Purpose: Explain whether chase is controlled, under pressure, or unstable.

```text
Chase Midpoint
Match: <match>
Chase state: <runs needed> from <balls>, <wickets> wickets left
Current favorite: <team> (<rounded_probability>%)
Pressure read: <one sentence>
```

### Final Review

Purpose: Build trust by being honest, especially on misses.

```text
Final Review
Match: <match>
Pre-match favorite: <team> (<confidence>)
Winner: <team>
Model call: <Right/Wrong>
What changed: <concrete match factor>
Review: <one brutally honest sentence>

Tracker updated.
```

## Accuracy Tracker

Minimum fields:

| Field | Purpose |
|-------|---------|
| Date | Match date in local public context |
| Match | Human-readable teams |
| Pre-match favorite | Team selected before toss |
| Final result | Winning team/result |
| Confidence | Low, Medium, High, plus optional rounded probability |
| What changed | One plain-English reason from toss/live/final review |

MVP storage can reuse append-only JSONL:

```json
{
  "date": "2026-05-01",
  "match": "RR vs DC",
  "pre_match_favorite": "RR",
  "final_result": "DC won",
  "confidence": "Medium (57%)",
  "what_changed": "DC powerplay wickets moved chase pressure earlier than model expected",
  "telegram_message_id": 12345,
  "dashboard_url": "https://..."
}
```

## Guardrails

- Verify fixture, team names, and start time from CREX/dashboard before publishing.
- Verify model output timestamp before every post.
- Use rounded probabilities publicly; keep detailed internals for dashboard.
- Never say "sure shot", "guaranteed", "lock", "fixed", or similar certainty language.
- Never give stake sizing.
- Never skip final review after a wrong call.
- Never edit old proof posts; publish a correction or review post instead.
- Do not share repeatedly in groups that do not invite promotional links.

## Dashboard CTA Plan

The CTA should be useful but secondary:

- Pre-match: "Full dashboard: <url>"
- Live updates: "Track live probability: <url>"
- Final review: "See full probability timeline: <url>"

If the production dashboard is not live, omit the CTA from match posts and use the channel as proof ledger until deployment is ready.

## Implementation Sequence

### Step 1 - Agent Brief

Add `.github/agents/crickzen.telegram.signals.agent.md` with:

- Goal: own IPL prediction attention layer first.
- Required source checks: fixture, model timestamp, dashboard URL.
- Lifecycle templates.
- Accuracy tracker rules.
- Copy guardrails.

### Step 2 - Dry-Run Drafting

Add dry-run generation before live posting:

- Input: fixture + model snapshot + lifecycle phase.
- Output: Telegram-ready draft and readiness status.
- Refuse publish-ready output if fixture/model state is stale.

### Step 3 - Tracker

Implement append-only tracker row generation:

- One tracker row per public pre-match signal.
- Final review required before row is complete.
- Tests cover right call, wrong call, no-result, and missing final review.

### Step 4 - Telegram Posting

Reuse existing Telegram config/client:

- Bot token and channel ID from env.
- Manual operator approval.
- Store Telegram message IDs.
- No credentials required in tests.

### Step 5 - Dashboard CTA

Wire posts to production public match URLs:

- Read `PUBLIC_DASHBOARD_BASE_URL`.
- Include match-specific URL when available.
- Omit CTA if URL not configured or dashboard health check fails.

### Step 6 - Launch Runbook

Document the first-hour checklist in repo docs or quickstart:

- Create channel.
- Set bio.
- Pin "How this channel works".
- Post first match signal.
- Share in allowed groups.
- Run lifecycle.
- Publish final review.

## Validation

Run focused tests once implementation exists:

```powershell
pytest tests/telegram/test_signal_formatter.py tests/telegram/test_signal_tracker.py -q
```

For dashboard distribution work:

```powershell
cd dashboard
.venv\Scripts\python.exe -m pytest tests/test_telegram_distribution.py -q
```

Manual launch validation:

1. Confirm Telegram bot can post to a private test channel.
2. Confirm production dashboard `/health` returns OK.
3. Generate a dry-run pre-match post.
4. Publish to test channel.
5. Verify storage/tracker row contains Telegram message ID.
6. Only then post to public channel.

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Overclaiming model accuracy | Use confidence bands, caveats, and final reviews |
| Public wrong prediction hurts trust | Publish honest review and tracker row; this is the trust mechanism |
| Stale model state gets posted | Require timestamp freshness and manual approval |
| Dashboard not ready at match time | Omit CTA and post Telegram-only proof |
| Telegram token leak | Environment variables only; never log token |
| Group spam backlash | Share once, obey group rules, lead with free analytics |

## Open Decisions

- Final public channel username.
- Production dashboard base URL.
- Exact confidence band thresholds.
- Whether tracker is initially JSONL-only, dashboard-rendered, or both.
