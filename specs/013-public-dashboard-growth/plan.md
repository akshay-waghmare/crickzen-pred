# Implementation Plan: Public Dashboard Growth Surfaces

**Spec**: `specs/013-public-dashboard-growth/spec.md`  
**Branch**: `013-public-dashboard-growth`  
**Date**: 2026-04-27  

---

## Summary

Add a public acquisition layer in front of the existing authenticated CrickenZen dashboard. The MVP introduces public SEO pages (`/`, `/ipl-prediction-today`, `/match/{slug}`, `/prediction/{league}/{teams}`), a public lite API (`/api/public/*`), a safe serializer that redacts premium model fields, deterministic model insight copy, and upgrade CTAs into the full dashboard.

The key product shift is:

```text
Private-only dashboard → Public prediction surfaces → Login/paid dashboard depth
```

This plan intentionally does **not** retrain models or rebuild the dashboard. It exposes a small, safe slice of the value that already exists.

---

## Technical Context

### Current Web Stack

- FastAPI app factory: `dashboard/app/main.py`
- Page routes: `dashboard/app/routers/pages.py`
- Authenticated live API: `dashboard/app/routers/live.py`
- Prediction process manager: `dashboard/app/prediction_manager.py`
- Templates: `dashboard/templates/`
- Shared frontend JS: `dashboard/static/js/dashboard.js`
- Dashboard tests: `dashboard/tests/`

### Important Current Behavior

- `/` currently redirects to `/dashboard`.
- `/dashboard` is the main authenticated dashboard page.
- `/api/matches/*` requires auth for useful state.
- `/api/matches/auto/status` exposes scheduler candidates only to authenticated users.
- Public league listing and league detection currently do not require auth.
- `PredictionManager` keeps predictions in memory, so public pages can show only active/recent runtime state unless future persistence is added.

---

## Architecture

### New Modules

| File | Purpose |
|------|---------|
| `dashboard/app/public.py` | Public serialization, slug helpers, insight builder, public match service |
| `dashboard/app/routers/public.py` | Unauthenticated `/api/public/*` API routes |
| `dashboard/templates/public.html` | Public acquisition home page |
| `dashboard/templates/ipl_today.html` | SEO page for "IPL prediction today" intent |
| `dashboard/templates/match_public.html` | Public match detail page |
| `dashboard/tests/test_public.py` | Public API/page tests |
| `dashboard/tests/test_public_insights.py` | Pure insight/serializer tests |

### Optional Later Modules

| File | Purpose |
|------|---------|
| `dashboard/app/entitlements.py` | Plan capability policy for free/pro/premium/team |
| `dashboard/app/telegram_distribution.py` | Dashboard-side Telegram event generation/dry-run service |
| `dashboard/tests/test_telegram_distribution.py` | Telegram event dedupe tests |

### Router Registration

Register `public_router` in `dashboard/app/main.py` before the page router:

```python
from app.routers.public import router as public_router

application.include_router(public_router)
...
application.include_router(pages_router)
```

The public API should be independent from `app.routers.live` to avoid accidentally exposing premium state.

---

## Public Data Boundary

### Allowed Public Fields

Public match list/detail payloads may expose:

- `slug`
- `title`
- `league`
- `status`
- `score`
- `overs`
- `batting_team`
- `bowling_team`
- `venue`
- `target`
- `win_probability_pct`
- `projection_label`
- `insight`
- `last_swings` (detail only, max 5)
- `updated_at`
- `detail_url`
- `dashboard_url`

### Forbidden Public Fields

The public serializer must never return:

- `monte_carlo`
- `odm`
- `blend`
- `features`
- `pred_state`
- `scraped_data`
- `history`
- `chart_history`
- `commentary`
- `ball_history`
- `balls_data`
- `ml_prob`
- `mc_prob`
- `ml_weight`
- `mc_weight`
- raw model probability decimals

### Internal State Source

