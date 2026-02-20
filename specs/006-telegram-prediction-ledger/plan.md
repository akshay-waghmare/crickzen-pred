# Implementation Plan: Telegram Prediction Ledger

**Branch**: `006-telegram-prediction-ledger` | **Date**: 2026-01-27 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/006-telegram-prediction-ledger/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Create a manual posting system that generates immutable, timestamped prediction records by posting structured messages to a Telegram channel. The system provides three modal-based interfaces in Streamlit for posting pre-match predictions, match start context, and match results. All posts are append-only (no edits/deletes) and stored both in Telegram and local JSON storage.

**Technical Approach**: Integrate python-telegram-bot library into the existing Streamlit app (`src/bbl_pipeline/app/`), create modal UI components using Streamlit's `@st.dialog` decorator, implement append-only JSON Lines storage, and use environment-based configuration for Telegram credentials.

## Technical Context

**Language/Version**: Python 3.10+ (matches existing project requirement)  
**Primary Dependencies**: python-telegram-bot (20.x), streamlit (1.31+), python-decouple (for env config)  
**Storage**: JSON Lines (.jsonl) for append-only local storage + Telegram channel as primary ledger  
**Testing**: pytest (existing project standard)  
**Target Platform**: Desktop/server running Streamlit app (Windows/Linux)  
**Project Type**: Single Python project (extension of existing bbl_pipeline)  
**Performance Goals**: Post submission < 60 seconds, Telegram API calls < 5 seconds under normal conditions  
**Constraints**: Manual-only operation (no automation), strict message format compliance, 100% immutability  
**Scale/Scope**: Single operator, ~10 posts per day, 3 modal interfaces, 1 storage file

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Verdict**: ✅ PASS - No constitution violations

This feature does NOT involve:
- Machine learning models (Principle V does not apply)
- Tournament-specific logic (Principle I does not apply)
- Data pipelines (Principle II does not apply)
- Model versioning (Principle III does not apply)
- Entity normalization for models (Principle IV does not apply)

This is a standalone UI/integration feature for the existing Streamlit app. It extends user capabilities without touching ML pipelines or model infrastructure.

**Technical Constraints Compliance**:
- ✅ Python (existing stack)
- ✅ Type hints required (will implement)
- ✅ Unit tests required (will implement)
- ✅ Documentation required (will implement)

**No violations to justify.**


## Project Structure

### Documentation (this feature)

```text
specs/006-telegram-prediction-ledger/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
│   └── telegram_messages.json  # Message format schemas
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
src/bbl_pipeline/
├── app/
│   ├── live_streamlit_app.py         # Existing
│   ├── streamlit_app.py               # Existing
│   └── telegram_ledger_app.py         # NEW - Telegram posting UI
├── telegram/                           # NEW - Telegram integration module
│   ├── __init__.py
│   ├── bot_client.py                  # Telegram Bot API wrapper
│   ├── message_formatter.py           # Message template formatting
│   ├── storage.py                     # Append-only JSON Lines storage
│   └── config.py                      # Environment-based config
└── ...

data/
└── telegram_predictions.jsonl          # NEW - Append-only prediction storage

tests/
├── telegram/                           # NEW - Tests for Telegram module
│   ├── test_bot_client.py
│   ├── test_message_formatter.py
│   └── test_storage.py
└── ...

config/
└── .env.example                        # NEW - Example Telegram config
```

**Structure Decision**: Single project structure extending existing `bbl_pipeline`. The Telegram feature is isolated in a new `telegram` module under `src/bbl_pipeline/` with a dedicated Streamlit UI file in `app/`. This follows the existing pattern where `app/` contains Streamlit interfaces and pipeline logic is in sibling modules.

## Complexity Tracking

**No violations** - Constitution Check passed with no gates triggered. This table is not applicable.

---

## Phase 0: Research ✅ COMPLETED

**Output**: [research.md](research.md)

**Completed Research**:
1. ✅ Telegram Bot API integration patterns (decision: python-telegram-bot 20.x)
2. ✅ Streamlit modal dialog implementation (decision: @st.dialog decorator)
3. ✅ Append-only storage format (decision: JSON Lines .jsonl)
4. ✅ Message formatting approach (decision: HTML parse mode)
5. ✅ Configuration management (decision: python-decouple + .env)
6. ✅ Error handling strategy (decision: fail-fast with user feedback)

**No remaining clarifications** - All technical unknowns resolved.

---

## Phase 1: Design & Contracts ✅ COMPLETED

**Outputs**:
- ✅ [data-model.md](data-model.md) - Three entity types (Prediction, Match Start, Result)
- ✅ [contracts/telegram_messages.json](contracts/telegram_messages.json) - Message format schemas
- ✅ [quickstart.md](quickstart.md) - End-user setup and usage guide

**Design Decisions**:
1. **Entity Model**: Three independent record types stored in unified JSON Lines file
2. **Storage Strategy**: Append-only local file + Telegram as source of truth
3. **Message Templates**: HTML-formatted with structured plain text fallback
4. **Validation**: Client-side validation in Streamlit forms before API calls
5. **Error Handling**: Fail-fast with Streamlit UI feedback (no automatic retries)

**API Contracts**:
- Pre-Match Prediction: 9 required fields → structured Telegram message
- Match Start Update: 5 required fields → separate Telegram message
- Match Result: 3 required fields → outcome message with correctness indicator

---

## Phase 2: Implementation Tasks

**Status**: NOT STARTED (use `/speckit.tasks` to generate tasks.md)

**High-Level Implementation Sequence**:
1. Add dependencies to `pyproject.toml`
2. Create `src/bbl_pipeline/telegram/` module structure
3. Implement config loading (`config.py`)
4. Implement Telegram bot client (`bot_client.py`)
5. Implement message formatters (`message_formatter.py`)
6. Implement append-only storage (`storage.py`)
7. Create Streamlit UI (`app/telegram_ledger_app.py`)
8. Write unit tests
9. Create `.env.example` template
10. Integration testing with real Telegram channel

---

## Constitution Re-Check (Post-Design)

**Verdict**: ✅ PASS - No violations introduced by design decisions

**Design Compliance**:
- ✅ **Type Hints**: All modules will use Python type hints (documented in research)
- ✅ **Unit Tests**: Test strategy defined (pytest for all modules)
- ✅ **Documentation**: Comprehensive user documentation provided (quickstart.md)
- ✅ **Modularity**: Feature isolated in dedicated `telegram/` module
- ✅ **No ML Impact**: Zero changes to existing model pipelines or calibration

**No constitution amendments required.**

---

## Summary

This implementation plan documents a complete design for the Telegram Prediction Ledger feature. All research completed (Phase 0), data models defined (Phase 1), and contracts specified. The feature is ready for task breakdown and implementation (Phase 2).

**Key Artifacts**:
- 📋 Complete technical research with technology decisions
- 📊 Data model with three entity types and validation rules
- 📜 API contracts (message templates and schemas)
- 📖 End-user quickstart guide
- ✅ Constitution compliance verified (no violations)

**Next Command**: Run `/speckit.tasks` to generate implementation task breakdown in `tasks.md`.
