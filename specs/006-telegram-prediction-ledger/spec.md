# Feature Specification: Telegram Prediction Ledger

**Feature Branch**: `006-telegram-prediction-ledger`  
**Created**: 2026-01-27  
**Status**: Draft  
**Input**: User description: "Create a system that generates a public, immutable, timestamped ledger of sports predictions by posting structured messages to a Telegram channel."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Post Pre-Match Prediction (Priority: P1)

A user has completed a pre-match analysis using the model and wants to create a verifiable public record of their prediction before the match begins. They click a button in the Streamlit interface, fill out a modal with match details and model predictions, and post it to the Telegram channel where it becomes an immutable, timestamped record.

**Why this priority**: This is the core value proposition - creating verifiable, timestamped predictions that cannot be edited or deleted after posting.

**Independent Test**: Can be fully tested by creating a Telegram bot, displaying a button in Streamlit, capturing user input, formatting a message, and posting it to Telegram. Delivers immediate value as a standalone prediction logger.

**Acceptance Scenarios**:

1. **Given** a user is viewing the Streamlit interface, **When** they click "Post Pre-Match Prediction" button, **Then** a modal appears with all required fields (Match ID, League, Team A, Team B, Selection, Model Probability, Market Odds, Model Edge)
2. **Given** the user has filled all required fields in the modal, **When** they click "Submit", **Then** a formatted message is posted to the Telegram channel with the exact template structure
3. **Given** a message has been posted to Telegram, **When** viewing the channel, **Then** the message displays the Telegram timestamp and cannot be edited or deleted
4. **Given** the user submits a prediction, **When** all fields are complete, **Then** the message includes: Match ID, League, Team names, Selection (BACK/LAY), Model probability, Market odds, Model edge, and "Pre-Match Prediction" status label

---

### User Story 2 - Post Match Start Context (Priority: P2)

When the match begins and the user starts their live predictor (e.g., CREX), they want to log the actual match conditions (toss winner, toss decision) as a separate immutable record. This provides context for how match conditions may have affected the pre-match prediction.

**Why this priority**: Adds important context for prediction verification, but the core prediction value is already delivered by P1. This enhances transparency but isn't required for basic prediction logging.

**Independent Test**: Can be tested by adding a second button and modal that captures toss information and posts a separate message. Delivers value independently by documenting match start conditions.

**Acceptance Scenarios**:

1. **Given** a match has started, **When** the user clicks "Post Match Start Info" button, **Then** a modal appears with fields for Match ID, Team A, Team B, Toss Winner, Toss Decision, and Model Pre-Match Probability
2. **Given** the user has filled all match start fields, **When** they click "Submit", **Then** a new Telegram message is posted with the "Match Start Update" template
3. **Given** match start info is posted, **When** viewing the Telegram channel, **Then** the message includes toss details and references the pre-match model probability without modifying the original prediction post

---

### User Story 3 - Post Match Result (Priority: P3)

After the match concludes, the user wants to post the final result and document whether their model prediction was correct. This creates a complete prediction-to-outcome record chain.

**Why this priority**: Nice-to-have for completing the narrative, but not essential for the core value of creating verifiable predictions. Users can manually verify results from other sources.

**Independent Test**: Can be tested by adding a third button that captures match outcome and posts a result message linking back to the original prediction.

**Acceptance Scenarios**:

1. **Given** a match has concluded, **When** the user clicks "Post Match Result" button, **Then** a modal appears with fields for Match ID and Winning Team
2. **Given** the user has entered the match result, **When** they click "Submit", **Then** a Telegram message is posted showing the winner and whether the model call was correct/incorrect
3. **Given** a result message is posted, **When** viewing the Telegram channel, **Then** the message includes the winning team and states whether the model prediction (BACK/LAY at specified probability) was correct

---

### Edge Cases