The public service should reuse safe pieces from existing enriched state logic without returning the enriched dict itself. Use this pattern:

1. Get active predictions from `PredictionManager.list_predictions()`.
2. For each active prediction, call `manager.get_prediction(id)` and `pred.read_state()`.
3. Call existing enrichment only internally if needed for projection/history:
   - `_enrich_detail_state(state, pred.output_json_path)`
4. Immediately pass the result into the public serializer.
5. Drop the enriched state object and return only `PublicMatchSummary`/`PublicMatchDetail`.

This avoids duplicating projection math while preserving a strict output boundary.

---

## Slug Strategy

### Active Match Slug

Prefer resolved teams from state:

```text
dc-vs-rcb-ipl-2026-win-probability
```

Fallback to CREX URL slug:

```text
dc-vs-rcb-39th-match-indian-premier-league-2026
```

### Slug Helper Requirements

- Lowercase ASCII
- Replace non-alphanumeric runs with `-`
- Trim leading/trailing `-`
- Keep slug stable across reloads where possible
- Store no persistent slug registry in MVP; resolve dynamically from active predictions and scheduler candidates

### Known Limitation

Without persistence, a match page may stop resolving after process restart or match cleanup. This is acceptable for MVP because the target traffic is live-match spike traffic. Future work can persist discovered match records.

---

## Insight Builder

Create pure helper functions in `dashboard/app/public.py`:

```python
def build_public_insight(state: dict | None, swings: list[dict]) -> str:
    ...
```

Priority order:

1. **Probability swing**: If recent movement >= 5 percentage points, say which side gained.
2. **Second-innings pressure**: If target/RRR/balls remaining exist, describe chase pressure.
3. **First-innings par**: If projected score and par/venue average exist, describe ahead/behind par.
4. **Basic probability**: If probability exists but no other context, describe model edge.
5. **Fallback**: "Model probability will appear once live ball data is available."

Example outputs:

- `RCB win probability up 8% across the last 2 overs.`
- `Chasing side under pressure: required rate is above current scoring pace.`
- `Batting side is tracking 12 runs above par.`
- `Model currently gives DC a narrow edge.`
- `Model probability will appear once live ball data is available.`

Keep copy conservative. Do not frame predictions as betting guarantees.

---

## Public Pages

### `/` Public Home

Replace redirect in `dashboard/app/routers/pages.py`:

```python
@router.get("/", response_class=HTMLResponse)
def index(request: Request):
    ...
    return templates.TemplateResponse(request, "public.html", {...})
```

Primary content:

- Brand/product signal: CrickenZen live cricket prediction engine
- Today/live match cards
- Quick explanation of free vs full dashboard
- CTA to `/ipl-prediction-today`
- CTA to `/login`

Avoid a pure marketing-only landing page. The first viewport should show live prediction content or upcoming cards.

### `/ipl-prediction-today`

SEO intent page:

- Title: `IPL Prediction Today | Live Win Probability - CrickenZen`
- Public IPL match cards
- If no active match, show upcoming IPL candidates
- Link each card to `/match/{slug}`
- CTA: `Unlock full model dashboard`

### `/match/{slug}`

Match detail page:

- Match title and status
- Score
- Rounded win probability or awaiting-model state
- Projected score or chase pressure
- Last 5 public swings
- One insight sentence
- Locked premium section preview: MC, ODM, full timeline, commentary
- CTA to login/register/dashboard

### `/prediction/{league}/{teams}`

Alias route:

- Resolve using same public service.
- If match found, render `match_public.html`.
- If not found, render a public fallback search-intent page with today's league cards.

---

## Public API Contracts

### `GET /api/public/matches`

Returns all public-safe active predictions plus relevant discovered candidates.

Example:

