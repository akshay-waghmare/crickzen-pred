# Feature Specification: SaaS Prediction Dashboard

**Feature Branch**: `001-saas-prediction-dashboard`  
**Created**: 2026-02-18  
**Status**: Draft  
**Input**: User description: "i wan to create a proper dashboard for this prediction it will be like a streamlit but like a saas and i should be able to sale it , app should be cleaner than streamlit app with only prediction and graph and score features from the streamlit app and it should be very atrractive and user friendly"

---

## Clarifications

### Session 2026-02-18

- Q: What authentication mechanism should the dashboard use to gate access for paying subscribers? → A: Email + password with JWT tokens (signed access token + refresh token rotation)
- Q: What is the deployment target for the SaaS dashboard? → A: Self-hosted VPS (e.g., DigitalOcean / Hetzner) running Docker Compose
- Q: How many concurrent subscribers must the dashboard support without degradation? → A: Up to 50 concurrent users (early SaaS launch target); HTTP polling architecture is acceptable at this scale
- Q: What is the session lifetime / inactivity behaviour? → A: Silent background token refresh — the dashboard silently renews the access token using the refresh token while the tab is open; session expires only after 30-day refresh token lifetime or explicit logout
- Q: Who can configure the dashboard auto-refresh interval? → A: Owner only, server-side — a single fixed value (default 3 seconds) in server config; subscribers have no UI control over it

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Live Match Win Probability View (Priority: P1)

A subscriber opens the dashboard during a live T20 match and immediately sees the current win probability for both teams displayed prominently, alongside the live scorecard and a real-time graph showing how probability has shifted over the course of the match.

**Why this priority**: This is the core value proposition — without real-time win probability and score display, the product has no MVP. All other features build on this.

**Independent Test**: Can be fully tested by pointing the app at a live match JSON state file and verifying the win probability gauge, live score panel, and probability timeline chart all update correctly.

**Acceptance Scenarios**:

1. **Given** the backend predictor is running and writing state to a JSON file, **When** the user opens the dashboard, **Then** they see both teams' win probabilities (as percentages and decimal odds), the live score (runs/wickets/overs), and a probability timeline chart — all without requiring any technical setup from the user.
2. **Given** the match data has been refreshed, **When** the auto-refresh interval elapses, **Then** the dashboard silently updates all panels (score, probabilities, chart) without a full page reload or visible flicker.
3. **Given** a match has ended, **When** the user views the dashboard, **Then** a clear "Match Over" result banner is displayed with the final winner and a complete probability history chart.

---

### User Story 2 - Attractive, Professional UI (Priority: P2)

A potential customer evaluates the product for the first time. The interface looks polished, commercial-grade, and distinctly different from a raw data tool — with a dark cricket-themed design, smooth animations, and clear information hierarchy.

**Why this priority**: Attractiveness and perceived quality are the primary reasons a user chooses to pay over using a free Streamlit prototype. A beautiful UI is a prerequisite for commercial viability.

**Independent Test**: Can be tested by loading any sample match state and confirming the UI meets a visual quality bar: no raw Streamlit widgets visible, branded header, dark theme with accent colors, smooth chart transitions, and mobile-responsive layout.

**Acceptance Scenarios**:

1. **Given** a user visits the dashboard on a desktop browser, **When** the page loads, **Then** the layout presents a branded header, win probability panels with gauge/indicator visuals, a score display, and a chart — all styled consistently with no default Streamlit chrome visible.
2. **Given** a user visits the dashboard on a mobile device, **Then** all key panels (score, probability, chart) are readable and usable without horizontal scrolling.
3. **Given** the probability value changes between refreshes, **When** the gauge updates, **Then** the transition is animated (smooth movement) rather than a hard jump.

---

### User Story 3 - Win Probability Timeline Chart (Priority: P2)

A user wants to understand how the match momentum has shifted by viewing a ball-by-ball win probability graph. The chart clearly marks innings boundaries, phase boundaries (powerplay / middle / death), and key events (wickets, boundaries).

**Why this priority**: The timeline chart is the "WOW" feature that differentiates this from a simple scoreboard. It provides analytical depth that drives engagement and subscription retention.

**Independent Test**: Can be tested independently by feeding a pre-recorded prediction history to the chart component and verifying phase markers, wicket markers, and team-colored probability lines render correctly.

**Acceptance Scenarios**:

1. **Given** a match has at least 6 deliveries recorded, **When** the chart renders, **Then** it shows a continuous probability line for the batting team, with phase boundaries marked (powerplay/middle/death) and the innings 2 start clearly indicated.
2. **Given** a wicket event appears in the history, **When** the chart renders that delivery, **Then** a visual marker (dot or icon) highlights that point on the line.
3. **Given** the match is in the second innings, **When** the chart is displayed, **Then** a secondary reference line or shaded band shows the target and the par score at each over.

