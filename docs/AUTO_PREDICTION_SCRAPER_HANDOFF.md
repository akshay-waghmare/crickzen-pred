# Automatic Prediction and Scraper Handoff

Updated: 2026-07-21

The automatic prediction scheduler is downstream of the scraper's bounded live slate. It must not independently choose a different set of CREX cards when the scraper already owns selection and browser capacity.

## Contract

- Scraper endpoint: `GET http://localhost:5000/prediction-candidates`.
- Dashboard setting on the host: `AUTO_SCRAPER_URL=http://127.0.0.1:5000`.
- Dashboard setting in Docker: `AUTO_SCRAPER_URL=http://host.docker.internal:5000`.
- `AUTO_LEAGUE_KEYS=ALL` enables all configured model families; `AUTO_EXCLUDE_LEAGUES=IPL` excludes IPL from this local slate.
- Scheduler source is `scraper:selected` when the endpoint returns candidates; CREX discovery remains a fallback only.
- The service account is exempt from `MAX_USER_MATCHES`; `MAX_TOTAL_MATCHES` remains enforced.

## Why this exists

The scraper's five selected matches and CREX HTML discovery are not the same slate. HTML discovery can expose only two matches, or a larger and different set, while the scraper is actively covering five. Using the scraper endpoint makes prediction selection and scraper selection identical.

## Format fallback

Generic URL classification covers T20/premier-league/The Hundred and ODI/one-day/CWC League/World Cup League URLs, routing to the combined gender-aware T20 or ODI model family.

## Rebuild requirement

The dashboard runs in the separate `crickenzen-dashboard` container. Source edits in the model repository do not affect the running process until the dashboard image is rebuilt and the container recreated:

```powershell
docker compose up -d --build dashboard
```

The local launcher may report the dashboard as healthy without replacing an old image, so verify the running container image and then verify the public feed.

## Acceptance check

For the current selected slate:

```powershell
$selected = (Invoke-RestMethod http://localhost:5000/prediction-candidates).count
$public = Invoke-RestMethod http://127.0.0.1:8000/api/public/matches
$models = @($public.matches | Where-Object model_label).Count
```

Accept only when `$selected -eq $models`, every row has a fresh `updated_at`, and each row's frontend `/match-intelligence/{slug}` route returns HTTP 200.
