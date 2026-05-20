# Feature Specification: Telegram Public Signals Agent

**Feature Branch**: `015-telegram-public-signals`  
**Created**: 2026-05-01  
**Status**: Draft  
**Input**: Build a CrickZen IPL Telegram channel workflow that posts free pre-match and live win probability updates, records accuracy openly, and converts serious users into the production dashboard.

## Definitions

- **Signal agent**: An operator-facing workflow that turns IPL v6 model/dashboard state into public Telegram post drafts, tracks what was published, and prepares honest review copy after the match.
- **Public signal**: A Telegram post that states a match phase, model favorite, confidence band, key reason for change, and CTA to the CrickZen dashboard without giving stake sizing or guaranteed betting advice.
- **Accuracy tracker**: A public-facing record of each match prediction with Date, Match, Pre-match favorite, Final result, Confidence, and What changed.
- **Lifecycle post**: One of the scheduled match updates: pre-match, toss, powerplay, 10-over/mid-innings, innings break, chase midpoint, final review.
- **Attention layer**: The public habit-forming channel where cricket fans see timely model probability updates before they are asked to use or pay for the deeper dashboard.

## Current State

### What Already Exists

- IPL v6 model artifacts and live prediction flow are available in this repo through `models/ipl_v6` and `data/ipl_feature_store_v3`.
- Telegram ledger infrastructure exists under `src/bbl_pipeline/telegram/`, including config, bot client, message formatting, storage, and tests.
- `specs/006-telegram-prediction-ledger` defines immutable manual Telegram prediction posting.
- `specs/013-public-dashboard-growth` defines public pages, lite APIs, Telegram dry-run distribution, and upgrade CTAs.
- The dashboard is planned as the production surface for public acquisition and deeper paid usage.

### What Is Missing

- No explicit agent brief for operating a public IPL prediction channel.
- No public trust-building posting cadence for same-day matches.
- No match lifecycle templates for pre-toss, toss, powerplay, mid-match, innings break, chase midpoint, and final review.
- No accuracy tracker designed for Telegram/channel use.
- No operational guide for creating the public Telegram channel, pinning "How this channel works", and safely sharing into cricket/fantasy communities.
- No clear CTA rules tying free Telegram updates to the dashboard without overselling betting.

---

## User Scenarios & Testing

### User Story 1 - Launch Public IPL Channel (Priority: P1)

As the CrickZen operator, I want to create a public Telegram channel with clear positioning and a pinned explanation, so that new users immediately understand that this is a transparent IPL probability feed.

**Why this priority**: The channel itself is the trust surface. The first hour should create a credible public home before any selling.

**Independent Test**: A new user can open the Telegram channel, read the bio and pinned post, and understand what is posted, when updates appear, what confidence means, and where the dashboard CTA leads.

**Acceptance Scenarios**:

1. **Given** the channel exists, **When** a user opens its profile, **Then** the bio reads: "Ball-by-ball IPL win probability powered by ML. Free pre-match and live prediction updates. Built by CrickZen."
2. **Given** the channel has no context, **When** the operator pins "How this channel works", **Then** the pinned post explains lifecycle updates, confidence bands, honest final reviews, and dashboard CTAs.
3. **Given** the operator shares the channel in cricket or fantasy groups, **When** the post is prepared, **Then** it is non-spammy, follows group rules, and invites users to follow free model updates.

---

### User Story 2 - Publish Same-Day Pre-Match Signal (Priority: P1)

As the operator, I want the agent to draft a same-day IPL pre-match post from the latest IPL v6/dashboard probability, so that RR vs DC or CSK vs MI can be publicly timestamped before toss.

**Why this priority**: Pre-match public proof is the trust anchor. It shows the model call before match conditions and market narrative shift.

**Independent Test**: Given a verified fixture and model probability, the agent generates a Telegram-ready pre-match post with favorite, confidence, model probability, caveats, and dashboard CTA.

**Acceptance Scenarios**:

1. **Given** today's fixture is verified as RR vs DC, **When** the operator requests a pre-match signal, **Then** the agent drafts a public post before toss using the current IPL v6 favorite and confidence band.
2. **Given** CSK vs MI is an upcoming fixture, **When** the operator requests a pre-toss prediction, **Then** the agent drafts a post explicitly marked "before toss" and avoids assuming toss or XI information.
3. **Given** model state is stale or fixture data is unverified, **When** a post is requested, **Then** the agent blocks live posting and asks the operator to refresh the dashboard/predictor first.

