# CrickZen Dashboard Production Deployment

This runbook matches the current production server at `204.12.199.137`.

## What the server looks like today

- Docker and Docker Compose are installed.
- `80/443` are already owned by the shared `victoryline-proxy` Caddy container.
- The live proxy config is mounted from:
  - `/home/administrator/victoryline-monorepo/Caddyfile.prod`
- The existing machine-learning checkout on the server is older and does not yet contain:
  - `dashboard/`
  - `docker-compose.yml`

Because of that, do **not** deploy this repo's default root `docker-compose.yml` on that box. It tries to start another public Caddy and Cloudflare tunnels, which will conflict with the running proxy stack.

## Recommended shape

Run the dashboard container on `127.0.0.1:8000` only, then add a new host block to the existing shared Caddy:

- Suggested public host: `app.crickzen.com`
- Join the dashboard container to the existing Docker network: `victoryline-monorepo_victoryline-network`
- Reverse proxy target from Caddy container: `crickzen-dashboard:8000`

This keeps the dashboard isolated from the existing `crickzen.com` frontend and avoids another `80/443` listener.

## Files added for this deploy path

- `docker-compose.dashboard-prod.yml`
- `dashboard/.env.prod.example`
- `deploy/caddy/app.crickzen.com.caddy`

## Server steps

1. Sync this newer repo state to the server.

   Example:

   ```bash
   rsync -av --delete \
     --exclude .git \
     --exclude .venv \
     --exclude dashboard/node_modules \
     /local/path/machine_learning_bbl_009-odi-mc-predictor/ \
     administrator@204.12.199.137:/home/administrator/projects/machine_learning_bbl/
   ```

2. On the server, create the dashboard env file.

   ```bash
   cd /home/administrator/projects/machine_learning_bbl
   cp dashboard/.env.prod.example dashboard/.env
   ```

3. Edit `dashboard/.env` and set at least:

   ```env
   JWT_SECRET=<strong-random-secret>
   DOMAIN=app.crickzen.com
   ADMIN_EMAIL=<your-admin-email>
   ADMIN_PASSWORD=<strong-admin-password>
   AUTO_PREDICTIONS_ENABLED=true
   AUTO_LEAGUE_KEY=IPL
   AUTO_TIMEZONE=Asia/Kolkata
   ```

4. Build and start only the dashboard service.

   ```bash
   cd /home/administrator/projects/machine_learning_bbl
   docker compose -f docker-compose.dashboard-prod.yml up -d --build
   ```

5. Verify the container locally on the host.

   ```bash
   curl -f http://127.0.0.1:8000/health
   docker ps --filter name=crickzen-dashboard
   docker logs --tail 100 crickzen-dashboard
   ```

6. Add the new Caddy host block to the shared proxy config.

   File:

   ```text
   /home/administrator/victoryline-monorepo/Caddyfile.prod
   ```

   Add the contents of `deploy/caddy/app.crickzen.com.caddy`.

   The dashboard compose file already joins the existing `victoryline-monorepo_victoryline-network`, so Caddy can reach the service by container name.

7. Reload the shared Caddy container.

   ```bash
   docker exec victoryline-proxy caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile
   ```

8. Verify externally.

   ```bash
   curl -I https://app.crickzen.com/health
   curl -I https://app.crickzen.com/dashboard
   ```

## Known production failure mode: dashboard healthy, live prediction frozen

Two separate things can make prod look "up" while the match prediction appears stopped:

1. **Dashboard restart kills predictors.** On FastAPI shutdown, `dashboard/app/main.py`
   calls `PredictionManager.cleanup_all()`, which stops every child
   `crex_live_predictor` subprocess. The web app can come back quickly while the live
   predictor is still gone, and the scheduler must rediscover/start it again.
2. **Predictor hang leaves a stale live card.** A child predictor can stop updating its
   JSON even while the dashboard container still answers `/health`. In that state the
   site can show an old score until the stale-runner cleanup path clears it.

### What to set on prod

Add these to `dashboard/.env`:

```env
STALE_RUNNING_MATCH_MINUTES=10
PUBLIC_MATCH_STALE_SECONDS=300
AUTO_DISCOVERY_INTERVAL_SECONDS=60
```

This keeps the public site from presenting a frozen score as live for long, while still
giving the scheduler a chance to restart the match automatically after stale cleanup.

## Current prod artifact reality

On the current `204.12.199.137` server, the checked-out model artifacts available to the
dashboard are:

- `models/ipl_v6`
- `data/ipl_feature_store_v3`

The newer dashboard default of `models/ipl_v14_pitch_features` plus
`data/ipl_feature_store_v9` will not work on this host until those artifacts are copied
to prod. If the dashboard is deployed with missing model/feature-store paths, the live
predictor falls back to scraper-only mode and may never emit the JSON state needed by the
public dashboard.

## DNS requirement

Before reloading Caddy, create an `A` record for `app.crickzen.com` pointing to `204.12.199.137`.

## Telegram and public-signals follow-up

Once the dashboard is live, use `https://app.crickzen.com` as the base URL for:

- public match pages
- Telegram CTA links
- final review timeline links

## Why this path

- No `80/443` conflict with the existing proxy.
- Dashboard stays private on localhost unless Caddy exposes it.
- Reuses the existing TLS/certificate flow already active on the server.
- Keeps the current `crickzen.com` frontend untouched while the dashboard ships on its own host.