- What happens when the user tries to post a pre-match prediction with missing required fields? → System must prevent submission and highlight incomplete fields
- What happens when the Telegram API fails to post a message? → System must display an error to the user and NOT record the prediction as posted (append-only storage only records successful posts)
- What happens when the user tries to post a Match Start or Result before posting a Pre-Match Prediction? → System should allow it (no strict ordering enforced) but the Match ID serves as the linking identifier
- What happens when the user posts duplicate predictions for the same Match ID? → System allows it (user responsibility to manage; append-only means no prevention of duplicates)
- What happens when the user closes the modal without submitting? → No action taken, no data stored, no Telegram message posted
- What happens when network connectivity is lost during submission? → System must provide clear error feedback and not create partial records

## Requirements *(mandatory)*

### Functional Requirements

**User Interface**

- **FR-001**: System MUST provide a "Post Pre-Match Prediction" button in the Streamlit interface
- **FR-002**: System MUST provide a "Post Match Start Info" button in the Streamlit interface
- **FR-003**: System MUST provide a "Post Match Result" button in the Streamlit interface (optional feature)
- **FR-004**: System MUST display a modal form when any posting button is clicked
- **FR-005**: All fields in each modal MUST be marked as required and validated before submission
- **FR-006**: System MUST prevent submission of incomplete forms and highlight missing fields

**Pre-Match Prediction Requirements**

- **FR-007**: Pre-Match Prediction modal MUST capture: Match ID (string), League (string), Team A (string), Team B (string), Selection (enum: BACK or LAY), Model Win Probability (percentage), Market Odds (decimal), Model Edge (percentage)
- **FR-008**: System MUST format pre-match predictions using the exact template structure: Match ID, League, Match (teams), Model Probability, Market Odds, Position (BACK/LAY + team), Model Edge, Status (Pre-Match Prediction)
- **FR-009**: Pre-match prediction messages MUST include "Pre-Match Prediction" as the status label

**Match Start Context Requirements**

- **FR-010**: Match Start modal MUST capture: Match ID (string), Team A (string), Team B (string), Toss Winner (string), Toss Decision (enum: Bat or Bowl), Model Pre-Match Probability (percentage, reference only)
- **FR-011**: System MUST format match start messages using the exact template structure: Match ID, Match Start Update (Toss winner and decision), Model (Pre-Match probability), Status (Match Started)
- **FR-012**: Match start messages MUST include "Match Started" as the status label
- **FR-013**: Match start messages MUST NOT modify or reference editing of earlier pre-match prediction posts

**Post-Match Result Requirements**

- **FR-014**: Match Result modal MUST capture: Match ID (string), Winning Team (string)
- **FR-015**: System MUST format result messages using the exact template structure: Match ID, Result (Winner), Model Call (Correct/Incorrect with original BACK/LAY and probability)
- **FR-016**: System MUST determine correctness by comparing the winning team to the original prediction selection

**Telegram Integration**

- **FR-017**: System MUST post all messages to a single configured Telegram channel via Telegram Bot API
- **FR-018**: System MUST NOT allow editing or deleting of posted Telegram messages
- **FR-019**: System MUST rely on Telegram's native timestamp as the authoritative time record
- **FR-020**: Posted messages MUST contain no explanations, commentary, emojis, hype, betting instructions, stake sizing, or external links
- **FR-021**: Posted messages MUST contain only structured prediction data as specified in the templates

**Data Storage**

- **FR-022**: System MUST maintain append-only local storage of successfully posted predictions
- **FR-023**: Local storage MUST record: Telegram message ID, timestamp of post, all prediction fields, post type (pre-match/start/result)
- **FR-024**: System MUST NOT allow modification or deletion of stored prediction records

**User Experience Constraints**

- **FR-025**: All posting actions MUST be manual (human-initiated button clicks only)
- **FR-026**: System MUST NOT implement auto-posting, scheduling, or automated prediction generation
- **FR-027**: System MUST provide clear success/failure feedback after each posting attempt

### Key Entities

- **Prediction Record**: Represents a pre-match prediction with attributes: match_id, league, team_a, team_b, selection_type (BACK/LAY), selected_team, model_probability, market_odds, model_edge, telegram_message_id, telegram_timestamp, post_type ("pre_match")

- **Match Start Record**: Represents match start context with attributes: match_id, team_a, team_b, toss_winner, toss_decision (Bat/Bowl), model_prematch_probability, telegram_message_id, telegram_timestamp, post_type ("match_start")