---

### User Story 4 - Multi-League & Calibration Selector (Priority: P3)

A power user monitoring a match in a specific league (BBL, SA20, ILT20, WPL, etc.) can select the active league so the dashboard applies the correct league-specific calibration to the displayed probability.

**Why this priority**: Calibration accuracy directly affects trust in the product. Different leagues have different base rates; applying the wrong calibration would show misleading probabilities.

**Independent Test**: Can be tested by switching the league selector and verifying the displayed probability changes to reflect the league calibrator's adjustment (e.g., raw → phase → per-over → league chain).

**Acceptance Scenarios**:

1. **Given** the user selects a specific league from a dropdown, **When** the dashboard loads or refreshes, **Then** the win probability displayed reflects the full calibration chain for that league (raw → phase → per-over → league).
2. **Given** the user selects a league for which no league calibrator exists, **Then** the dashboard falls back to the global T20 model probability and displays a notice indicating that league-specific calibration is unavailable.

---

### User Story 5 - Access Control / Subscription Gate (Priority: P3)

The dashboard enforces a login and subscription check before displaying any prediction data, enabling the owner to sell access to end users.

**Why this priority**: Without access control, the product cannot be monetised. However, the core prediction features must work independently of the auth layer, which is why this is P3.

**Independent Test**: Can be tested independently by attempting to access the dashboard without valid credentials and verifying a login/paywall screen is shown instead of match data.

**Acceptance Scenarios**:

1. **Given** an unauthenticated user visits the dashboard URL, **Then** they are redirected to a login/landing page rather than seeing match data.
2. **Given** a user has an active subscription and valid credentials, **When** they log in, **Then** they are taken directly to the live dashboard with no extra steps.
3. **Given** a user's subscription has expired, **When** they attempt to log in, **Then** they see a clear message explaining their subscription status and a way to renew.

---

### Edge Cases

- What happens when the backend JSON file is missing or stale (older than 60 seconds)? → A "Waiting for live data…" indicator is shown; no errors are exposed to the user.
- What happens if the match is in an innings break? → The score and last-known probability are frozen with an "Innings Break" status label.
- What happens when the probability is exactly 50/50? → Both gauges show 50% and neither team's colour dominates.
- What happens when a user has a very slow network connection? → The dashboard gracefully degrades — charts still render using cached data; only the "last updated" timestamp indicates the data may be delayed.
- What happens when the backend produces a probability outside 0–100%? → The dashboard clamps the value and logs a warning; no broken UI is shown to the user.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The dashboard MUST display real-time win probability for both teams as a percentage and decimal odds, updated from the live prediction backend.
- **FR-002**: The dashboard MUST display the live scorecard including runs, wickets, overs completed, and (for the second innings) target and runs needed.
- **FR-003**: The dashboard MUST render a ball-by-ball win probability timeline chart with phase boundaries (powerplay / middle / death) and wicket markers.
- **FR-004**: The dashboard MUST auto-refresh at a fixed interval set by the owner in server configuration (default: 3 seconds). Subscribers have no UI control over the refresh rate. The interval applies uniformly to all connected sessions.
- **FR-005**: The dashboard MUST support league selection so the correct league-specific calibration chain is applied to displayed probabilities.
- **FR-006**: The dashboard MUST display a current run rate (CRR) and required run rate (RRR) indicator during the second innings.
- **FR-007**: The dashboard MUST display a clear "Match Over" result banner with the winning team when the match concludes.
- **FR-008**: The dashboard MUST be deployable on a self-hosted Linux VPS using Docker Compose. A single `docker compose up` command MUST start all required services (dashboard web server, prediction backend, auth/database). No local software installation is required on the subscriber's side — a standard browser is sufficient.
- **FR-009**: The dashboard MUST authenticate users via email + password. On successful login the server issues a signed JWT access token (short-lived, ≤60 min) and a refresh token (long-lived, ≤30 days, HTTP-only cookie). All subsequent API requests MUST carry the access token in the `Authorization: Bearer` header. The dashboard client MUST silently renew the access token using the refresh token before expiry (proactive refresh when ≤5 min remaining), so a subscriber watching a live match is never interrupted by an expiry prompt. No idle timeout is enforced — the session remains active as long as the tab is open and the refresh token has not expired or been revoked.
- **FR-010**: The dashboard MUST be visually distinct from the existing Streamlit prototype — no default Streamlit widget chrome should be visible to end users.
- **FR-011**: The dashboard MUST render correctly on desktop (1280px+) and mobile (375px+) screen widths.
- **FR-012**: The dashboard MUST show a graceful "Waiting for data" state when the backend has not yet produced a prediction or the JSON state file is stale.
- **FR-013**: The dashboard MUST NOT expose raw model internals, calibration details, or backend file paths to end users.
- **FR-014**: Passwords MUST be stored as bcrypt hashes (cost factor ≥ 12); plaintext passwords MUST never be logged or stored.
- **FR-015**: JWT access tokens MUST be signed with a secret known only to the server (HS256 minimum); the server MUST validate signature, expiry, and issuer on every protected request.
- **FR-016**: Refresh tokens MUST be stored server-side (database or secure cache) and invalidated immediately on logout or subscription expiry. A refresh token MUST only be accepted once (rotation: old token revoked on use, new token issued).
- **FR-017**: The login endpoint MUST enforce rate limiting — no more than 5 failed login attempts per IP per 15-minute window; subsequent attempts within the window MUST return a 429 response.
- **FR-018**: All traffic between clients and the server MUST be over HTTPS (TLS 1.2+); HTTP requests MUST be redirected to HTTPS automatically.