---

### User Story 3 - Run Match Lifecycle Updates (Priority: P1)

As the operator, I want the agent to guide public posts at toss, 6 overs, 10 overs, innings break, chase midpoint, and final review, so that the channel owns the IPL prediction attention layer during the match.

**Why this priority**: Live attention compounds when updates are timely, disciplined, and visibly accountable.

**Independent Test**: For a live match state sequence, the agent produces one post per lifecycle milestone, explains what changed, and suppresses duplicate unchanged updates.

**Acceptance Scenarios**:

1. **Given** toss information is available, **When** the toss update is requested, **Then** the post states toss winner, decision, and whether the model favorite changed from pre-match.
2. **Given** six overs are complete, **When** the powerplay update is requested, **Then** the post states current favorite, probability movement, score context, and one reason for movement.
3. **Given** ten overs or innings midpoint is reached, **When** the mid-innings update is requested, **Then** the post states whether the batting side is ahead or behind model par.
4. **Given** innings break occurs, **When** the update is requested, **Then** the post states target, chase favorite, and confidence band.
5. **Given** chase midpoint is reached, **When** the update is requested, **Then** the post explains chase pressure or control without excessive precision.
6. **Given** the match finishes, **When** final review is requested, **Then** the post states prediction result, what the model got right/wrong, and one concrete lesson.

---

### User Story 4 - Maintain Public Accuracy Tracker (Priority: P1)

As a potential dashboard user, I want to see a simple public accuracy tracker, so that I can judge CrickZen by recorded outcomes rather than claims.

**Why this priority**: Trust comes from public accountability, not one-off winning screenshots.

**Independent Test**: After every final review, the tracker has one updated row with Date, Match, Pre-match favorite, Final result, Confidence, and What changed.

**Acceptance Scenarios**:

1. **Given** a pre-match signal has been posted, **When** the match ends, **Then** the accuracy tracker row is updated with the final result.
2. **Given** the model favorite was wrong, **When** the final review is generated, **Then** the "What changed" field honestly describes the match factor that broke the pre-match view.
3. **Given** the model favorite was right, **When** the row is published, **Then** it records the win without overstating certainty or implying guaranteed future results.

---

### User Story 5 - Convert Serious Users to Dashboard (Priority: P2)

As a serious cricket user, I want Telegram posts to link me into a live dashboard with deeper model context, so that I can inspect probability movement, projections, and premium detail after seeing public proof.

**Why this priority**: The channel should not hard-sell betting. It should create repeated evidence, then route high-intent users to deeper platform usage.

**Independent Test**: Every eligible public post includes one restrained CTA to the production dashboard or public match page, and public pages preserve a clear upgrade path.

**Acceptance Scenarios**:

1. **Given** the production dashboard is deployed, **When** a lifecycle post is generated, **Then** it includes a link to the public match page or dashboard CTA.
2. **Given** a user clicks from Telegram, **When** they land on the public page, **Then** they see the same match and a clear path to the full dashboard.
3. **Given** Telegram is used for acquisition, **When** copy is generated, **Then** it avoids stake sizing, guaranteed returns, and "sell betting today" language.

---

## Edge Cases

- Fixture mismatch: If RR vs DC or CSK vs MI is not confirmed for the requested date, the agent must not invent the matchup.
- Stale model output: If the latest prediction timestamp is too old for the intended post, the agent must require a refresh before publishing.
- Toss changes context: If toss materially moves probability, the toss update must say the pre-match view changed instead of pretending the original call was always obvious.
- Rain/DLS/reduced overs: Posts must mark the match as reduced-over or DLS-affected and avoid comparing directly with normal 20-over expectations.
- Missing score/probability: The agent may draft a "waiting for model state" internal note but must not publish a fake probability.
- Duplicate milestones: The same 6-over or 10-over update must not be posted twice unless the operator explicitly posts a correction.
- Wrong public post: Corrections are separate follow-up posts; the agent must not edit/delete earlier public proof.
- Dashboard outage: Telegram posts can continue with tracker-only CTA removed or replaced by a neutral "dashboard temporarily unavailable" note.
- Group sharing: The operator must follow community rules and avoid unsolicited repeated promotion.
- Legal/product risk: All copy must present analytics and probabilities, not financial advice or guaranteed betting outcomes.

## Requirements

### Functional Requirements