```json
{
  "matches": [
    {
      "slug": "dc-vs-rcb-ipl-2026-win-probability",
      "title": "DC vs RCB",
      "league": "IPL",
      "status": "running",
      "score": "128/4",
      "overs": "14.2",
      "win_probability_pct": 57,
      "projection_label": "Projected 184",
      "insight": "RCB win probability up 8% across the last 2 overs.",
      "updated_at": "2026-04-27T14:33:58Z",
      "detail_url": "/match/dc-vs-rcb-ipl-2026-win-probability"
    }
  ],
  "generated_at": "2026-04-27T14:34:01Z"
}
```

### `GET /api/public/ipl-today`

Same response shape as `/api/public/matches`, filtered to IPL candidates/matches only.

Filtering rules:

- `league == "IPL"` for internal predictions/candidates
- OR source/URL contains `indian-premier-league`
- Reject generic live-score candidates that do not match IPL metadata

### `GET /api/public/matches/{slug}`

Returns:

```json
{
  "match": {
    "...summary fields": "...",
    "venue": "Venue TBC",
    "target": 181,
    "last_swings": [
      { "over": "12.4", "score": "101/3", "win_probability_pct": 55, "label": "+6%" }
    ],
    "dashboard_url": "/dashboard"
  }
}
```

If unresolved:

```json
{
  "detail": "Match not found",
  "suggested_url": "/ipl-prediction-today"
}
```

with HTTP 404.

---

## Telegram Distribution Plan

### MVP Scope

Do not post live messages in the first code pass. Build dry-run event generation first:

- Consume `PublicMatchDetail`
- Generate message text
- Deduplicate events by `match_slug:event_type:event_key`
- Store in memory for MVP or in SQLite later

### Event Types

| Event | Trigger |
|-------|---------|
| `match_live` | First public state for a running match |
| `milestone` | Over crosses 5, 10, 15, 20, etc. |
| `swing` | Win probability movement >= configured threshold |
| `final_pressure` | Second innings with <= 12 balls remaining |
| `match_finished` | Status becomes finished/stopped with final score |

### Later Posting

Once dry-run is tested, wire to existing `src/bbl_pipeline/telegram/bot_client.py` and config. Keep credentials out of tests.

---

## Entitlement Plan

### MVP

Public API is always free and redacted.

Existing authenticated dashboard remains full-access for now unless a separate billing feature is implemented. The public pages should still visually preview locked premium surfaces:

- Monte Carlo detail
- ODM signal
- Full timeline
- Commentary
- Alerts
- Multi-match dashboard

### Next Feature

Add `dashboard/app/entitlements.py`:

```python
PLAN_CAPABILITIES = {
    "free": {"max_matches": 0, "mc": False, "odm": False, "alerts": False},
    "monthly": {"max_matches": 2, "mc": True, "odm": True, "alerts": True},
    "yearly": {"max_matches": 4, "mc": True, "odm": True, "alerts": True},
    "admin": {"max_matches": 99, "mc": True, "odm": True, "alerts": True},
}
```

Full payment integration should be a separate Stripe spec.

---

## Implementation Steps

### Step 1 — Public Service and Serializer

Add `dashboard/app/public.py` containing:

- slug helpers
- probability rounding helper
- public swing extraction
- projection label builder
- insight builder
- premium key redaction tests
- `PublicMatchService`

The service should accept optional `request.app.state.auto_scheduler` for candidate discovery. For testability, make core functions pure and pass scheduler status as data where possible.

### Step 2 — Public API Router

Add `dashboard/app/routers/public.py` with:

- `GET /api/public/matches`
- `GET /api/public/ipl-today`
- `GET /api/public/matches/{slug}`

Register router in `dashboard/app/main.py`.

### Step 3 — Public Page Routes

Update `dashboard/app/routers/pages.py`:

- change `/` to render `public.html`
- add `/ipl-prediction-today`
- add `/match/{slug}`
- add `/prediction/{league}/{teams}`

Routes should call `PublicMatchService` and pass already-renderable payloads into templates.

### Step 4 — Public Templates

Add:

- `dashboard/templates/public.html`
- `dashboard/templates/ipl_today.html`
- `dashboard/templates/match_public.html`