- **Result Record**: Represents match outcome with attributes: match_id, winning_team, model_call_correct (boolean), original_selection_type, original_probability, telegram_message_id, telegram_timestamp, post_type ("result")

- **Telegram Message**: Represents a posted message with attributes: message_id (from Telegram API), channel_id, timestamp (from Telegram), content (formatted text), post_type

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can complete posting of a pre-match prediction in under 60 seconds from button click to Telegram confirmation
- **SC-002**: 100% of successfully posted messages are immutable (cannot be edited or deleted via the system)
- **SC-003**: 100% of posted messages display Telegram's native timestamp for verification
- **SC-004**: System successfully posts predictions to Telegram with 99%+ success rate under normal network conditions
- **SC-005**: All posted messages strictly follow the defined template structure with zero formatting deviations
- **SC-006**: Local append-only storage maintains perfect consistency with Telegram channel (all successful posts are recorded, no phantom records)

## Assumptions *(mandatory)*

### Technical Assumptions

1. **Telegram Bot Setup**: User has created a Telegram bot via BotFather and obtained a bot token
2. **Telegram Channel**: User has created a Telegram channel and added the bot as an administrator with post permissions
3. **Network Connectivity**: System assumes stable internet connection for Telegram API calls
4. **Streamlit Environment**: System runs within the existing Streamlit application framework
5. **Python Environment**: Python 3.8+ with ability to install Telegram Bot API library (e.g., python-telegram-bot)
6. **Local Storage**: System has file system write access for append-only storage (JSON or CSV format)

### Business Assumptions

1. **Single Channel**: All predictions are posted to one Telegram channel (no multi-channel support)
2. **Manual Operation**: User is responsible for timely posting (no SLAs on posting speed)
3. **Data Entry**: User manually enters all prediction data (no automation from live predictor output)
4. **No Editing**: Once posted, predictions cannot be corrected even if user made a data entry error (append-only principle)
5. **Public Channel**: The Telegram channel is assumed to be public or semi-public for transparency
6. **No User Comments**: The Telegram channel does not support user comments or replies (bot posts only)

### Scope Assumptions

1. **No Live Integration**: This system does NOT auto-populate fields from the live predictor (CREX) - user copies data manually
2. **No Odds Fetching**: Market odds are manually entered, not fetched from betting APIs
3. **No Analytics**: No dashboard, statistics, or performance tracking within this system
4. **No Notifications**: System does not send alerts or notifications to users or subscribers
5. **No Authentication**: No user login or multi-user support (single operator assumed)
6. **No Result Verification**: System does not auto-verify match results from external sources

## Out of Scope *(mandatory)*

The following are explicitly **NOT** included in this feature:

1. **Automated Posting**: No scheduled posts, auto-posting on match start, or triggered posts
2. **Odds Integration**: No live odds fetching from betting APIs or odds comparison
3. **Multi-Channel Support**: No posting to multiple Telegram channels or other platforms (Twitter, Discord, etc.)
4. **User Engagement Features**: No polls, comments, reactions, or subscriber interactions
5. **Analytics Dashboard**: No web-based performance tracking, win/loss statistics, or charts
6. **Monetization**: No payment processing, subscription management, or tipster services
7. **Live Updates**: No in-play prediction updates or ball-by-ball commentary
8. **Result Automation**: No automatic result verification from Cricsheet or other data sources
9. **Edit/Delete Functionality**: No administrative override to edit or delete posted messages (strictly immutable)
10. **Multi-User Support**: No user roles, permissions, or multiple operator support
11. **Mobile App**: No native mobile application or responsive mobile-optimized UI
12. **Export Features**: No PDF reports, CSV exports, or data download capabilities
13. **Historical Search**: No search interface or filtering of past predictions within the system
14. **Match Scheduling**: No integration with match calendars or fixture lists

## Dependencies *(optional)*

### External Dependencies

1. **Telegram Bot API**: System depends on Telegram Bot API availability and stability
2. **Telegram Channel**: Requires pre-existing Telegram channel with bot administrator access
3. **Network Connectivity**: Requires internet connection for Telegram API communication

### Internal Dependencies

