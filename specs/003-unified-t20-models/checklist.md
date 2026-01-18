# Task Checklist: Unified T20 Models

**Feature Branch**: `3-unified-t20-models`
**Specification**: [spec.md](spec.md)
**Created**: 2026-01-18

## Phase 1: Data Download (P1)

### 1.1 Create Download Script
- [ ] Create `scripts/download_cricsheet_t20.py`
- [ ] Define male league list with cricsheet URL slugs
- [ ] Define female league list with cricsheet URL slugs
- [ ] Implement download function with progress bar
- [ ] Implement ZIP extraction to organized folders
- [ ] Add retry logic for failed downloads
- [ ] Add checksum/validation for downloaded files

### 1.2 Execute Downloads
- [ ] Download all male T20 leagues to `data/t20_male_json/`
- [ ] Download all female T20 leagues to `data/t20_female_json/`
- [ ] Verify file counts match expected
- [ ] Log download summary (leagues, match counts)

### 1.3 Data Validation
- [ ] Validate JSON schema consistency across leagues
- [ ] Check for required fields (teams, innings, result)
- [ ] Identify and log any problematic files
- [ ] Create data manifest with league → match count mapping

## Phase 2: Data Ingestion (P2)

### 2.1 Update Ingestion Pipeline
- [ ] Add support for multi-league ingestion in CLI
- [ ] Add `league` column to track source competition
- [ ] Add `gender` column (male/female)
- [ ] Handle team name normalization across leagues
- [ ] Create unified venue mapping

### 2.2 Run Male Ingestion
- [ ] Ingest all male T20 JSON files
- [ ] Output to `data/t20_male_raw/matches/`
- [ ] Verify parquet schema matches existing format
- [ ] Log ingestion summary (matches, balls, leagues)

### 2.3 Run Female Ingestion
- [ ] Ingest all female T20 JSON files
- [ ] Output to `data/t20_female_raw/matches/`
- [ ] Verify parquet schema
- [ ] Log ingestion summary

## Phase 3: Feature Engineering (P2)

### 3.1 Process Male Features
- [ ] Run feature processing on male raw data
- [ ] Create unified feature store at `data/t20_male_feature_store_v1/`
- [ ] Generate training parquet at `data/t20_male_features_v1/training.parquet`
- [ ] Verify feature columns match expected schema
- [ ] Log sample counts by league

### 3.2 Process Female Features
- [ ] Run feature processing on female raw data
- [ ] Create unified feature store at `data/t20_female_feature_store_v1/`
- [ ] Generate training parquet at `data/t20_female_features_v1/training.parquet`
- [ ] Verify feature columns
- [ ] Log sample counts by league

## Phase 4: Model Training (P3)

### 4.1 Train Male Model
- [ ] Train XGBLogRegEnsemble on male training data
- [ ] Save model to `models/t20_male_v1/champion_model.joblib`
- [ ] Run generate-oof to create calibrators
- [ ] Run analyze-oof to generate OOF report
- [ ] Verify Brier score improvement over resource_win_prob

### 4.2 Train Female Model
- [ ] Train XGBLogRegEnsemble on female training data
- [ ] Save model to `models/t20_female_v1/champion_model.joblib`
- [ ] Run generate-oof to create calibrators
- [ ] Run analyze-oof to generate OOF report
- [ ] Verify Brier score improvement over resource_win_prob

### 4.3 Update Model Registry
- [ ] Add t20_male_v1 to model registry
- [ ] Add t20_female_v1 to model registry
- [ ] Update copilot-instructions.md with new models
- [ ] Document model performance in README

## Phase 5: Validation & Documentation (P3)

### 5.1 Cross-League Validation
- [ ] Hold out 1-2 leagues for validation
- [ ] Test model generalization to unseen leagues
- [ ] Document cross-league performance

### 5.2 Documentation
- [ ] Create `docs/T20_UNIFIED_MODELS.md`
- [ ] Document data sources and match counts
- [ ] Document model architecture and features
- [ ] Document calibration strategy and results

### 5.3 Cleanup & Commit
- [ ] Remove temporary files
- [ ] Stage all changes
- [ ] Commit with detailed message
- [ ] Merge to main branch

## Progress Summary

| Phase | Status | Notes |
|-------|--------|-------|
| 1. Data Download | Not Started | |
| 2. Data Ingestion | Not Started | |
| 3. Feature Engineering | Not Started | |
| 4. Model Training | Not Started | |
| 5. Validation & Docs | Not Started | |

## Commands Reference

```bash
# Download data
python scripts/download_cricsheet_t20.py --gender male --output data/t20_male_json/
python scripts/download_cricsheet_t20.py --gender female --output data/t20_female_json/

# Ingest (after download)
bbl-pipeline ingest --input-dir data/t20_male_json --output-dir data/t20_male_raw
bbl-pipeline ingest --input-dir data/t20_female_json --output-dir data/t20_female_raw

# Process features
bbl-pipeline process --input-dir data/t20_male_raw/matches --output-dir data/t20_male_features_v1 --feature-store-dir data/t20_male_feature_store_v1
bbl-pipeline process --input-dir data/t20_female_raw/matches --output-dir data/t20_female_features_v1 --feature-store-dir data/t20_female_feature_store_v1

# Train models
bbl-pipeline train --input-file data/t20_male_features_v1/training.parquet --output-dir models/t20_male_v1
bbl-pipeline train --input-file data/t20_female_features_v1/training.parquet --output-dir models/t20_female_v1

# Analyze calibration
bbl-pipeline analyze-oof --input-file data/t20_male_features_v1/training.parquet --model-dir models/t20_male_v1
bbl-pipeline analyze-oof --input-file data/t20_female_features_v1/training.parquet --model-dir models/t20_female_v1
```