- **FR-001**: The system MUST provide a CrickZen Telegram signal agent brief in the repo's agent framework.
- **FR-002**: The agent MUST support a first-hour launch checklist: create channel, set bio, pin "How this channel works", publish first pre-match post, share in three relevant groups, run lifecycle updates, and publish final review.
- **FR-003**: The agent MUST generate Telegram-ready post drafts for pre-match, toss, powerplay, 10-over/mid-innings, innings break, chase midpoint, final review, and accuracy tracker updates.
- **FR-004**: The pre-match post MUST include match, timestamp context, favorite, rounded win probability or confidence band, one caveat, and CTA when dashboard URL is available.
- **FR-005**: Toss updates MUST compare against the pre-match favorite and state what changed.
- **FR-006**: Powerplay and mid-match updates MUST include score context, current favorite, probability movement, and a short reason.
- **FR-007**: Final reviews MUST include whether the pre-match favorite won, what changed, and what the model learned or missed.
- **FR-008**: The accuracy tracker MUST store Date, Match, Pre-match favorite, Final result, Confidence, and What changed.
- **FR-009**: The agent MUST refuse to draft publish-ready posts from unverified fixtures, stale model state, or missing probability data.
- **FR-010**: The agent MUST maintain a no-cherry-picking rule: every pre-match public signal must receive a final review and tracker row.
- **FR-011**: The agent MUST keep Telegram copy restrained, public-proof oriented, and free of stake sizing, guaranteed betting advice, or exaggerated certainty.
- **FR-012**: The agent MUST include dashboard CTA copy only after the prediction value is stated, and the CTA must not dominate the post.
- **FR-013**: The agent MUST support manual operator approval before any live Telegram publish.
- **FR-014**: The agent MUST be compatible with the existing Telegram ledger modules and public dashboard growth plan.
- **FR-015**: The channel setup guide MUST document BotFather token creation, public channel creation, bot admin permissions, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHANNEL_ID`, and safe test posting.

### Key Entities

- **SignalPostDraft**: Draft Telegram message with match, phase, generated text, source timestamp, model probability, CTA URL, and publish readiness.
- **SignalSchedule**: The expected post sequence for a match: pre-match, toss, powerplay, 10-over/mid-innings, innings break, chase midpoint, final review.
- **AccuracyTrackerRow**: Public outcome row with Date, Match, Pre-match favorite, Final result, Confidence, and What changed.
- **ChannelSetupChecklist**: Operator checklist for creating and configuring the Telegram channel.
- **DashboardCTA**: Public or authenticated dashboard link metadata inserted into eligible posts.

## Success Criteria

- **SC-001**: The operator can complete the first-hour channel launch checklist in under 60 minutes.
- **SC-002**: 100% of pre-match posts have a matching final review and accuracy tracker row.
- **SC-003**: Lifecycle posts are generated for at least five match moments: pre-match, toss, powerplay, innings break or chase midpoint, and final review.
- **SC-004**: No public post contains stake sizing, guaranteed return language, or unverified fixture claims.
- **SC-005**: Telegram post drafts can be generated without live bot credentials in tests or dry-run mode.
- **SC-006**: Public CTA links route users to the production public match page or dashboard when configured.
- **SC-007**: A new user can understand how the channel works from the pinned post without needing external explanation.
- **SC-008**: The accuracy tracker remains readable in Telegram and can be copied into a dashboard/table view later without reformatting.

## Assumptions

- The public channel name will use CrickZen branding and IPL probability positioning.
- The first release is operator-approved, not fully automated live posting.
- IPL v6 model and live dashboard state remain the source of prediction truth.
- Telegram is the initial public distribution channel; other social channels are out of scope for this spec.
- The channel is a trust-building analytics surface, not a betting tipster service.

## Dependencies

- Existing Telegram modules in `src/bbl_pipeline/telegram/`.
- Existing Streamlit ledger app and JSONL storage from `specs/006-telegram-prediction-ledger`.
- Public dashboard routes and CTA work from `specs/013-public-dashboard-growth`.
- Production dashboard deployment with a stable public URL.
- Operator-owned Telegram account, BotFather bot, and public channel admin access.

## Out of Scope

- Fully automated posting without human approval.
- Paid subscription billing inside Telegram.
- Multi-channel social distribution beyond Telegram.
- Betting stake recommendations or odds execution.
- Editing or deleting previous public signal posts.
- Claiming model certainty beyond probability/confidence language.
