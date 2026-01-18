# Feature Specification: Unified T20 Models

**Feature Branch**: `3-unified-t20-models`  
**Created**: 2026-01-18  
**Status**: Draft  
**Input**: User description: "Download all club-wise T20 matches from cricsheet.org and create a single unified T20 male model and T20 female model, organized in separate male and female data folders"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Download All T20 Club Data (Priority: P1)

As a data scientist, I want to download all T20 club/franchise league data from cricsheet.org so that I have comprehensive training data for unified models.

**Why this priority**: Without data, no model can be trained. This is the foundational step.

**Independent Test**: Can verify by checking that all ZIP files are downloaded and extracted to correct folders with expected file counts.

**Acceptance Scenarios**:

1. **Given** cricsheet.org is accessible, **When** I run the download script, **Then** all T20 male club leagues are downloaded to `data/t20_male_json/`
2. **Given** cricsheet.org is accessible, **When** I run the download script, **Then** all T20 female club leagues are downloaded to `data/t20_female_json/`
3. **Given** a download completes, **When** I check the folder, **Then** JSON files are extracted and organized

---

### User Story 2 - Ingest and Process Unified Data (Priority: P2)

As a data scientist, I want to ingest all downloaded T20 matches into a unified training dataset with consistent feature engineering.

**Why this priority**: Ingestion and processing creates the training data needed for model development.

**Independent Test**: Run ingestion pipeline and verify parquet files are created with expected schema and row counts.

**Acceptance Scenarios**:

1. **Given** T20 male JSON files exist, **When** I run ingestion, **Then** unified parquet files are created at `data/t20_male_raw/`
2. **Given** raw parquet files exist, **When** I run processing, **Then** training features are created at `data/t20_male_features_v1/`
3. **Given** T20 female JSON files exist, **When** I run the same pipeline, **Then** female training features are created at `data/t20_female_features_v1/`

---

### User Story 3 - Train Unified T20 Models (Priority: P3)

As a data scientist, I want to train unified T20 models that generalize across all club leagues.

**Why this priority**: The trained model is the ultimate deliverable, but requires data first.

**Independent Test**: Train model and verify it produces better Brier score than resource_win_prob baseline.

**Acceptance Scenarios**:

1. **Given** male training features exist, **When** I train the model, **Then** a champion model is saved to `models/t20_male_v1/`
2. **Given** female training features exist, **When** I train the model, **Then** a champion model is saved to `models/t20_female_v1/`
3. **Given** trained models exist, **When** I run analyze-oof, **Then** OOF calibration report shows Brier improvement over baseline

---

### Edge Cases

- What happens when a league has incomplete or corrupted JSON files?
- How do we handle matches with missing required fields (venue, teams, result)?
- How do we handle different team naming conventions across leagues?
- What if a league has fewer than 50 matches (insufficient for reliable calibration)?

## Requirements *(mandatory)*

### Functional Requirements

#### Data Download
- **FR-001**: System MUST download all T20 male club/franchise leagues from cricsheet.org
- **FR-002**: System MUST download all T20 female club/franchise leagues from cricsheet.org
- **FR-003**: Downloads MUST be stored in separate folders: `data/t20_male_json/` and `data/t20_female_json/`
- **FR-004**: System MUST extract ZIP files and organize JSON files by league subfolder

#### Data Ingestion
- **FR-005**: System MUST ingest all male T20 JSON files to unified parquet format
- **FR-006**: System MUST ingest all female T20 JSON files to unified parquet format
- **FR-007**: System MUST add league identifier column to track source league
- **FR-008**: System MUST handle different team name formats across leagues

#### Feature Engineering
- **FR-009**: System MUST apply consistent feature engineering across all leagues
- **FR-010**: System MUST create unified feature stores for team/player/venue stats
- **FR-011**: System MUST generate `t20_male_features_v1/training.parquet` and `t20_female_features_v1/training.parquet`

#### Model Training
- **FR-012**: System MUST train XGBLogRegEnsemble model on unified male data
- **FR-013**: System MUST train XGBLogRegEnsemble model on unified female data
- **FR-014**: System MUST generate OOF calibrators using brier_optimized method
- **FR-015**: System MUST produce OOF calibration reports showing performance vs baseline

### Key Entities

- **League**: Source competition (BBL, IPL, SA20, etc.) with identifier and gender
- **Match**: Individual T20 match with standard schema (teams, venue, result, ball-by-ball)
- **TrainingSample**: Ball-by-ball row with features and is_winner target
- **UnifiedModel**: Single model trained on all leagues of same gender

## Success Criteria

1. **Data Coverage**: Download at least 10+ male leagues and 3+ female leagues
2. **Sample Size**: Male model trained on 500K+ samples, Female on 50K+ samples
3. **Model Quality**: Brier score better than resource_win_prob baseline by at least 5%
4. **Calibration**: ECE ≤ 0.02 after per-over isotonic calibration
5. **Generalization**: Model performs reasonably on held-out leagues (cross-validation)

## Scope

### In Scope
- All T20 club/franchise leagues from cricsheet.org (not international T20Is)
- Male and female leagues as separate models
- Standard XGBLogRegEnsemble architecture
- Per-over brier-optimized calibration

### Out of Scope
- International T20I matches (different dynamics)
- Test/ODI formats
- Real-time inference integration (separate feature)
- League-specific model tuning

## Assumptions

1. Cricsheet.org data is in consistent JSON format across leagues
2. Existing ingestion/processing pipeline can handle multi-league data
3. Team/venue stats will be aggregated across all leagues in feature store
4. 5-fold cross-validation is sufficient for OOF analysis

## Data Sources (from cricsheet.org)

### Male T20 Leagues
| League | URL Slug | Est. Matches |
|--------|----------|--------------|
| Big Bash League | bbl | 500+ |
| Indian Premier League | ipl | 1000+ |
| Pakistan Super League | psl | 300+ |
| Caribbean Premier League | cpl | 400+ |
| SA20 | sa20 | 120+ |
| Bangladesh Premier League | bpl | 300+ |
| Lanka Premier League | lpl | 150+ |
| International League T20 | ilt20 | 100+ |
| Major League Cricket | mlc | 50+ |
| Super Smash (NZ) | ssm | 200+ |
| County T20 Blast | t20_blast | 500+ |

*Excluded: The Hundred (100-ball format), T10 leagues (10-over format)*

### Female T20 Leagues
| League | URL Slug | Est. Matches |
|--------|----------|--------------|
| Women's Big Bash League | wbbl | 300+ |
| Women's Premier League | wpl | 70+ |
| Super Smash (Women) | ssf | 100+ |
| Women's Caribbean Premier League | wcpl | 50+ |

*Excluded: The Hundred (100-ball format)*