Use existing `base.html`, `nav.html`, CSS utility classes, and dashboard visual style. Keep the first viewport focused on prediction content, not long explanatory copy.

### Step 5 — Client Enhancement

Optional MVP enhancement:

- Add lightweight polling to public pages via `dashboard/static/js/dashboard.js` or inline Alpine in templates.
- Public pages must still render useful initial server-side content without JS.

### Step 6 — Telegram Dry-Run Events

Add `dashboard/app/telegram_distribution.py` only after Steps 1-4 are stable:

- event detector
- dedupe store interface
- message formatter
- dry-run endpoint or CLI/test-only helper

This can also reuse existing Telegram formatter modules if doing so does not pull in live credentials.

### Step 7 — Tests

Add focused tests before broad UI polish:

```powershell
cd dashboard
.venv\Scripts\python.exe -m pytest tests/test_public.py tests/test_public_insights.py -q
```

Then:

```powershell
cd dashboard
.venv\Scripts\python.exe -m pytest tests/ -q
```

---

## File Change Summary

| File | Change |
|------|--------|
| `dashboard/app/public.py` | New public serializer/service/insight helper |
| `dashboard/app/routers/public.py` | New unauthenticated public API |
| `dashboard/app/main.py` | Include public router |
| `dashboard/app/routers/pages.py` | Public home and match SEO routes |
| `dashboard/templates/public.html` | Public acquisition home |
| `dashboard/templates/ipl_today.html` | IPL prediction today page |
| `dashboard/templates/match_public.html` | Public match detail page |
| `dashboard/static/js/dashboard.js` | Optional public polling helper |
| `dashboard/app/telegram_distribution.py` | Optional P2 dry-run Telegram distribution |
| `dashboard/tests/test_public.py` | Endpoint/page tests |
| `dashboard/tests/test_public_insights.py` | Pure serializer/insight tests |
| `dashboard/tests/test_telegram_distribution.py` | P2 Telegram event tests |

---

## Validation Commands

### Run Local Server

```powershell
cd dashboard
$env:PROJECT_ROOT = (Split-Path -Parent $PWD)
$env:PYTHONPATH = "$env:PROJECT_ROOT\src;$PWD"
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### Public Smoke Checks

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/api/public/matches
Invoke-RestMethod http://127.0.0.1:8000/api/public/ipl-today
Invoke-WebRequest http://127.0.0.1:8000/
Invoke-WebRequest http://127.0.0.1:8000/ipl-prediction-today
```

### Redaction Check

```powershell
$json = Invoke-RestMethod http://127.0.0.1:8000/api/public/matches | ConvertTo-Json -Depth 20
$forbidden = @("monte_carlo","odm","blend","features","pred_state","history","chart_history","commentary","ml_prob","mc_prob","ml_weight","mc_weight")
foreach ($key in $forbidden) {
  if ($json -match "`"$key`"") { throw "Forbidden key leaked: $key" }
}
```

### Tests

```powershell
cd dashboard
.venv\Scripts\python.exe -m pytest tests/test_public.py tests/test_public_insights.py -q
.venv\Scripts\python.exe -m pytest tests/ -q
```

---

## Execution Order

```text
1. Add public serializer/service
2. Add public API router
3. Register router
4. Add public page routes
5. Add public templates
6. Add tests for API/page/serializer redaction
7. Add insight copy tests
8. Add optional public page polling
9. Add Telegram dry-run distribution
10. Run full dashboard test suite
```

---

## MVP Boundary

MVP is complete when:

- `/` is public and useful
- `/ipl-prediction-today` renders without auth
- `/match/{slug}` renders for active/discovered matches
- `/api/public/*` returns redacted lite data without auth
- public payloads include one model insight
- premium fields do not leak
- existing authenticated dashboard still passes tests

Telegram and hard paid-plan enforcement are valuable P2 work. They should not block the first public acquisition launch.
