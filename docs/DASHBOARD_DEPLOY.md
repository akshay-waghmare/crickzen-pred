# Dashboard — Production Deployment Guide

This guide covers deploying the CrickenZen Prediction Dashboard on a VPS using Docker Compose and Caddy for automatic HTTPS.

---

## Server Requirements

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| CPU | 1 vCPU | 2 vCPU |
| RAM | 1 GB | 2 GB |
| Disk | 10 GB | 20 GB (model + data) |
| OS | Ubuntu 22.04+ | Ubuntu 24.04 LTS |

Software required: **Docker 24+**, **Docker Compose v2**, **Git**

---

## 1 — Clone & Configure

```bash
git clone https://github.com/akshay-waghmare/crickzen-pred.git
cd crickzen-pred

# Copy and fill in secrets
cp dashboard/.env.example dashboard/.env
nano dashboard/.env
```

Required values in `.env`:
```dotenv
JWT_SECRET=<openssl rand -hex 32>
ADMIN_EMAIL=admin@yourdomain.com
ADMIN_PASSWORD=<strong-password>
STATE_FILE=../data/live_state.json
DATABASE_URL=sqlite:///./auth.db
```

---

## 2 — Build CSS (one-time)

```bash
cd dashboard
npm install
npm run build:css
cd ..
```

---

## 3 — Docker Compose

The repo ships with `docker-compose.yml` for the dashboard and `docker-compose.caddy.yml` for HTTPS.

### Start everything
```bash
docker compose up -d          # dashboard + predictor
docker compose -f docker-compose.caddy.yml up -d   # Caddy reverse proxy
```

### Check logs
```bash
docker compose logs -f dashboard
docker compose logs -f caddy
```

### Stop
```bash
docker compose down
```

---

## 4 — Caddy (HTTPS)

Edit `Caddyfile` to set your domain:
```
yourdomain.com {
    reverse_proxy dashboard:8000
}
```

Caddy will automatically obtain and renew a Let's Encrypt certificate.  
Make sure **ports 80 and 443** are open in your firewall:

```bash
ufw allow 80/tcp
ufw allow 443/tcp
```

---

## 5 — Subscriber Management (Production)

### Add a subscriber
```bash
# Get admin token first
TOKEN=$(curl -s -X POST https://yourdomain.com/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@yourdomain.com","password":"<ADMIN_PASSWORD>"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Create subscriber
curl -s -X POST https://yourdomain.com/admin/subscribers \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"email":"newuser@example.com","password":"TempPass1!","plan":"monthly"}'
```

### Suspend a subscriber
```bash
curl -s -X PATCH https://yourdomain.com/admin/subscribers/<USER_ID>/suspend \
  -H "Authorization: Bearer $TOKEN"
```

### Reactivate a subscriber
```bash
curl -s -X PATCH https://yourdomain.com/admin/subscribers/<USER_ID>/reactivate \
  -H "Authorization: Bearer $TOKEN"
```

### List all subscribers
```bash
curl -s https://yourdomain.com/admin/subscribers \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

---

## 6 — Updating the Deployment

```bash
git pull origin main
docker compose build dashboard
docker compose up -d dashboard
```

---

## 7 — Security Checklist

- [ ] Change `ADMIN_PASSWORD` from default before first deploy
- [ ] Set `JWT_SECRET` to a random 32+ byte hex string (`openssl rand -hex 32`)
- [ ] Set `CORS_ORIGINS` to your domain (not `*`) in production
- [ ] Enable firewall — only ports 22, 80, 443 open
- [ ] Use HTTPS (Caddy handles this automatically)
- [ ] Rotate `JWT_SECRET` if compromised (all sessions invalidated)
- [ ] Back up `dashboard/auth.db` daily (see SaaS setup guide)

---

## 8 — Monitoring

```bash
# Health endpoint
curl -s https://yourdomain.com/health

# Container resource usage
docker stats --no-stream

# Tail dashboard logs
docker compose logs -f --tail=100 dashboard

# Check DB size
du -sh dashboard/auth.db
```

---

## 9 — Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `502 Bad Gateway` | Dashboard container not running | `docker compose up -d dashboard` |
| `{"detail":"Not authenticated"}` | JWT expired or missing | Re-login to get fresh token |
| Stale predictions on screen | Predictor stopped | Restart predictor command |
| `_fill_dtype` error | scikit-learn 1.8 incompatibility | `pip install scikit-learn==1.7.2` |
| CSS not loading | Tailwind not built | `cd dashboard && npm run build:css` |

---

## Related Docs

- [`dashboard/README.md`](../dashboard/README.md) — Local dev setup
- [`docs/PREDICTOR_INTEGRATION.md`](PREDICTOR_INTEGRATION.md) — How predictor feeds the dashboard
- [`docs/SAAS_SETUP.md`](SAAS_SETUP.md) — Subscriber lifecycle & monetisation