### Key Entities

- **MatchState**: A snapshot of match data at a single point in time — score, wickets, overs, batting/bowling team, current win probability (raw and calibrated), match phase, innings number, target (if 2nd innings), CRR, RRR.
- **PredictionHistory**: An ordered sequence of MatchState entries for the current match, used to render the probability timeline chart.
- **League**: A named T20 competition (BBL, SA20, ILT20, WPL, SSM, etc.) associated with a specific calibration chain.
- **User / Subscriber**: A person who has registered and paid for dashboard access. Has a subscription status (active / expired / trial) and associated league access permissions.
- **Session**: An authenticated user context represented by a short-lived JWT access token (≤60 min) and a long-lived refresh token (≤30 days) stored as an HTTP-only cookie. While the tab is open, the client silently renews the access token when ≤5 minutes remain — the user is never prompted to re-authenticate mid-match. No idle timeout is applied. A session is fully terminated on: (a) explicit logout, (b) refresh token expiry after 30 days, or (c) server-side revocation triggered by subscription expiry or the owner revoking access.

### Deployment & Infrastructure Constraints

- **DC-001**: The application MUST be packaged as a Docker Compose stack. Each logical concern (dashboard frontend/API, prediction backend, database) MUST run as a separate named service.
- **DC-002**: All persistent data (user accounts, refresh tokens, match state history) MUST be stored in a named Docker volume so it survives container restarts.
- **DC-003**: The Compose stack MUST expose only two ports to the public internet: 80 (HTTP → redirect to HTTPS) and 443 (HTTPS). All inter-service communication MUST use the internal Docker network.
- **DC-004**: The prediction backend service (ML model + scraper) MUST be able to restart independently without taking down the dashboard or auth service.
- **DC-005**: The stack MUST include a reverse proxy service (e.g., Nginx or Caddy) responsible for TLS termination, HTTPS redirect, and routing requests to the correct internal service.
- **DC-006**: Environment-specific secrets (JWT signing key, database credentials, TLS certificate paths) MUST be supplied via a `.env` file or Docker secrets — never hard-coded in source files or Docker images.
- **DC-007**: The dashboard API MUST handle at least 50 concurrent subscribers polling at 3-second intervals (≈17 requests/second) without exceeding 80% CPU on a 2-vCPU VPS. HTTP short-polling is the accepted data-delivery mechanism at this scale; WebSockets/SSE are out of scope.
- **DC-008**: The system MUST enforce a hard cap of 50 active authenticated sessions. If the cap is reached, new login attempts MUST receive a clear "capacity reached" message rather than silently failing.
- **DC-009**: The poll interval MUST be a single server-side environment variable (e.g., `POLL_INTERVAL_MS`, default `3000`). Changing it requires a server config update and service restart; no per-user override is exposed via the API or UI.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: First meaningful content (score + probability) is visible within 3 seconds of a user opening a live match page on a standard broadband connection.
- **SC-002**: The probability timeline chart renders the full match history (up to 240 deliveries) without visible lag or dropped frames on a standard laptop browser, with up to 50 concurrent subscribers viewing simultaneously.
- **SC-003**: 90% of first-time users can identify the winning team's current probability without reading any instructions (measured via usability test or session recording).
- **SC-004**: The dashboard auto-refresh successfully updates all displayed values within 5 seconds of the backend writing a new prediction state.
- **SC-005**: Starting from a fresh Linux VPS, the owner can run `docker compose up` and have the dashboard fully accessible to external subscribers within 30 minutes, including TLS certificate provisioning.
- **SC-006**: An unauthenticated request to any prediction data endpoint returns an access-denied response — no match data is leaked to unauthenticated users.
- **SC-007**: The visual design is rated as "professional / commercial quality" (not resembling a data prototype) by at least 3 independent evaluators.
- **SC-008**: A penetration test or manual security review confirms that (a) no prediction data is reachable without a valid JWT, (b) tokens cannot be replayed after logout, and (c) brute-force login is blocked after 5 failed attempts.
