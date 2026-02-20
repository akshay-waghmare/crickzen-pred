# CrickenZen SaaS Setup Guide

Everything you need to run CrickenZen as a paid subscription service.

---

## Subscriber Lifecycle

```
New customer pays
       │
       ▼
POST /admin/subscribers   ← you create the account
       │
       ▼
Customer logs in → JWT token (60-min TTL, auto-refreshed)
       │
       ▼
Customer views live predictions
       │
   [cancel / non-renewal]
       │
       ▼
PATCH /admin/subscribers/{id}/suspend   ← you suspend the account
```

---

## 1 — Adding a Subscriber

### Via API (recommended)
```bash
# Step 1: get admin token
TOKEN=$(curl -s -X POST https://yourdomain.com/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@yourdomain.com","password":"<ADMIN_PASSWORD>"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Step 2: create account
curl -s -X POST https://yourdomain.com/admin/subscribers \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "customer@example.com",
    "password": "TempPass123!",
    "plan": "monthly"
  }'
```

**Plans available:** `monthly`, `seasonal`, `annual` (stored as metadata; billing is handled externally).

### Via admin dashboard page
Login at `https://yourdomain.com/login` as admin → Subscribers → Add New.

---

## 2 — Suspending a Subscriber

```bash
# Get subscriber ID from list
SUBSCRIBERS=$(curl -s https://yourdomain.com/admin/subscribers \
  -H "Authorization: Bearer $TOKEN")

# Suspend by ID
curl -s -X PATCH https://yourdomain.com/admin/subscribers/42/suspend \
  -H "Authorization: Bearer $TOKEN"
```

Suspended accounts receive a `403 Forbidden` on login with message: `"Account suspended"`.

---

## 3 — Reactivating a Subscriber

```bash
curl -s -X PATCH https://yourdomain.com/admin/subscribers/42/reactivate \
  -H "Authorization: Bearer $TOKEN"
```

---

## 4 — Monetisation Options

### Option A: Gumroad (recommended for solo operators)
1. Create a product on [gumroad.com](https://gumroad.com) (monthly membership).
2. In the Gumroad webhook, call `POST /admin/subscribers` with the buyer's email.
3. On cancellation webhook, call `PATCH /admin/subscribers/{id}/suspend`.

### Option B: Stripe
1. Create a Stripe product + recurring price.
2. Use Stripe Webhooks:
   - `customer.subscription.created` → create subscriber
   - `customer.subscription.deleted` → suspend subscriber
   - `invoice.payment_failed` (after grace) → suspend subscriber

### Option C: Manual (WhatsApp / UPI / bank transfer)
1. Receive payment confirmation.
2. Run the `POST /admin/subscribers` curl command above.
3. Send the subscriber their temporary password by WhatsApp or email.
4. Remind them to change password from profile page.

---

## 5 — Session Management

- JWT tokens expire after **60 minutes** (configurable via `JWT_EXPIRE_MINUTES`).
- Frontend automatically refreshes tokens via `/auth/refresh` before expiry.
- To force-logout all active sessions for a user, suspend and immediately reactivate (this invalidates all outstanding JWTs for that user).

---

## 6 — Welcome Email Template

```
Subject: Your CrickenZen access is ready 🏏

Hi [Name],

Your CrickenZen prediction dashboard is ready.

Login: https://yourdomain.com/login
Email: [their email]
Temporary password: [TempPass123!]

Please change your password after first login.

What you get:
✅ Real-time win probability for every T20 match we cover
✅ Full calibration chain (Raw → Phase → Per-Over → League)
✅ Mobile-friendly dashboard

Questions? Reply to this email.

Cheers,
[Your name]
```

---

## 7 — Database Backup

The subscriber database is a SQLite file at `dashboard/auth.db`.  Add this crontab entry on the server to back up daily:

```bash
# Edit crontab
crontab -e

# Add this line (backs up at 3:00 AM UTC)
0 3 * * * cp /path/to/crickzen-pred/dashboard/auth.db \
  /path/to/backups/auth_$(date +\%Y\%m\%d).db
```

Keep the last 30 days:
```bash
0 4 * * * find /path/to/backups -name "auth_*.db" -mtime +30 -delete
```

---

## 8 — Subscriber Count & Revenue Tracking

```bash
# Count active subscribers
curl -s https://yourdomain.com/admin/subscribers \
  -H "Authorization: Bearer $TOKEN" \
  | python3 -c "
import sys, json
subs = json.load(sys.stdin)
active = [s for s in subs if s['status'] == 'active']
print(f'Active: {len(active)} / Total: {len(subs)}')
"
```

---

## 9 — Changing the Admin Password

1. Update `ADMIN_PASSWORD` in `dashboard/.env`.
2. Restart the server: `docker compose restart dashboard` (or kill & rerun uvicorn locally).
3. The bootstrap admin account is recreated with the new password on next startup (if the account already exists, only the password hash is updated).

---

## Related Docs

- [`dashboard/README.md`](../dashboard/README.md) — Local dev setup
- [`docs/DASHBOARD_DEPLOY.md`](DASHBOARD_DEPLOY.md) — Production server setup
- [`docs/PREDICTOR_INTEGRATION.md`](PREDICTOR_INTEGRATION.md) — Live prediction flow