1. **Existing Streamlit App**: Feature integrates into the existing `src/bbl_pipeline/app/` Streamlit application
2. **Python Environment**: Depends on existing Python environment with package management (pip/poetry)
3. **Configuration System**: May depend on existing config management for storing Telegram bot token and channel ID

### Assumptions About Dependencies

1. Telegram Bot API maintains backwards compatibility and does not deprecate posting endpoints
2. Streamlit framework supports modal dialogs or equivalent UI patterns for form capture
3. No rate limiting issues from Telegram API for the expected posting frequency (typically <10 posts per day)

## Risks & Mitigations *(optional)*

### Risk 1: Telegram API Failure During Posting

**Description**: Telegram API may be unavailable or return errors, causing post failures

**Impact**: User's prediction is not recorded on the immutable ledger, breaking the audit trail

**Likelihood**: Low (Telegram has high uptime, but network issues possible)

**Mitigation**: 
- Display clear error message to user with exact failure reason
- Do NOT record prediction in local storage if Telegram post fails
- Provide "Retry" option for user to attempt posting again
- Log all API failures for debugging

### Risk 2: User Data Entry Errors

**Description**: User manually enters incorrect data (wrong odds, wrong team name, etc.)

**Impact**: Posted prediction contains incorrect information but cannot be edited due to immutability

**Likelihood**: Medium (human error is common)

**Mitigation**:
- Implement clear field labels and examples in the modal
- Add confirmation preview before final submission ("Review your prediction before posting")
- Accept that immutability means errors are permanent (feature, not bug)
- User can post a clarification message if needed (separate post)

### Risk 3: Telegram Bot Token Exposure

**Description**: Bot token may be exposed in logs, config files, or source control

**Impact**: Unauthorized posting to the channel, potential security breach

**Likelihood**: Medium (common configuration mistake)

**Mitigation**:
- Store bot token in environment variables or secure config file
- Never log or display the bot token in UI or terminal output
- Add `.env` to `.gitignore` to prevent accidental commits
- Document secure token management in setup instructions

### Risk 4: Message Template Breaking Changes

**Description**: Required message format may need changes after predictions are posted

**Impact**: Inconsistency across historical posts, potential confusion

**Likelihood**: Low (template is well-defined)

**Mitigation**:
- Design template to be extensible (allow adding fields without breaking old messages)
- Version the template format in each message (e.g., "Template: v1")
- Accept that old messages will use old format (immutability)
- Plan template carefully upfront to minimize need for changes

## Notes *(optional)*

### Design Philosophy

This system embraces **radical transparency and immutability**. The core principle is that predictions, once made public, cannot be altered, deleted, or spun. This creates trust through verifiable evidence rather than narrative control.

### Why Telegram?

- **Native Timestamps**: Telegram provides authoritative timestamps that are difficult to fake
- **Public Accessibility**: Channels can be viewed by anyone without login
- **No Edit History**: Edited messages show edit timestamps, preserving integrity
- **Simplicity**: No need to build custom web infrastructure for public display
- **Durability**: Telegram's infrastructure ensures long-term message retention

### Manual-Only Rationale

The system is deliberately manual to ensure:
- **Human Accountability**: Every post is a conscious human decision
- **No Automation Errors**: Prevents accidental or incorrect automated posts
- **Intentionality**: User must think through each prediction before posting
- **Flexibility**: User can choose what to post and when (not forced by automation)

### Implementation Recommendations

While this spec is technology-agnostic, the following patterns are recommended:

1. **Telegram Library**: Use `python-telegram-bot` for reliable API interaction
2. **Modal Pattern**: Use `st.dialog` (Streamlit 1.31+) or custom modal component
3. **Storage Format**: JSON Lines (.jsonl) for append-only local storage
4. **Config Management**: Use `python-decouple` or similar for environment-based config
5. **Error Handling**: Implement exponential backoff for Telegram API retries

### Future Considerations (Not in Scope)

If this feature proves valuable, future enhancements could include:

- Read-only web dashboard showing posted predictions (link to Telegram messages)
- Automated result verification via Cricsheet integration (but still manual posting)
- Multiple channel support for different leagues or bet types
- Blockchain timestamping for additional immutability verification (overkill for most use cases)
